"""Export service - 漫画导出服务 (migrated from app/services/export_service.py).

Implements T3 D29-D31: Transaction splitting for export operations.
- Task creation, status updates, and result writes use independent short sessions
- Image processing (CPU-bound + sync I/O) runs via asyncio.to_thread with no session held
- Prevents long-running transactions from blocking the connection pool

New architecture compliance:
- Config via ``app.core.config`` (not ``app.config``)
- DB session via ``app.core.database.async_session_factory`` (not ``app.database``)
- File I/O via ``app.infra.file_utils`` (already wrapped with asyncio.to_thread)
- All sync I/O (PIL image processing, font loading, file checks) wrapped with asyncio.to_thread
- No imports from ``app.services.*`` / ``app.adapters.*`` (legacy paths)
"""
import asyncio
import ctypes
import logging
import os
import random
import re
from datetime import datetime, timedelta
from typing import Optional, Tuple
from uuid import UUID

from PIL import Image as PILImage, ImageDraw, ImageFont
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import async_session_factory
from app.infra.file_utils import file_exists
from app.models.layout import LayoutChapter, LayoutPage, GeneratedImage
from app.models.novel import Novel
from app.repositories.task_repo import TaskRepository

logger = logging.getLogger(__name__)

# 路径片段安全字符集：中英文、数字、下划线、连字符。
# 路径分隔符、盘符冒号、"." / ".." 等一律剔除——alias_name 直接来自请求体，
# 未清洗时可用 "..\\.." 或绝对路径逃逸出 EXPORT_TARGET_DIR 写入任意文件。
_UNSAFE_PATH_CHARS = re.compile("[^0-9A-Za-z_\\-一-鿿]")
_DEFAULT_EXPORT_FOLDER = "导出漫画"
# 长图格式取值：前端与请求体默认值均为 "long_image"；
# "long_strip" 是早期 ExportRequest 默认值，历史任务记录的 input_data 里仍可能存有该值，
# 重新导出这些旧任务时同样应走长图分支。
_LONG_IMAGE_FORMATS = ("long_image", "long_strip")


def _sanitize_path_component(raw: str, max_len: int = 40) -> str:
    """清洗单个路径片段：只保留中英文/数字/下划线/连字符，并限制长度（Windows 路径长度上限）."""
    return _UNSAFE_PATH_CHARS.sub("", raw or "")[:max_len]


def _resolve_export_dir(folder_name: str) -> str:
    """拼接导出目录并校验结果仍位于 EXPORT_TARGET_DIR 之下.

    folder_name 应先经 ``_sanitize_path_component`` 清洗；此处用 realpath 做二次兜底，
    符号链接 / 绝对路径等逃逸情况一律拒绝。
    """
    base_dir = os.path.realpath(settings.EXPORT_TARGET_DIR)
    export_dir = os.path.realpath(os.path.join(base_dir, folder_name))
    base_prefix = base_dir if base_dir.endswith(os.sep) else base_dir + os.sep
    if export_dir != base_dir and not export_dir.startswith(base_prefix):
        raise ValueError(f"导出目录不在允许的根目录内，已拒绝: {folder_name}")
    return export_dir


