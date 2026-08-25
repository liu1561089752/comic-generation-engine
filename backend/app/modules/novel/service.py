"""Novel service - 小说 CRUD + 文本解析 service (extracted from novel_service.py).

Handles novel upload, preprocessing, editor, and chapter management.
AI-dependent preprocess_novel implements T3 D42 (short transaction pattern).
"""
import asyncio
import logging
import os
import re
from typing import Optional, List
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.core.database import async_session_factory
from app.core.llm_utils import parse_llm_json
from app.infra.adapters.llm_adapter import LLMAdapter
from app.infra.adapters.base_llm import ChatMessage
from app.infra.task_progress import TaskProgressTracker
from app.models.novel import Chapter
from app.repositories.novel_repo import (
    NovelRepository, ChapterRepository,
    ParagraphRepository, EditorVersionRepository,
)
from app.schemas.novel_schema import ChapterUpdate
from app.infra.prompt_loader import get_prompt

logger = logging.getLogger(__name__)


class NovelService:
    """小说 CRUD + 文本解析服务 (slim, extracted from God Object)."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.novel_repo = NovelRepository(session)
        self.chapter_repo = ChapterRepository(session)
        self.paragraph_repo = ParagraphRepository(session)
        self.version_repo = EditorVersionRepository(session)

    # =================================================================
    # Novel upload & preprocessing
    # =================================================================

    async def upload_novel(
        self,
        project_id: UUID,
        file_content: bytes,
        filename: str,
        title: str = None,
    ) -> dict:
        """上传小说文件并解析保存. 支持 txt / docx / md 三种格式.

        约束：一个项目只允许上传一本小说；项目已存在小说时拒绝再次上传。
        """
        # 校验：一个项目只允许一本小说
        existing = await self.novel_repo.list(project_id=project_id, skip=0, limit=1)
        if existing[0]:
            raise ValueError("该项目已上传过小说，每个项目仅允许上传一本小说")

        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "txt"
        if ext not in ("txt", "docx", "md"):
            raise ValueError(f"不支持的文件格式: .{ext}，仅支持 txt / docx / md")

        if ext == "docx":
            raw_text = await asyncio.to_thread(self._parse_docx, file_content)
        elif ext == "md":
            raw_text = self._parse_md(file_content)
        else:
            raw_text = self._parse_txt(file_content)

        word_count = self._count_words(raw_text)
        if not title:
            title = filename.rsplit(".", 1)[0]

        novel = await self.novel_repo.create(
            project_id=project_id,
            title=title,
            raw_text=raw_text,
            word_count=word_count,
            format=ext,
        )

        chapter = await self.chapter_repo.create(
            novel_id=novel.id,
            chapter_number=1,
            title="第 1 章",
            content=raw_text,
            status="pending",
        )

        paragraphs = self._split_paragraphs(raw_text)
        for i, para_text in enumerate(paragraphs):
            num_str = str(i + 1).zfill(4)
            await self.paragraph_repo.create(
                chapter_id=chapter.id,
                paragraph_number=num_str,
                text=para_text,
                sort_order=i,
            )

        return {
            "id": novel.id,
            "title": novel.title,
            "word_count": word_count,
            "format": ext,
            "chapter_count": 1,
        }

    async def delete_novel(self, project_id: UUID, novel_id: UUID) -> dict:
        """删除小说及其全部下游数据（章节/段落/版本/脚本/分镜/排版/生成图片文件）。

        每项目仅允许一本小说，删除后项目回到"未导入"状态，可重新上传。
        图片文件删除不可回滚，放在数据库事务提交成功之后执行。
        """
        storage_dir = os.path.join(
            settings.STORAGE_LOCAL_PATH,
            str(project_id),
            "generation",
            str(novel_id),
        )

        async with async_session_factory() as write_session:
            repo = NovelRepository(write_session)
            novel = await repo.get(novel_id)
            if novel is None or str(novel.project_id) != str(project_id):
                raise ValueError("小说不存在")
            # ORM 级联删除：chapters/paragraphs/versions、script、storyboard、layout 及下游
            await write_session.delete(novel)
            await write_session.commit()
            logger.info(f"小说已删除: {novel_id} (project={project_id})")

        # 事务提交成功后再删图片目录（失败只记 warning，不阻塞删除结果）
        try:
            if os.path.exists(storage_dir):
                import shutil
                shutil.rmtree(storage_dir, ignore_errors=True)
                logger.info(f"已删除小说图片目录: {storage_dir}")
        except Exception as e:
            logger.warning(f"删除小说图片目录失败，残留文件待人工清理: {storage_dir}, error: {e}")

        return {"deleted": True, "novel_id": str(novel_id)}

    async def _read_novel_text(self, novel_id: UUID) -> str:
        """短事务读取小说文本，返回截断后的文本。"""
        async with async_session_factory() as read_session:
            novel = await NovelRepository(read_session).get(novel_id)
            if novel is None:
                raise ValueError("小说不存在")
            raw = novel.raw_text or ""
            if not raw.strip():
                raise ValueError("小说文本为空")

        MAX_CHARS = 50000
        if len(raw) > MAX_CHARS:
            logger.warning(
                f"小说文本长度 {len(raw)} 超过 {MAX_CHARS} 字符，后部分将被截断。"
                f"建议后续实现分块处理。"
            )
        return raw[:MAX_CHARS]

    async def _call_preprocess_ai(self, raw_content: str) -> dict:
        """调用 AI 进行小说预处理（章节拆分），不持有 DB session。"""
        llm = LLMAdapter(
            api_key=settings.LLM_API_KEY,
            api_base=settings.LLM_API_BASE,
            model=settings.LLM_MODEL or "gpt-4o",
        )
        system_prompt = await get_prompt("novel_preprocess")
        messages = [
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="user", content=raw_content),
        ]
        result = await llm.chat(messages=messages, temperature=0.2)
        return parse_llm_json(result.content)

    async def _save_preprocess_result(self, novel_id: UUID, chapters_data: list, raw: str) -> dict:
        """短事务保存预处理结果：删除旧章节、创建新章节、更新小说统计。"""
        cleaned = self._clean_text(raw)
        word_count = self._count_words(cleaned)

        async with async_session_factory() as write_session:
            novel_repo = NovelRepository(write_session)
            chapter_repo = ChapterRepository(write_session)
            paragraph_repo = ParagraphRepository(write_session)

            valid_chapters = [ch for ch in chapters_data if ch.get("shots")]
            if not valid_chapters:
                raise ValueError("AI 未返回有效章节数据，已保留原有章节")

            old_chapters = await chapter_repo.list_all(novel_id=novel_id)
            for ch in old_chapters:
                await chapter_repo.delete(ch.id)

            for idx, ch in enumerate(valid_chapters, start=1):
                chapter_title = ch.get("chapterTitle", "")
                shots = ch.get("shots", [])
                shot_content = "\n".join(s["content"] for s in shots if s.get("content"))
                chapter = await chapter_repo.create(
                    novel_id=novel_id, chapter_number=idx,
                    title=chapter_title, content=shot_content, status="pending",
                )
                paragraphs = self._split_paragraphs(shot_content)
                for i, para_text in enumerate(paragraphs):
                    num_str = str(i + 1).zfill(4)
                    await paragraph_repo.create(
                        chapter_id=chapter.id, paragraph_number=num_str,
                        text=para_text, sort_order=i,
                    )

            remaining_chapters = await chapter_repo.list_all(
                novel_id=novel_id, order_by=Chapter.chapter_number.asc()
            )
            for idx, ch in enumerate(remaining_chapters):
                if ch.chapter_number != idx + 1:
                    await chapter_repo.update(ch.id, chapter_number=idx + 1)

            await novel_repo.update(novel_id, cleaned_text=cleaned, word_count=word_count)
            await write_session.commit()

        return {
            "novel_id": str(novel_id),
            "word_count": word_count,
            "chapters": chapters_data,
            "chapter_count": len(chapters_data),
        }

    async def preprocess_novel(self, novel_id: UUID, tracker: Optional[TaskProgressTracker] = None) -> dict:
        """预处理小说文本（调用 AI 进行章节拆分和镜头划分）.

        T3 D42: Short transaction pattern:
        1. Short read: get novel text
        2. AI call (no session held)
        3. Short write: create chapters/paragraphs + renumber + update novel

        已拆分为 _read_novel_text → _call_preprocess_ai → _save_preprocess_result 三个子方法。
        """
        if tracker:
            await tracker.set_running("开始预处理小说...")

        raw = await self._read_novel_text(novel_id)

        try:
            parsed = await self._call_preprocess_ai(raw)
            if tracker:
                await tracker.update_progress(70, "AI 处理完成，保存章节数据...")

            chapters_data = parsed.get("chapters", [])
            result_data = await self._save_preprocess_result(novel_id, chapters_data, raw)

            if tracker:
                await tracker.update_progress(90, "保存完成")
                await tracker.complete(result_data)
            return result_data
        except Exception as e:
            if tracker:
                await tracker.fail(str(e))
            logger.error(f"AI 预处理失败: {e}", exc_info=True)
            raise

    async def update_novel_text(self, novel_id: UUID, raw_text: str) -> dict:
        """更新小说文本并重新统计"""
        novel = await self.novel_repo.get(novel_id)
        if novel is None:
            raise ValueError("小说不存在")
        cleaned = self._clean_text(raw_text)
        word_count = self._count_words(cleaned)
        paragraphs = self._split_paragraphs(cleaned)
        await self.novel_repo.update(novel_id, raw_text=raw_text, cleaned_text=cleaned, word_count=word_count)
        return {
            "id": str(novel.id),
            "cleaned_text": cleaned,
            "paragraphs": paragraphs,
            "word_count": word_count,
        }

    async def get_novel_detail(self, novel_id: UUID) -> dict:
        """获取小说详情（含章节概要）"""
        novel = await self.novel_repo.get(novel_id)
        if novel is None:
            raise ValueError("小说不存在")

        chapters = await self.chapter_repo.list_all(
            novel_id=novel_id, order_by=Chapter.chapter_number.asc()
        )
        total = len(chapters)

        chapter_ids = [ch.id for ch in chapters]
        paragraphs_map = await self.paragraph_repo.list_by_chapter_ids(chapter_ids)

        chapter_list = []
        for ch in chapters:
            paragraphs = paragraphs_map.get(ch.id, [])
            stats = {"dialogue": 0, "narration": 0, "action": 0, "description": 0, "unmarked": 0}
            for p in paragraphs:
                if p.annotation_type:
                    stats[p.annotation_type] = stats.get(p.annotation_type, 0) + 1
                else:
                    stats["unmarked"] = stats.get("unmarked", 0) + 1

            chapter_list.append({
                "id": ch.id,
                "chapter_number": ch.chapter_number,
                "title": ch.title,
                "status": ch.status,
                "paragraph_count": len(paragraphs),
                "paragraph_stats": stats,
                "created_at": ch.created_at.isoformat() if ch.created_at else None,
                "updated_at": ch.updated_at.isoformat() if ch.updated_at else None,
            })

        return {
            "id": novel.id,
            "project_id": novel.project_id,
            "title": novel.title,
            "author": novel.author,
            "word_count": novel.word_count,
            "format": novel.format,
            "raw_text": novel.raw_text,
            "cleaned_text": novel.cleaned_text,
            "created_at": novel.created_at.isoformat() if novel.created_at else None,
            "updated_at": novel.updated_at.isoformat() if novel.updated_at else None,
            "chapters": chapter_list,
        }

    async def list_chapters(self, novel_id: UUID) -> List[dict]:
        """获取章节列表"""
        chapters = await self.chapter_repo.list_all(
            novel_id=novel_id, order_by=Chapter.chapter_number.asc()
        )
        chapter_ids = [ch.id for ch in chapters]
        paragraphs_map = await self.paragraph_repo.list_by_chapter_ids(chapter_ids)
        result = []
        for ch in chapters:
            paragraphs = paragraphs_map.get(ch.id, [])
            stats = {"dialogue": 0, "narration": 0, "action": 0, "description": 0, "unmarked": 0}
            for p in paragraphs:
                if p.annotation_type:
                    stats[p.annotation_type] = stats.get(p.annotation_type, 0) + 1
                else:
                    stats["unmarked"] = stats.get("unmarked", 0) + 1

            result.append({
                "id": ch.id,
                "novel_id": ch.novel_id,
                "chapter_number": ch.chapter_number,
                "title": ch.title,
                "status": ch.status,
                "paragraph_count": len(paragraphs),
                "paragraph_stats": stats,
                "created_at": ch.created_at.isoformat() if ch.created_at else None,
                "updated_at": ch.updated_at.isoformat() if ch.updated_at else None,
            })
        return result

    # =================================================================
    # Editor API
    # =================================================================

    async def get_chapter_detail(self, chapter_id: UUID) -> dict:
        """获取章节详情（含段落）"""
        chapter = await self.chapter_repo.get(chapter_id)
        if chapter is None:
            raise ValueError("章节不存在")

        paragraphs = await self.paragraph_repo.list_by_chapter(chapter_id)

        stats = {"dialogue": 0, "narration": 0, "action": 0, "description": 0, "unmarked": 0}
        para_list = []

        if paragraphs:
            for p in paragraphs:
                if p.annotation_type:
                    stats[p.annotation_type] = stats.get(p.annotation_type, 0) + 1
                else:
                    stats["unmarked"] = stats.get("unmarked", 0) + 1

                para_list.append({
                    "id": str(p.id),
                    "paragraph_number": p.paragraph_number,
                    "text": p.text,
                    "annotation_type": p.annotation_type,
                    "annotation_content": p.annotation_content,
                    "comment": p.comment,
                    "sort_order": p.sort_order,
                })
        elif chapter.content:
            content_paragraphs = self._split_paragraphs(chapter.content)
            for i, text in enumerate(content_paragraphs):
                num_str = str(i + 1).zfill(4)
                stats["unmarked"] += 1
                para_list.append({
                    "id": f"temp-{num_str}",
                    "paragraph_number": num_str,
                    "text": text,
                    "annotation_type": None,
                    "annotation_content": None,
                    "comment": None,
                    "sort_order": i,
                })

        return {
            "id": str(chapter.id),
            "novel_id": chapter.novel_id,
            "chapter_number": chapter.chapter_number,
            "title": chapter.title,
            "status": chapter.status,
            "content": chapter.content,
            "paragraphs": para_list,
            "paragraph_stats": stats,
            "created_at": chapter.created_at.isoformat() if chapter.created_at else None,
            "updated_at": chapter.updated_at.isoformat() if chapter.updated_at else None,
        }

    async def save_editor(
        self, chapter_id: UUID, paragraphs_data: list, summary: Optional[str] = None
    ) -> dict:
        """保存编辑器内容: 替换段落 + 创建版本快照.

        M11: 使用 SELECT FOR UPDATE 锁定章节行，防止并发保存丢失更新。
        """
        ch_result = await self.session.execute(
            select(Chapter).where(Chapter.id == chapter_id).with_for_update()
        )
        chapter = ch_result.scalar_one_or_none()
        if chapter is None:
            raise ValueError("章节不存在")

        full_text = "\n\n".join([p.get("text", "") for p in paragraphs_data])

        await self.paragraph_repo.delete_by_chapter(chapter_id)
        for i, item in enumerate(paragraphs_data):
            await self.paragraph_repo.create(
                chapter_id=chapter_id,
                paragraph_number=item.get("paragraph_number", str(i + 1).zfill(4)),
                text=item.get("text", ""),
                annotation_type=item.get("annotation_type"),
                annotation_content=item.get("annotation_content"),
                comment=item.get("comment"),
                sort_order=i,
            )

        await self.chapter_repo.update(chapter_id, content=full_text)

        max_ver = await self.version_repo.get_max_version(chapter_id)
        new_version = await self.version_repo.create(
            chapter_id=chapter_id,
            version_number=max_ver + 1,
            summary=summary or f"版本 {max_ver + 1}",
            content_snapshot=[
                {
                    "paragraph_number": p.get("paragraph_number", str(i + 1).zfill(4)),
                    "text": p.get("text", ""),
                    "annotation_type": p.get("annotation_type"),
                    "annotation_content": p.get("annotation_content"),
                    "comment": p.get("comment"),
                }
                for i, p in enumerate(paragraphs_data)
            ],
        )

        return {
            "version_id": str(new_version.id),
            "version_number": new_version.version_number,
            "paragraph_count": len(paragraphs_data),
        }

    async def get_version_history(self, chapter_id: UUID) -> List[dict]:
        """获取版本历史"""
        versions = await self.version_repo.list_by_chapter(chapter_id)
        return [
            {
                "id": str(v.id),
                "chapter_id": str(v.chapter_id),
                "version_number": v.version_number,
                "summary": v.summary,
                "created_at": v.created_at.isoformat() if v.created_at else None,
            }
            for v in versions
        ]

    async def get_version_detail(self, version_id: UUID) -> dict:
        """获取版本详情"""
        version = await self.version_repo.get(version_id)
        if version is None:
            raise ValueError("版本不存在")
        return {
            "id": str(version.id),
            "chapter_id": str(version.chapter_id),
            "version_number": version.version_number,
            "summary": version.summary,
            "content_snapshot": version.content_snapshot,
            "created_at": version.created_at.isoformat() if version.created_at else None,
        }

    async def restore_version(self, chapter_id: UUID, version_id: UUID) -> dict:
        """恢复版本.

        M11: 使用 SELECT FOR UPDATE 锁定章节行，防止并发恢复/保存丢失更新。
        """
        version = await self.version_repo.get(version_id)
        if version is None:
            raise ValueError("版本不存在")
        if version.chapter_id != chapter_id:
            raise ValueError("版本不属于当前章节")

        # 锁定章节行，序列化并发 restore/save
        ch_result = await self.session.execute(
            select(Chapter).where(Chapter.id == chapter_id).with_for_update()
        )
        if ch_result.scalar_one_or_none() is None:
            raise ValueError("章节不存在")

        snapshot = version.content_snapshot or []

        await self.paragraph_repo.delete_by_chapter(chapter_id)
        full_text_parts = []
        for i, item in enumerate(snapshot):
            await self.paragraph_repo.create(
                chapter_id=chapter_id,
                paragraph_number=item.get("paragraph_number", str(i + 1).zfill(4)),
                text=item.get("text", ""),
                annotation_type=item.get("annotation_type"),
                annotation_content=item.get("annotation_content"),
                comment=item.get("comment"),
                sort_order=i,
            )
            full_text_parts.append(item.get("text", ""))

        full_text = "\n\n".join(full_text_parts)
        await self.chapter_repo.update(chapter_id, content=full_text)

        max_ver = await self.version_repo.get_max_version(chapter_id)
        await self.version_repo.create(
            chapter_id=chapter_id,
            version_number=max_ver + 1,
            summary=f"恢复至版本 {version.version_number}",
            content_snapshot=snapshot,
        )

        return {"restored": True, "from_version": version.version_number}

    # =================================================================
    # Chapter management API
    # =================================================================

    async def update_chapter(self, chapter_id: UUID, data: ChapterUpdate) -> dict:
        """更新章节信息"""
        chapter = await self.chapter_repo.get(chapter_id)
        if chapter is None:
            raise ValueError("章节不存在")

        update_kwargs = {}
        if data.title is not None:
            update_kwargs["title"] = data.title
        if data.content is not None:
            update_kwargs["content"] = data.content
        if data.status is not None:
            update_kwargs["status"] = data.status

        if update_kwargs:
            await self.chapter_repo.update(chapter_id, **update_kwargs)

        updated = await self.chapter_repo.get(chapter_id)
        return {
            "id": str(updated.id),
            "novel_id": updated.novel_id,
            "chapter_number": updated.chapter_number,
            "title": updated.title,
            "status": updated.status,
            "updated_at": updated.updated_at.isoformat() if updated.updated_at else None,
        }

    async def merge_chapters(self, source_chapter_id: UUID, target_chapter_id: UUID) -> dict:
        """合并章节（将源章节合并到目标章节）"""
        if source_chapter_id == target_chapter_id:
            raise ValueError("源章节与目标章节不能相同")
        source = await self.chapter_repo.get(source_chapter_id)
        target = await self.chapter_repo.get(target_chapter_id)
        if source is None or target is None:
            raise ValueError("源章节或目标章节不存在")
        if source.novel_id != target.novel_id:
            raise ValueError("只能合并同一小说下的章节")

        source_paragraphs = await self.paragraph_repo.list_by_chapter(source_chapter_id)
        target_paragraphs = await self.paragraph_repo.list_by_chapter(target_chapter_id)

        offset = len(target_paragraphs)
        for i, p in enumerate(source_paragraphs):
            new_num = str(offset + i + 1).zfill(4)
            await self.paragraph_repo.create(
                chapter_id=target_chapter_id,
                paragraph_number=new_num,
                text=p.text,
                annotation_type=p.annotation_type,
                annotation_content=p.annotation_content,
                comment=p.comment,
                sort_order=offset + i,
            )

        all_paragraphs = await self.paragraph_repo.list_by_chapter(target_chapter_id)
        full_text = "\n\n".join([p.text for p in all_paragraphs])
        await self.chapter_repo.update(target_chapter_id, content=full_text)

        novel_id = source.novel_id
        deleted_number = source.chapter_number

        # 先删源章节再递补后续编号，避免中间态出现两章同号
        await self.chapter_repo.delete(source_chapter_id)

        chapters = await self.chapter_repo.list_all(novel_id=novel_id)
        chapters_sorted = sorted(chapters, key=lambda c: c.chapter_number)
        for ch in chapters_sorted:
            if ch.chapter_number > deleted_number:
                await self.chapter_repo.update(ch.id, chapter_number=ch.chapter_number - 1)

        return {
            "merged": True,
            "target_chapter_id": str(target_chapter_id),
            "total_paragraphs": len(all_paragraphs),
        }

    async def split_chapter(self, chapter_id: UUID, split_at_paragraph_number: str) -> dict:
        """分割章节"""
        chapter = await self.chapter_repo.get(chapter_id)
        if chapter is None:
            raise ValueError("章节不存在")

        paragraphs = await self.paragraph_repo.list_by_chapter(chapter_id)
        split_index = None
        for i, p in enumerate(paragraphs):
            if p.paragraph_number == split_at_paragraph_number:
                split_index = i + 1
                break

        if split_index is None:
            raise ValueError(f"未找到段落编号: {split_at_paragraph_number}")
        if split_index >= len(paragraphs):
            raise ValueError("分割点不能在最后一个段落之后")

        latter_paragraphs = paragraphs[split_index:]

        # 后半章必须紧跟原章节，其后的章节编号整体顺延一位；
        # 倒序更新避免中间态出现重复编号
        origin_num = chapter.chapter_number
        new_chapter_num = origin_num + 1
        chapters_desc = await self.chapter_repo.list_all(
            novel_id=chapter.novel_id, order_by=Chapter.chapter_number.desc()
        )
        for ch in chapters_desc:
            if ch.chapter_number > origin_num:
                await self.chapter_repo.update(ch.id, chapter_number=ch.chapter_number + 1)

        latter_text = "\n\n".join([p.text for p in latter_paragraphs])
        new_chapter = await self.chapter_repo.create(
            novel_id=chapter.novel_id,
            chapter_number=new_chapter_num,
            title=f"第 {new_chapter_num} 章",
            content=latter_text,
            status=chapter.status,
        )

        for i, p in enumerate(latter_paragraphs):
            new_num = str(i + 1).zfill(4)
            await self.paragraph_repo.update(
                p.id,
                chapter_id=new_chapter.id,
                paragraph_number=new_num,
                sort_order=i,
            )

        former_paragraphs = paragraphs[:split_index]
        former_text = "\n\n".join([p.text for p in former_paragraphs])
        await self.chapter_repo.update(chapter_id, content=former_text)

        for i, p in enumerate(former_paragraphs):
            new_num = str(i + 1).zfill(4)
            await self.paragraph_repo.update(p.id, paragraph_number=new_num, sort_order=i)

        chapters = await self.chapter_repo.list_all(novel_id=chapter.novel_id)
        chapters_sorted = sorted(chapters, key=lambda c: c.chapter_number)
        for idx, ch in enumerate(chapters_sorted):
            if ch.chapter_number != idx + 1:
                await self.chapter_repo.update(ch.id, chapter_number=idx + 1)

        return {
            "split": True,
            "original_chapter_id": str(chapter_id),
            "new_chapter_id": str(new_chapter.id),
            "new_chapter_number": new_chapter_num,
        }

    # =================================================================
    # Text parsing helpers
    # =================================================================

    def _parse_txt(self, content: bytes) -> str:
        return content.decode("utf-8", errors="replace")

    def _parse_docx(self, content: bytes) -> str:
        try:
            from docx import Document
            from io import BytesIO

            doc = Document(BytesIO(content))
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            return "\n\n".join(paragraphs)
        except ImportError:
            raise RuntimeError("python-docx 未安装，无法解析 .docx 文件")
        except Exception as e:
            raise RuntimeError(f"解析 .docx 文件失败: {e}")

    def _parse_md(self, content: bytes) -> str:
        text = content.decode("utf-8", errors="replace")
        text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
        text = re.sub(r"\*{1,3}(.*?)\*{1,3}", r"\1", text)
        text = re.sub(r"`([^`]+)`", r"\1", text)
        text = re.sub(r"!\[.*?\]\(.*?\)", "", text)
        text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
        text = re.sub(r"^-{3,}\s*$", "", text, flags=re.MULTILINE)
        text = re.sub(r"^>\s?", "", text, flags=re.MULTILINE)
        return text.strip()

    def _clean_text(self, text: str) -> str:
        """基本清洗：合并连续空行、去除首尾空白"""
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def _split_paragraphs(self, text: str) -> List[str]:
        """按空行或换行分割段落"""
        paragraphs = re.split(r"\n\s*\n", text)
        return [p.strip() for p in paragraphs if p.strip()]

    def _count_words(self, text: str) -> int:
        """统计字数（中英文混合）"""
        if not text:
            return 0
        chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
        english_words = len(re.findall(r"[a-zA-Z]+", text))
        return chinese_chars + english_words
