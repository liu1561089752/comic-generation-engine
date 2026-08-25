"""Generation service - 漫画图片生成 service (extracted from novel_service.py).

Implements T3 D42: AI calls use short transaction pattern (read → close → AI → new session → write).
"""
import asyncio
import base64
import logging
import os
from typing import Optional, Dict, Any, Tuple
from uuid import UUID

from sqlalchemy import select, delete as sa_delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import async_session_factory
from app.infra.adapters.image_gen_adapter import ImageGenAdapter
from app.infra.adapters.http_client import HttpClientManager
from app.infra.file_utils import read_bytes, write_bytes_atomic, makedirs, rmtree, remove_file
from app.infra.task_progress import TaskProgressTracker
from app.models.layout import LayoutChapter, LayoutPage, LayoutShot, ImagePrompt, GeneratedImage, ReferenceMatch
from app.models.storyboard import StoryboardChapter, StoryboardShot
from app.models.novel import ScriptChapter, ScriptShot
from app.models.world import SceneAsset, Prop, Building, Outfit
from app.models.character import Character, CharacterReferenceImage, CharacterState
from app.repositories import layout_repo
from app.repositories.novel_repo import NovelRepository
from app.infra.prompt_loader import get_prompt

logger = logging.getLogger(__name__)


class GenerationService:
    """漫画图片生成服务."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.novel_repo = NovelRepository(session)

    async def _load_reference_images_data(
        self, session: AsyncSession, reference_ids: list[str]
    ) -> Tuple[str, list[str]]:
        """根据参考图ID列表加载参考图信息.

        C14: 批量查询 6 张表（每表一次 IN 查询），替代逐 ID × 6 表的 N+1 模式。

        Returns:
            desc_text: 描述文本，如"给你提供的参考图分别是：场景-森林、道具-矿泉水"
            base64_images: base64 编码的图片列表（data URI 格式）
        """
        if not reference_ids:
            return "", []

        valid_uuids = []
        for ref_id in reference_ids:
            try:
                valid_uuids.append(UUID(ref_id))
            except (ValueError, TypeError):
                continue
        if not valid_uuids:
            return "", []

        ref_map: dict[UUID, tuple[str, Optional[str]]] = {}

        if valid_uuids:
            r = await session.execute(select(SceneAsset).where(SceneAsset.id.in_(valid_uuids)))
            for a in r.scalars().all():
                ref_map[a.id] = (f"场景-{a.name}", a.image_url or None)

            r = await session.execute(select(Prop).where(Prop.id.in_(valid_uuids)))
            for p in r.scalars().all():
                ref_map[p.id] = (f"道具-{p.name}", p.image_url or None)

            r = await session.execute(select(Building).where(Building.id.in_(valid_uuids)))
            for b in r.scalars().all():
                ref_map[b.id] = (f"建筑-{b.name}", b.image_url or None)

            r = await session.execute(select(Outfit).where(Outfit.id.in_(valid_uuids)))
            for o in r.scalars().all():
                ref_map[o.id] = (f"服装-{o.name}", o.image_url or None)

            r = await session.execute(select(Character).where(Character.id.in_(valid_uuids)))
            # 批量查询角色默认形象图（state_id IS NULL 表示默认）
            cri_for_char_r = await session.execute(
                select(CharacterReferenceImage)
                .where(
                    CharacterReferenceImage.character_id.in_(valid_uuids),
                    CharacterReferenceImage.state_id.is_(None),
                )
            )
            char_default_img = {cri.character_id: cri.image_url for cri in cri_for_char_r.scalars().all()}
            for c in r.scalars().all():
                img_url = char_default_img.get(c.id)
                ref_map[c.id] = (f"角色-{c.name}", img_url or None)

            r = await session.execute(select(CharacterReferenceImage).where(CharacterReferenceImage.id.in_(valid_uuids)))
            for cri in r.scalars().all():
                ref_map[cri.id] = (f"角色参考-{cri.angle or '多角度'}", cri.image_url or None)

            # CharacterState references — resolve state_id -> CharacterReferenceImage
            state_r = await session.execute(select(CharacterState).where(CharacterState.id.in_(valid_uuids)))
            all_states = list(state_r.scalars().all())
            if all_states:
                state_ids_list = [s.id for s in all_states]
                cri_for_state_r = await session.execute(
                    select(CharacterReferenceImage).where(
                        CharacterReferenceImage.state_id.in_(state_ids_list)
                    )
                )
                state_img_map: dict = {}
                for cri in cri_for_state_r.scalars().all():
                    if cri.state_id:
                        state_img_map[cri.state_id] = cri.image_url
                for s in all_states:
                    img_url = state_img_map.get(s.id)
                    if img_url:
                        ref_map[s.id] = (f"角色状态-{s.name}", img_url)

        descriptions = []
        image_urls = []
        for ref_id in reference_ids:
            try:
                ref_uuid = UUID(ref_id)
            except (ValueError, TypeError):
                continue
            entry = ref_map.get(ref_uuid)
            if entry:
                desc, img_url = entry
                descriptions.append(desc)
                if img_url:
                    image_urls.append(img_url)

        desc_text = "给你提供的参考图分别是：" + "、".join(descriptions) if descriptions else ""

        # 问题 9: 生图 API 的图片预算控制——base64 图片体积大，
        # 每张约 1-3MB，超过 5 张容易撑爆 API token / 请求体上限。
        # 文字描述保留全部，仅截断实际发送的图片。
        MAX_IMAGES_FOR_API = 5
        if len(image_urls) > MAX_IMAGES_FOR_API:
            logger.warning(
                f"参考图数量 {len(image_urls)} 超过 API 图片预算 {MAX_IMAGES_FOR_API}，"
                f"仅发送前 {MAX_IMAGES_FOR_API} 张"
            )
            image_urls = image_urls[:MAX_IMAGES_FOR_API]

        # 将图片转为 base64
        base64_images = []
        for url in image_urls:
            try:
                file_path = url
                if url.startswith("/storage/"):
                    file_path = os.path.join(
                        settings.STORAGE_LOCAL_PATH,
                        url[len("/storage/"):].lstrip("/")
                    )

                if os.path.exists(file_path):
                    img_data = await read_bytes(file_path)
                    if img_data:
                        b64_str = base64.b64encode(img_data).decode("utf-8")
                        base64_images.append(f"data:image/png;base64,{b64_str}")
                else:
                    logger.warning(f"参考图文件不存在: {file_path}")
            except Exception as e:
                logger.warning(f"读取参考图失败: {url}, error: {e}")

        return desc_text, base64_images

    async def generate_single_page_image(
        self, project_id: UUID, novel_id: UUID, page_id: str,
        reference_ids: Optional[list[str]] = None,
        tracker: Optional[TaskProgressTracker] = None,
    ) -> dict:
        """为指定页面生成图片.

        T3 D42: Uses short transaction pattern:
        1. Short read: get target page + reference images
        2. AI call + image download (no session held)
        3. Short write: update image_url
        """
        if tracker:
            await tracker.set_running(f"开始生成页面 {page_id} 图片...")

        # Step 1: Short read — find target page + load reference images
        async with async_session_factory() as read_session:
            target_page = await self._find_page_by_label(read_session, novel_id, page_id)
            if target_page is None:
                raise ValueError(f"页面 {page_id} 不存在")
            if not target_page["image_prompt"]:
                raise ValueError(f"页面 {page_id} 暂无生图提示词，请先生成提示词")

            # Load reference images if provided
            desc_text = ""
            base64_images: list[str] = []
            if reference_ids:
                desc_text, base64_images = await self._load_reference_images_data(read_session, reference_ids)

        try:
            # Step 2: AI call + image download (no session held)
            comic_prompt = await get_prompt("comic_page_generation")
            full_prompt = f"{comic_prompt}\n\n{target_page['image_prompt']}"
            if desc_text:
                full_prompt = f"{desc_text}\n\n{full_prompt}"

            params: Dict[str, Any] = {"aspectRatio": "3:4", "imageSize": "1K"}
            if base64_images:
                params["images"] = base64_images

            image_gen = ImageGenAdapter()
            gen_result = await image_gen.generate(full_prompt, params=params)
            image_url = gen_result.get("image_url", "")
            if not image_url:
                raise ValueError(f"页面 {page_id} 生图结果无URL")

            if tracker:
                await tracker.update_progress(50, "图片已生成，正在下载...")

            # Download image to local storage
            storage_dir = os.path.join(
                settings.STORAGE_LOCAL_PATH,
                str(project_id),
                "generation",
                str(novel_id),
            )
            await makedirs(storage_dir, exist_ok=True)

            filename = f"{page_id}.png"
            filepath = os.path.join(storage_dir, filename)

            # T1: 使用 httpx.AsyncClient 替代 requests + asyncio.to_thread
            client = HttpClientManager.get_image_client()
            resp = await client.get(
                image_url,
                headers={
                    "User-Agent": "Mozilla/5.0.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
                    "Accept-Language": "zh-CN,zh;q=0.9",
                    "Referer": "https://grsai.dakka.com.cn/",
                },
            )
            resp.raise_for_status()
            await write_bytes_atomic(filepath, resp.content)

            local_path = f"/storage/{project_id}/generation/{novel_id}/{filename}"

            # Step 3: Short write — save GeneratedImage record
            async with async_session_factory() as write_session:
                # 重生成时先清掉该页旧记录：同一 page_id 累积多条 selected 会让
                # 导出（长图拼接）把同一页重复输出。
                await write_session.execute(
                    sa_delete(GeneratedImage).where(GeneratedImage.page_id == target_page["id"])
                )
                write_session.add(GeneratedImage(
                    page_id=target_page["id"],
                    image_url=local_path,
                    is_selected="selected",
                ))
                await write_session.commit()
            logger.info(f"页面 {page_id} 图片已生成: {local_path}")

            if tracker:
                await tracker.update_progress(100, f"页面 {page_id} 图片已保存")

            async with async_session_factory() as result_session:
                result = await self._build_layout_response_session(result_session, novel_id)
            if tracker:
                await tracker.complete(result)
            return result
        except Exception as e:
            if tracker:
                await tracker.fail(str(e))
            raise

    async def generate_page_images(
        self, project_id: UUID, novel_id: UUID,
        reference_ids: Optional[Dict[str, list[str]]] = None,
        tracker: Optional[TaskProgressTracker] = None,
    ) -> dict:
        """为已有提示词的页面生成图片.

        T3 D42: Uses short transaction pattern:
        1. Short read: get all pages needing images + their reference images
        2. Parallel AI calls + downloads (no session held)
        3. Short write: batch update image_url
        """
        if tracker:
            await tracker.set_running("开始生成各页面图片...")

        # Step 1: Short read — get all pages needing images
        async with async_session_factory() as read_session:
            chapters = await self._get_layout_chapters_session(read_session, novel_id)
            if not chapters:
                raise ValueError("请先生成排版")

            # Collect all pages that need image generation (have prompt, no image)
            all_pages = []
            for ch in chapters:
                pages_result = await read_session.execute(
                    select(LayoutPage)
                    .options(
                        selectinload(LayoutPage.image_prompt),
                        selectinload(LayoutPage.reference_match),
                        selectinload(LayoutPage.generated_images),
                    )
                    .where(LayoutPage.chapter_id == ch.id)
                    .order_by(LayoutPage.sort_order)
                )
                for p in pages_result.scalars().all():
                    if p.image_prompt and not p.generated_images:
                        all_pages.append({
                            "id": p.id,
                            "page_label": p.page_label,
                            "image_prompt": p.image_prompt.full_prompt if p.image_prompt else "",
                            "reference_ids": p.reference_match.ref_ids if p.reference_match else [],
                        })

        # 分页限制：只处理前 100 页
        if settings.PAGE_LIMIT_ENABLED and len(all_pages) > 100:
            logger.info(f"PAGE_LIMIT_ENABLED=True，生图只处理前 100 页（共 {len(all_pages)} 页）")
            all_pages = all_pages[:100]
            if tracker:
                await tracker.update_progress(0, "开始生成各页面图片（前100页模式）...")

        if not all_pages:
            async with async_session_factory() as empty_session:
                return await self._build_layout_response_session(empty_session, novel_id)

        # Pre-load reference images for all pages (within the read session is already closed,
        # so we load per-page inside the task)
        ref_ids_map = reference_ids or {}
        total_pages = len(all_pages)
        completed_pages = 0
        failed_page_labels: list[str] = []
        image_results: Dict[str, str] = {}  # page_label -> local_path
        tracker_lock = asyncio.Lock()

        # Step 2: Parallel AI calls + downloads (no session held)
        semaphore = asyncio.Semaphore(settings.IMAGE_MAX_CONCURRENT)
        comic_prompt = await get_prompt("comic_page_generation")

        async def fetch_image(index: int) -> None:
            nonlocal completed_pages
            page = all_pages[index]
            async with semaphore:
                try:
                    # Load reference images in a short read session
                    page_ref_ids = ref_ids_map.get(page["page_label"]) if page["page_label"] in ref_ids_map else page["reference_ids"]
                    desc_text = ""
                    base64_images: list[str] = []
                    if page_ref_ids:
                        async with async_session_factory() as ref_session:
                            desc_text, base64_images = await self._load_reference_images_data(ref_session, page_ref_ids)

                    full_prompt = f"{comic_prompt}\n\n{page['image_prompt']}"
                    if desc_text:
                        full_prompt = f"{desc_text}\n\n{full_prompt}"

                    params: Dict[str, Any] = {"aspectRatio": "3:4", "imageSize": "1K"}
                    if base64_images:
                        params["images"] = base64_images

                    # 自定义重试：仅对 API 返回 "generate failed" 时重试（最多 3 次）
                    # 其他错误（超时、502、连接错误等）由 adapter 层 max_retries=1 不重试，直接抛出
                    max_gen_retries = 3
                    image_url = ""
                    for img_attempt in range(max_gen_retries):
                        try:
                            image_gen = ImageGenAdapter(max_retries=1, request_timeout=180)
                            gen_result = await image_gen.generate(full_prompt, params=params)
                            image_url = gen_result.get("image_url", "")
                            break  # 成功，退出重试循环
                        except RuntimeError as e:
                            error_msg = str(e)
                            if "generate failed" in error_msg and img_attempt < max_gen_retries - 1:
                                logger.warning(
                                    f"页面 {page['page_label']} 生图失败（generate failed），"
                                    f"第 {img_attempt+2}/{max_gen_retries} 次重试..."
                                )
                                continue
                            raise  # 非 generate failed 错误或重试用完，向外抛
                    if not image_url:
                        raise ValueError("生图结果无URL")

                    # Download image to local storage
                    storage_dir = os.path.join(
                        settings.STORAGE_LOCAL_PATH,
                        str(project_id),
                        "generation",
                        str(novel_id),
                    )
                    await makedirs(storage_dir, exist_ok=True)

                    filename = f"{page['page_label']}.png"
                    filepath = os.path.join(storage_dir, filename)

                    client = HttpClientManager.get_image_client()
                    resp = await client.get(
                        image_url,
                        headers={
                            "User-Agent": "Mozilla/5.0.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                            "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
                            "Accept-Language": "zh-CN,zh;q=0.9",
                            "Referer": "https://grsai.dakka.com.cn/",
                        },
                    )
                    resp.raise_for_status()
                    await write_bytes_atomic(filepath, resp.content)

                    local_path = f"/storage/{project_id}/generation/{novel_id}/{filename}"
                    image_results[page["page_label"]] = local_path
                    logger.info(f"页面 {page['page_label']} 图片已保存: {local_path}")

                    # 问题 5: 只有成功才计入 completed
                    async with tracker_lock:
                        completed_pages += 1
                        if tracker and total_pages > 0:
                            pct = int(completed_pages / total_pages * 90)
                            await tracker.update_progress(pct, f"已生成 {completed_pages}/{total_pages} 页图片")

                except Exception as e:
                    logger.error(f"页面 {page['page_label']} 生图失败: {e}")
                    async with tracker_lock:
                        failed_page_labels.append(page["page_label"])

        tasks = [fetch_image(i) for i in range(total_pages)]
        # T2: return_exceptions 防止单页失败导致全批中断
        await asyncio.gather(*tasks, return_exceptions=True)

        # Step 3: Short write — batch save GeneratedImage records
        if image_results:
            async with async_session_factory() as write_session:
                # 获取所有需要更新的页面ID
                all_labels = list(image_results.keys())
                pages_r = await write_session.execute(
                    select(LayoutPage.id, LayoutPage.page_label)
                    .where(LayoutPage.page_label.in_(all_labels))
                    .where(LayoutPage.chapter_id.in_(
                        select(LayoutChapter.id).where(LayoutChapter.novel_id == novel_id)
                    ))
                )
                page_id_map = {label: pid for pid, label in pages_r.all()}
                # 与单页生图一致：先清掉这些页面的旧记录，避免同页累积多条导致导出重复
                target_page_ids = [
                    pid for pid in (page_id_map.get(lbl) for lbl in image_results) if pid
                ]
                if target_page_ids:
                    await write_session.execute(
                        sa_delete(GeneratedImage).where(GeneratedImage.page_id.in_(target_page_ids))
                    )
                for page_label, local_path in image_results.items():
                    page_id = page_id_map.get(page_label)
                    if page_id:
                        write_session.add(GeneratedImage(
                            page_id=page_id,
                            image_url=local_path,
                            is_selected="selected",
                        ))
                await write_session.commit()

        async with async_session_factory() as result_session:
            result = await self._build_layout_response_session(result_session, novel_id)

        # 问题 5: 聚合失败结果，报告部分失败而非全部完成
        if failed_page_labels:
            result["failed_pages"] = failed_page_labels
            result["failed_count"] = len(failed_page_labels)
            result["success_count"] = completed_pages
            if tracker:
                if completed_pages == 0:
                    await tracker.fail(
                        f"全部 {total_pages} 页生图失败: {', '.join(failed_page_labels[:5])}"
                    )
                else:
                    await tracker.complete(
                        result,
                        f"部分成功: {completed_pages}/{total_pages} 页完成，"
                        f"失败 {len(failed_page_labels)} 页: {', '.join(failed_page_labels[:5])}"
                    )
            logger.warning(
                f"生图部分失败: 成功 {completed_pages}/{total_pages}, "
                f"失败页: {failed_page_labels}"
            )
        elif tracker:
            await tracker.complete(result)

        return result

    async def batch_delete_pages_content(
        self, project_id: UUID, novel_id: UUID,
        start_page: int, end_page: int, delete_type: str,
    ) -> dict:
        """批量删除指定页面的内容（支持按范围和类型删除）.

        Args:
            start_page: 起始页码（1-based，全局页索引）
            end_page: 结束页码（1-based，包含）
            delete_type: "prompt" | "reference" | "page"
                - prompt: 清空生图提示词 (image_prompt)
                - reference: 清空参考图 (reference_ids)
                - page: 删除漫画页图片 (image_url + 图片文件)
        """
        # 1. 获取所有页面并按全局顺序排列
        async with async_session_factory() as read_session:
            chapters = await self._get_layout_chapters_session(read_session, novel_id)
            if not chapters:
                return {"status": "ok", "affected_pages": 0}

            all_pages = []
            for ch in chapters:
                result = await read_session.execute(
                    select(LayoutPage)
                    .where(LayoutPage.chapter_id == ch.id)
                    .order_by(LayoutPage.sort_order)
                )
                for p in result.scalars().all():
                    all_pages.append(p)

        if not all_pages:
            return {"status": "ok", "affected_pages": 0}

        # 2. 校验页码范围（1-based → 0-based slice）
        start_idx = max(0, start_page - 1)
        end_idx = min(len(all_pages) - 1, end_page - 1)
        if start_idx > end_idx:
            raise ValueError(f"页码范围无效: {start_page}-{end_page}，总页数 {len(all_pages)}")

        target_pages = all_pages[start_idx:end_idx + 1]
        target_ids = [p.id for p in target_pages]
        page_labels = [p.page_label for p in target_pages]

        # 3. 根据类型执行删除
        # 文件删除不可回滚，必须放在数据库事务提交成功之后；否则事务失败会留下
        # image_url 指向已删除文件的悬挂记录（前端显示有图、实际 404）。
        pending_image_files = []
        async with async_session_factory() as write_session:
            if delete_type == "prompt":
                # 删除 ImagePrompt 记录（cascade 不会反向触发，需手动删）
                await write_session.execute(
                    sa_delete(ImagePrompt).where(ImagePrompt.page_id.in_(target_ids))
                )
                affected = len(target_ids)
                logger.info(f"批量清空提示词: pages={page_labels}, count={affected}")

            elif delete_type == "reference":
                # 删除 ReferenceMatch 记录
                await write_session.execute(
                    sa_delete(ReferenceMatch).where(ReferenceMatch.page_id.in_(target_ids))
                )
                affected = len(target_ids)
                logger.info(f"批量清空参考图: pages={page_labels}, count={affected}")

            elif delete_type == "page":
                # 删除漫画页图片：先删 GeneratedImage 记录，图片文件留到事务提交后再删
                storage_dir = os.path.join(
                    settings.STORAGE_LOCAL_PATH,
                    str(project_id),
                    "generation",
                    str(novel_id),
                )
                pending_image_files = [
                    os.path.join(storage_dir, f"{label}.png") for label in page_labels
                ]

                await write_session.execute(
                    sa_delete(GeneratedImage).where(GeneratedImage.page_id.in_(target_ids))
                )
                affected = len(target_ids)
                logger.info(f"批量删除漫画页图片: pages={page_labels}, count={affected}")
            else:
                raise ValueError(f"不支持的删除类型: {delete_type}，可选: prompt / reference / page")

            await write_session.commit()

        # 4. 事务提交成功后再删图片文件；逐文件失败只记 warning，最多残留垃圾文件，
        # 不能让文件层面的失败影响已提交的删除结果。
        for filepath in pending_image_files:
            try:
                if os.path.exists(filepath):
                    await remove_file(filepath)
                    logger.info(f"已删除图片文件: {filepath}")
            except Exception as e:
                logger.warning(f"删除图片文件失败，残留文件待人工清理: {filepath}, error: {e}")

        return {"status": "ok", "affected_pages": affected, "pages": page_labels}

    async def delete_all_storyboard_and_generation(self, project_id: UUID, novel_id: UUID) -> dict:
        """删除所有分镜及下游数据（排版、生图提示词、参考图、漫画页图片）.

        调用方注意：此操作不可撤销，会删除：
          1. 所有漫画页图片文件
          2. LayoutPage 记录（含 image_prompt / image_url / reference_ids）
          3. LayoutChapter 记录
          4. StoryboardShot 记录
          5. StoryboardChapter 记录

        文件删除不可回滚，必须放在数据库事务提交成功之后；否则事务失败会留下
        image_url 指向已删除文件的悬挂记录。
        """
        storage_dir = os.path.join(
            settings.STORAGE_LOCAL_PATH,
            str(project_id),
            "generation",
            str(novel_id),
        )

        async with async_session_factory() as write_session:
            # 1. 删除 Layout 数据（LayoutPage → LayoutChapter）
            layout_chapters = await self._get_layout_chapters_session(write_session, novel_id)
            layout_chapter_ids = [ch.id for ch in layout_chapters]
            if layout_chapter_ids:
                # 先删子表（外键依赖 LayoutPage.id）
                page_ids_subq = select(LayoutPage.id).where(LayoutPage.chapter_id.in_(layout_chapter_ids))
                await write_session.execute(
                    sa_delete(GeneratedImage).where(GeneratedImage.page_id.in_(page_ids_subq))
                )
                await write_session.execute(
                    sa_delete(ReferenceMatch).where(ReferenceMatch.page_id.in_(page_ids_subq))
                )
                await write_session.execute(
                    sa_delete(ImagePrompt).where(ImagePrompt.page_id.in_(page_ids_subq))
                )
                await write_session.execute(
                    sa_delete(LayoutShot).where(LayoutShot.page_id.in_(page_ids_subq))
                )
                await write_session.execute(
                    sa_delete(LayoutPage).where(LayoutPage.chapter_id.in_(layout_chapter_ids))
                )
                # 再删 LayoutChapter
                await write_session.execute(
                    sa_delete(LayoutChapter).where(LayoutChapter.id.in_(layout_chapter_ids))
                )
                logger.info(f"已删除 Layout 数据: {len(layout_chapter_ids)} 个章节")

            # 2. 删除分镜数据（StoryboardShot → StoryboardChapter）
            sb_result = await write_session.execute(
                select(StoryboardChapter).where(StoryboardChapter.novel_id == novel_id)
            )
            sb_chapter_ids = [ch.id for ch in sb_result.scalars().all()]
            if sb_chapter_ids:
                # 先删 StoryboardShot（外键依赖）
                await write_session.execute(
                    sa_delete(StoryboardShot).where(StoryboardShot.chapter_id.in_(sb_chapter_ids))
                )
                # 再删 StoryboardChapter
                await write_session.execute(
                    sa_delete(StoryboardChapter).where(StoryboardChapter.id.in_(sb_chapter_ids))
                )
                logger.info(f"已删除分镜数据: {len(sb_chapter_ids)} 个章节")

            await write_session.commit()

        # 3. 事务提交成功后再删图片目录；删除失败最多残留垃圾文件，不影响数据一致性
        await self._remove_storage_dir(storage_dir)

        return {
            "status": "ok",
            "deleted_layout_chapters": len(layout_chapter_ids),
            "deleted_storyboard_chapters": len(sb_chapter_ids),
        }

    async def delete_all_layout_and_generation(self, project_id: UUID, novel_id: UUID) -> dict:
        """删除所有排版及下游数据（生图提示词、参考图、漫画页图片），保留分镜数据.

        调用方注意：此操作不可撤销，会删除：
          1. 所有漫画页图片文件
          2. LayoutPage 记录（含 image_prompt / image_url / reference_ids）
          3. LayoutChapter 记录

        文件删除不可回滚，必须放在数据库事务提交成功之后；否则事务失败会留下
        image_url 指向已删除文件的悬挂记录。
        """
        storage_dir = os.path.join(
            settings.STORAGE_LOCAL_PATH,
            str(project_id),
            "generation",
            str(novel_id),
        )

        async with async_session_factory() as write_session:
            # 1. 删除 Layout 数据（LayoutPage → LayoutChapter），Storyboard 不受影响
            layout_chapters = await self._get_layout_chapters_session(write_session, novel_id)
            layout_chapter_ids = [ch.id for ch in layout_chapters]
            if layout_chapter_ids:
                # 先删子表（外键依赖 LayoutPage.id）
                page_ids_subq = select(LayoutPage.id).where(LayoutPage.chapter_id.in_(layout_chapter_ids))
                await write_session.execute(
                    sa_delete(GeneratedImage).where(GeneratedImage.page_id.in_(page_ids_subq))
                )
                await write_session.execute(
                    sa_delete(ReferenceMatch).where(ReferenceMatch.page_id.in_(page_ids_subq))
                )
                await write_session.execute(
                    sa_delete(ImagePrompt).where(ImagePrompt.page_id.in_(page_ids_subq))
                )
                await write_session.execute(
                    sa_delete(LayoutShot).where(LayoutShot.page_id.in_(page_ids_subq))
                )
                await write_session.execute(
                    sa_delete(LayoutPage).where(LayoutPage.chapter_id.in_(layout_chapter_ids))
                )
                await write_session.execute(
                    sa_delete(LayoutChapter).where(LayoutChapter.id.in_(layout_chapter_ids))
                )
                logger.info(f"已删除排版数据: {len(layout_chapter_ids)} 个章节")

            await write_session.commit()

        # 2. 事务提交成功后再删图片目录
        await self._remove_storage_dir(storage_dir)

        return {
            "status": "ok",
            "deleted_layout_chapters": len(layout_chapter_ids),
        }

    async def delete_all_layout_pages(self, project_id: UUID, novel_id: UUID) -> dict:
        """删除所有漫画页的图片：清空所有 GeneratedImage 记录 + 删除已下载的图片文件，保留排版/提示词等数据.

        H2: 改用原子 DELETE（单条 SQL），替代 read-modify-write 循环。

        文件删除不可回滚，必须放在数据库事务提交成功之后；否则事务失败会留下
        image_url 指向已删除文件的悬挂记录。
        """
        storage_dir = os.path.join(
            settings.STORAGE_LOCAL_PATH,
            str(project_id),
            "generation",
            str(novel_id),
        )

        # 1. 原子 DELETE：删除所有 GeneratedImage 记录
        async with async_session_factory() as write_session:
            chapters = await self._get_layout_chapters_session(write_session, novel_id)
            chapter_ids = [ch.id for ch in chapters]
            cleared = 0
            if chapter_ids:
                page_ids_subq = (
                    select(LayoutPage.id)
                    .where(LayoutPage.chapter_id.in_(chapter_ids))
                    .subquery()
                )
                result = await write_session.execute(
                    sa_delete(GeneratedImage)
                    .where(GeneratedImage.page_id.in_(page_ids_subq))
                )
                cleared = result.rowcount or 0
            await write_session.commit()

        # 2. 事务提交成功后再删图片目录
        await self._remove_storage_dir(storage_dir)

        return {"status": "ok", "cleared_pages": cleared}

    async def delete_all_script_and_downstream(self, project_id: UUID, novel_id: UUID) -> dict:
        """删除所有脚本及下游数据（分镜、排版、生图提示词、参考图、漫画页图片）.

        保留：角色提取、世界观、场景、道具、建筑、服饰等资产数据不受影响。

        调用方注意：此操作不可撤销，会删除：
          1. 已下载的漫画页图片文件
          2. GeneratedImage / ReferenceMatch / ImagePrompt 记录
          3. LayoutShot / LayoutPage / LayoutChapter 记录
          4. StoryboardShot / StoryboardChapter 记录
          5. ScriptShot / ScriptChapter 记录

        文件删除不可回滚，必须放在数据库事务提交成功之后；否则事务失败会留下
        image_url 指向已删除文件的悬挂记录。
        """
        storage_dir = os.path.join(
            settings.STORAGE_LOCAL_PATH,
            str(project_id),
            "generation",
            str(novel_id),
        )

        async with async_session_factory() as write_session:
            # 1. 删除 Layout 数据（LayoutPage → LayoutChapter）
            layout_chapters = await self._get_layout_chapters_session(write_session, novel_id)
            layout_chapter_ids = [ch.id for ch in layout_chapters]
            if layout_chapter_ids:
                page_ids_subq = select(LayoutPage.id).where(LayoutPage.chapter_id.in_(layout_chapter_ids))
                await write_session.execute(
                    sa_delete(GeneratedImage).where(GeneratedImage.page_id.in_(page_ids_subq))
                )
                await write_session.execute(
                    sa_delete(ReferenceMatch).where(ReferenceMatch.page_id.in_(page_ids_subq))
                )
                await write_session.execute(
                    sa_delete(ImagePrompt).where(ImagePrompt.page_id.in_(page_ids_subq))
                )
                await write_session.execute(
                    sa_delete(LayoutShot).where(LayoutShot.page_id.in_(page_ids_subq))
                )
                await write_session.execute(
                    sa_delete(LayoutPage).where(LayoutPage.chapter_id.in_(layout_chapter_ids))
                )
                await write_session.execute(
                    sa_delete(LayoutChapter).where(LayoutChapter.id.in_(layout_chapter_ids))
                )
                logger.info(f"已删除 Layout 数据: {len(layout_chapter_ids)} 个章节")

            # 2. 删除分镜数据（StoryboardShot → StoryboardChapter）
            sb_result = await write_session.execute(
                select(StoryboardChapter).where(StoryboardChapter.novel_id == novel_id)
            )
            sb_chapter_ids = [ch.id for ch in sb_result.scalars().all()]
            if sb_chapter_ids:
                await write_session.execute(
                    sa_delete(StoryboardShot).where(StoryboardShot.chapter_id.in_(sb_chapter_ids))
                )
                await write_session.execute(
                    sa_delete(StoryboardChapter).where(StoryboardChapter.id.in_(sb_chapter_ids))
                )
                logger.info(f"已删除分镜数据: {len(sb_chapter_ids)} 个章节")

            # 3. 删除脚本数据（ScriptShot → ScriptChapter）
            sc_result = await write_session.execute(
                select(ScriptChapter).where(ScriptChapter.novel_id == novel_id)
            )
            sc_chapter_ids = [ch.id for ch in sc_result.scalars().all()]
            if sc_chapter_ids:
                await write_session.execute(
                    sa_delete(ScriptShot).where(ScriptShot.chapter_id.in_(sc_chapter_ids))
                )
                await write_session.execute(
                    sa_delete(ScriptChapter).where(ScriptChapter.id.in_(sc_chapter_ids))
                )
                logger.info(f"已删除脚本数据: {len(sc_chapter_ids)} 个章节")

            await write_session.commit()

        # 4. 事务提交成功后再删图片目录
        await self._remove_storage_dir(storage_dir)

        return {
            "status": "ok",
            "deleted_script_chapters": len(sc_chapter_ids),
            "deleted_storyboard_chapters": len(sb_chapter_ids),
            "deleted_layout_chapters": len(layout_chapter_ids),
        }

    # =================================================================
    # Helpers
    # =================================================================

    async def _remove_storage_dir(self, storage_dir: str) -> None:
        """删除图片目录 —— 仅允许在数据库事务提交成功之后调用.

        文件删除不可回滚，因此失败只记 warning：残留文件由后续清理兜底，
        不能让文件层面的失败影响已提交的删除结果。
        """
        try:
            if os.path.exists(storage_dir):
                await rmtree(storage_dir, ignore_errors=True)
                logger.info(f"已删除图片目录: {storage_dir}")
        except Exception as e:
            logger.warning(f"删除图片目录失败，残留文件待人工清理: {storage_dir}, error: {e}")

    async def _find_page_by_label(self, session: AsyncSession, novel_id: UUID, page_id: str) -> Optional[dict]:
        """Find a LayoutPage by its page_label, return as dict (detached from session).

        Uses selectinload to avoid N+1 (H1): single query for chapters + pages.
        """
        result = await session.execute(
            select(LayoutChapter)
            .options(
                selectinload(LayoutChapter.pages).selectinload(LayoutPage.image_prompt),
            )
            .where(LayoutChapter.novel_id == novel_id)
            .order_by(LayoutChapter.sort_order)
        )
        for ch in result.scalars().all():
            for p in ch.pages:
                if p.page_label == page_id:
                    return {
                        "id": p.id,
                        "page_label": p.page_label,
                        "image_prompt": p.image_prompt.full_prompt if p.image_prompt else "",
                        "image_url": "",
                    }
        return None

    async def _get_layout_chapters_session(self, session: AsyncSession, novel_id: UUID):
        return await layout_repo.get_layout_chapters_session(session, novel_id)

    async def _build_layout_response_session(self, session: AsyncSession, novel_id: UUID) -> dict:
        return await layout_repo.build_layout_response_session(session, novel_id)