class ExportService:
    """漫画导出服务 - 将已生成的漫画页面导出为长图 / PNG / JPG 等格式.

    导出记录以 ``Task``（task_type="export"）形式存储，无独立 Export 模型。
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.task_repo = TaskRepository(session)

    async def create_export_task(
        self,
        project_id: UUID,
        fmt: str,
        chapter_id: Optional[UUID] = None,
        quality: int = 90,
        add_alias: bool = False,
        alias_name: str = "",
    ) -> dict:
        """创建导出任务.

        T3 D29: Task creation uses the shared session (short write).
        Processing uses independent sessions to avoid holding the original session.
        """
        input_data = {
            "format": fmt,
            "chapter_id": str(chapter_id) if chapter_id else None,
            "quality": quality,
            "add_alias": add_alias,
            "alias_name": alias_name,
        }
        task = await self.task_repo.create(
            project_id=project_id,
            task_type="export",
            status="queued",
            priority="normal",
            progress=0,
            input_data=input_data,
        )
        await self.session.commit()
        # expire_on_commit=False 导致 identity map 持有陈旧 task 对象；
        # _process_export 通过独立 session 更新状态后，self.session 仍缓存旧值。
        # 手动 expire 使后续 get_export_status 从 DB 重新加载。
        # 注意: 必须在 expire 之前保存 task.id，否则访问过期属性会触发
        # AsyncSession 的同步刷新，抛出 MissingGreenlet 错误。
        task_id = task.id
        self.session.expire(task)

        # T3 D29-D31: Process export with independent sessions
        # (don't hold self.session during image processing)
        await self._process_export(task_id)

        result = await self.get_export_status(task_id)
        return result

    async def get_export_status(self, export_id: UUID) -> dict:
        """获取导出任务状态"""
        task = await self.task_repo.get(export_id)
        if not task:
            raise ValueError("Export task not found")
        return {
            "task_id": str(task.id),
            "status": task.status,
            "progress": task.progress,
            "error_message": task.error_message,
            "output_data": task.output_data,
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        }

    async def download_export(self, export_id: UUID) -> Tuple[str, str]:
        """获取导出文件路径和文件名.

        对于文件夹导出模式，返回导出目录路径供用户手动访问；
        对于单文件导出（long_image），可返回文件路径用于 HTTP 下载。
        """
        task = await self.task_repo.get(export_id)
        if not task:
            raise ValueError("Export task not found")
        if task.status != "completed":
            raise ValueError("Export task is not completed yet")
        output = task.output_data or {}
        export_dir = output.get("export_dir", "")
        # 对 long_image 格式，可以返回单个文件；否则返回文件夹路径
        file_path = output.get("file_path", "")
        filename = output.get("filename", "export.png")
        if file_path and await file_exists(file_path):
            return file_path, filename
        if export_dir and await file_exists(export_dir):
            return export_dir, f"export_{export_id}"
        raise ValueError("Export file not found on disk")

    async def cancel_export(self, export_id: UUID) -> dict:
        """取消导出任务"""
        task = await self.task_repo.get(export_id)
        if not task:
            raise ValueError("Export task not found")
        if task.status in ("completed", "failed"):
            return {"status": task.status, "message": f"Task already {task.status}"}
        await self.task_repo.update(export_id, status="cancelled")
        return {"status": "cancelled", "message": "Export cancelled"}

    async def list_exports(self, project_id: UUID) -> list:
        """获取项目的导出历史"""
        tasks, total = await self.task_repo.list(project_id=project_id, task_type="export")
        return [
            {
                "id": str(t.id),
                "task_id": str(t.id),
                "project_id": str(t.project_id) if t.project_id else None,
                "format": t.input_data.get("format") if t.input_data else None,
                "status": t.status,
                "progress": t.progress,
                "file_url": t.output_data.get("file_url") if t.output_data else None,
                "file_size": t.output_data.get("file_size") if t.output_data else None,
                "export_dir": t.output_data.get("export_dir") if t.output_data else None,
                "folder_name": t.output_data.get("folder_name") if t.output_data else None,
                "file_count": t.output_data.get("file_count") if t.output_data else None,
                "created_at": t.created_at.isoformat() if t.created_at else None,
                "updated_at": t.updated_at.isoformat() if t.updated_at else None,
            }
            for t in tasks
        ]

    async def _process_export(self, task_id: UUID):
        """实际执行导出任务.

        T3 D29-D31: Uses independent short sessions for each DB operation:
        1. Short read: get task data + page images
        2. Image processing (no session held) — sync I/O wrapped with asyncio.to_thread
        3. Short write: update task status with results
        """
        # T3 D30: Short read — get task data
        async with async_session_factory() as read_session:
            task_repo = TaskRepository(read_session)
            task = await task_repo.get(task_id)
            if not task:
                return

            input_data = task.input_data or {}
            project_id = task.project_id
            chapter_id = input_data.get("chapter_id")
            novel_id = input_data.get("novel_id")

            # D69: 单次 join 查询消除 N+1
            storage_base = settings.STORAGE_LOCAL_PATH

            page_query = (
                select(
                    LayoutPage.id,
                    LayoutPage.page_label,
                    GeneratedImage.image_url,
                    LayoutChapter.sort_order,
                    LayoutPage.sort_order,
                    Novel.title,
                    LayoutChapter.title,
                )
                .join(LayoutChapter, LayoutPage.chapter_id == LayoutChapter.id)
                .join(Novel, LayoutChapter.novel_id == Novel.id)
                .join(GeneratedImage, GeneratedImage.page_id == LayoutPage.id)
                .where(Novel.project_id == project_id)
                .where(GeneratedImage.image_url.isnot(None))
                .where(GeneratedImage.image_url != "")
            )
            # 单章导出必须收窄到该章节；否则会把整个项目所有小说的页面都导出。
            # 没有 chapter_id 时退一步限定 novel_id（若任务参数里带了）。
            if chapter_id:
                try:
                    page_query = page_query.where(LayoutChapter.id == UUID(str(chapter_id)))
                except (ValueError, TypeError):
                    logger.warning(f"导出任务 {task_id} 的 chapter_id 非法，忽略该过滤条件: {chapter_id}")
            elif novel_id:
                try:
                    page_query = page_query.where(LayoutChapter.novel_id == UUID(str(novel_id)))
                except (ValueError, TypeError):
                    logger.warning(f"导出任务 {task_id} 的 novel_id 非法，忽略该过滤条件: {novel_id}")

            rows = (
                await read_session.execute(
                    page_query.order_by(
                        LayoutChapter.sort_order,
                        LayoutPage.sort_order,
                        GeneratedImage.created_at,
                    )
                )
            ).all()

        # Process rows outside session — file checks are sync I/O, run in thread
        def _collect_page_images_sync():
            # 同一页面可能累积多条 GeneratedImage（重生成不清旧记录），按 page_id 去重，
            # rows 已按 created_at 升序排列，字典覆盖后保留的是最新一条。
            by_page = {}  # page_pk -> (page_label, file_path, ch_sort, pg_sort, file_stem)
            for row in rows:
                page_pk, page_label, image_url, ch_sort, pg_sort, novel_title, chapter_title = row
                if not image_url or not image_url.startswith("/storage/"):
                    continue
                rel = image_url[len("/storage/"):]
                img_path = os.path.join(storage_base, rel.replace("/", os.sep))
                if not os.path.isfile(img_path):
                    continue
                # page_label（P1、P2…）只在单章内唯一，跨小说/跨章节会重名互相覆盖，
                # 因此文件名加上小说与章节前缀。
                stem_parts = [
                    _sanitize_path_component(novel_title, max_len=20),
                    _sanitize_path_component(chapter_title, max_len=20),
                    _sanitize_path_component(page_label, max_len=10),
                ]
                file_stem = "_".join(p for p in stem_parts if p) or f"page{pg_sort}"
                by_page[page_pk] = (page_label, img_path, ch_sort, pg_sort, file_stem)
            return list(by_page.values())

        page_images = await asyncio.to_thread(_collect_page_images_sync)

        if not page_images:
            await self._update_task_status(
                task_id,
                status="failed",
                error_message="未找到已生成的漫画图片，请先在生图中心生成图片",
            )
            return

        page_images.sort(key=lambda x: (x[2], x[3]))

        # T3 D30: Short write — update status to processing
        await self._update_task_status(task_id, status="processing", progress=10)

        # Prepare export parameters
        quality = input_data.get("quality", 90)
        add_alias = input_data.get("add_alias", False)
        alias_name = input_data.get("alias_name") or ""

        # T3 D31: Update progress before image processing
        await self._update_task_status(task_id, progress=20)

        fmt = input_data.get("format")

        try:
            # 生成按顺序的创建时间戳（5天前开始，P1最早）
            timestamps = await asyncio.to_thread(self._generate_timestamps, len(page_images))

            # 确定导出文件夹：使用别名或默认名称。alias_name 来自请求体，
            # 必须清洗 + 校验后才能参与路径拼接。
            folder_name = _sanitize_path_component(alias_name.strip(), max_len=60) or _DEFAULT_EXPORT_FOLDER
            export_dir = _resolve_export_dir(folder_name)

            # 保存图片到目标文件夹并设置创建时间
            file_paths = await asyncio.to_thread(
                self._process_images_sync,
                page_images,
                fmt,
                quality,
                add_alias,
                alias_name,
                export_dir,
                timestamps,
            )

            # T3 D31: Short write — update task with results
            await self._update_task_status(
                task_id,
                status="completed",
                progress=100,
                output_data={
                    "export_dir": export_dir,
                    "folder_name": folder_name,
                    "file_count": len(file_paths),
                    "file_path": file_paths[0] if file_paths else "",
                    "filename": os.path.basename(file_paths[0]) if file_paths else "",
                },
            )
        except Exception as e:
            logger.error(f"Export task failed: {e}", exc_info=True)
            await self._update_task_status(task_id, status="failed", error_message=str(e))

    async def _update_task_status(
        self,
        task_id: UUID,
        status: Optional[str] = None,
        progress: Optional[int] = None,
        error_message: Optional[str] = None,
        output_data: Optional[dict] = None,
    ):
        """T3 D29-D31: Update task status using an independent short session.

        This prevents the export process from holding a long-lived session
        during CPU-bound image processing.
        """
        async with async_session_factory() as session:
            task_repo = TaskRepository(session)
            update_kwargs = {}
            if status is not None:
                update_kwargs["status"] = status
            if progress is not None:
                update_kwargs["progress"] = progress
            if error_message is not None:
                update_kwargs["error_message"] = error_message
            if output_data is not None:
                update_kwargs["output_data"] = output_data
            if update_kwargs:
                await task_repo.update(task_id, **update_kwargs)
            await session.commit()

    def _get_font(self, font_size: int = 30):
        """获取可用字体（同步方法，在 asyncio.to_thread 中调用）.

        依次尝试 simhei / simsun / msyh，均失败时回退到 PIL 默认字体。
        """
        try:
            return ImageFont.truetype("simhei.ttf", font_size)
        except IOError:
            try:
                return ImageFont.truetype("C:/Windows/Fonts/simsun.ttc", font_size)
            except IOError:
                try:
                    return ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", font_size)
                except IOError:
                    return ImageFont.load_default()

    def _draw_alias_watermark(self, img: PILImage.Image, alias_name: str, page_label: str) -> PILImage.Image:
        """在图片底部绘制作品别名水印，返回 RGB 图像（同步，在 _process_images_sync 内调用）."""
        rgba = img.convert("RGBA")
        draw = ImageDraw.Draw(rgba)
        font = self._get_font(30)
        text = f"《{alias_name}》{page_label}"
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        x = (rgba.width - tw) // 2
        y = rgba.height - th - 20
        draw.rectangle([x - 10, y - 10, x + tw + 10, y + th + 10], fill=(255, 255, 255, 200))
        draw.text((x, y), text, fill=(0, 0, 0), font=font)
        return rgba.convert("RGB")

    def _generate_timestamps(self, num_images: int) -> list:
        """生成图片创建时间戳列表。

        起始日期为导出日期往前推5天，当天08:00开始。
        第一张图片为08:05-08:10随机，后续每张与前一张相差20-30分钟。
        即 P1 最早创建时间，P2、P3... 依次递增。
        若超过22:00则跳到次日08:00继续。
        """
        base = datetime.now().replace(hour=8, minute=0, second=0, microsecond=0) - timedelta(days=5)
        timestamps = []
        current = base + timedelta(minutes=random.randint(5, 10))
        for _ in range(num_images):
            if current.hour >= 22:
                current = (current + timedelta(days=1)).replace(hour=8, minute=0, second=0, microsecond=0)
                current += timedelta(minutes=random.randint(20, 30))
            timestamps.append(current)
            current += timedelta(minutes=random.randint(20, 30))
        return timestamps

    def _generate_modify_time(self, create_dt: datetime, page_index: int = 0) -> datetime:
        """生成按顺序递增的修改时间，创建时间必须早于修改时间。

        修改时间 = 创建时间 + 5分钟基准 + page_index 秒增量，可跨日期。
        """
        modify_dt = create_dt + timedelta(minutes=5, seconds=page_index)
        return modify_dt

    def _set_file_times_windows(self, file_path: str, create_dt: datetime, modify_dt: datetime):
        """在 Windows 上设置文件创建时间和修改时间。

        使用 kernel32.SetFileTime 同时设置 lpCreationTime 和 lpLastWriteTime，
        参考加页码.py 使用 GENERIC_WRITE + FILE_FLAG_BACKUP_SEMANTICS。
        """
        # 将本地时间转换为 Windows FILETIME
        def _to_filetime(dt):
            ts = dt.timestamp()
            ft_int = int((ts + 11644473600) * 10_000_000)
            class _FT(ctypes.Structure):
                _fields_ = [("dwLowDateTime", ctypes.c_uint32),
                            ("dwHighDateTime", ctypes.c_uint32)]
            return _FT(ft_int & 0xFFFFFFFF, ft_int >> 32)

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.CreateFileW(
            file_path,
            0x40000000,    # GENERIC_WRITE
            0,             # 不共享
            None,          # 默认安全属性
            3,             # OPEN_EXISTING
            0x80,          # FILE_FLAG_BACKUP_SEMANTICS
            None,
        )
        if handle == ctypes.c_void_p(-1).value:
            logger.warning(f"设置文件时间权限不足，跳过: {file_path}")
            return

        try:
            ft_create = _to_filetime(create_dt)
            ft_modify = _to_filetime(modify_dt)
            kernel32.SetFileTime(handle, ctypes.byref(ft_create), None, ctypes.byref(ft_modify))
        finally:
            kernel32.CloseHandle(handle)

    def _process_images_sync(
        self,
        page_images: list,
        fmt: str,
        quality: int,
        add_alias: bool,
        alias_name: str,
        export_dir: str,
        timestamps: list,
    ) -> list:
        """同步处理图片拼接/保存（必须在 asyncio.to_thread 中调用）.

        CPU 密集 + 同步文件 I/O，直接调用会阻塞事件循环。
        保存完成后调用 ``_set_file_times_windows`` 设置文件创建时间和修改时间，
        修改时间按页面顺序递增（每页 +1 分钟偏移），创建时间始终早于修改时间。
        返回所有生成文件的路径列表。
        """
        import os

        if fmt in _LONG_IMAGE_FORMATS:
            os.makedirs(export_dir, exist_ok=True)
            images = []
            for page_label, img_path, _ch_sort, _pg_sort, _file_stem in page_images:
                img = PILImage.open(img_path).convert("RGB")
                if add_alias and alias_name:
                    img = self._draw_alias_watermark(img, alias_name, page_label)
                images.append(img)

            total_height = sum(img.height for img in images)
            max_width = max(img.width for img in images)
            long_image = PILImage.new("RGB", (max_width, total_height))
            y_offset = 0
            for img in images:
                long_image.paste(img, (0, y_offset))
                y_offset += img.height

            file_path = os.path.join(export_dir, "export.png")
            long_image.save(file_path, quality=quality)
            if timestamps:
                create_dt = timestamps[0]
                modify_dt = self._generate_modify_time(create_dt)
                self._set_file_times_windows(file_path, create_dt, modify_dt)
            return [file_path]
        else:
            os.makedirs(export_dir, exist_ok=True)
            ext = "jpg" if fmt == "jpg" else "png"
            file_paths = []
            for idx, (page_label, img_path, _ch_sort, _pg_sort, file_stem) in enumerate(page_images):
                img = PILImage.open(img_path).convert("RGB")
                if add_alias and alias_name:
                    img = self._draw_alias_watermark(img, alias_name, page_label)

                page_path = os.path.join(export_dir, f"{file_stem}.{ext}")
                if fmt == "jpg":
                    img.save(page_path, quality=quality)
                else:
                    img.save(page_path)
                # 按顺序设置时间：创建时间递增，修改时间按页面顺序递增
                if timestamps and idx < len(timestamps):
                    create_dt = timestamps[idx]
                    modify_dt = self._generate_modify_time(create_dt, page_index=idx)
                    self._set_file_times_windows(page_path, create_dt, modify_dt)
                file_paths.append(page_path)

            return file_paths
