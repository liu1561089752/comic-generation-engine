"""Script service - 剧情拆解 service (extracted from novel_service.py).

Implements T3 D42: AI calls use short transaction pattern (read → close → AI → new session → write).
Implements T9 problem 4: ScriptChapter/ScriptShot carry source_version + sync_status.
"""
import hashlib
import logging
from typing import Optional
from uuid import UUID

from sqlalchemy import select, delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import async_session_factory
from app.core.llm_utils import parse_llm_json
from app.infra.adapters.llm_adapter import LLMAdapter
from app.infra.adapters.base_llm import ChatMessage
from app.infra.task_progress import TaskProgressTracker
from app.models.layout import LayoutChapter, LayoutPage, LayoutShot
from app.models.novel import ScriptChapter, ScriptShot
from app.models.storyboard import StoryboardChapter, StoryboardShot
from app.repositories.novel_repo import NovelRepository
from app.infra.prompt_loader import get_prompt

logger = logging.getLogger(__name__)


class ScriptService:
    """脚本生成服务 - handles script generation and CRUD."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.novel_repo = NovelRepository(session)

    # =================================================================
    # Script generation (T3 D42: short transaction pattern)
    # =================================================================

    async def generate_script(self, novel_id: UUID, tracker: Optional[TaskProgressTracker] = None) -> dict:
        """调用LLM生成脚本（章节+镜头），保存到数据库并返回.

        T3 D42: Uses short transaction pattern:
        1. Short read transaction to get novel data
        2. AI call (no session held)
        3. Short write transaction to save results
        """
        if tracker:
            await tracker.set_running("开始生成脚本...")

        # Step 1: Short read transaction — get novel text
        async with async_session_factory() as read_session:
            novel = await NovelRepository(read_session).get(novel_id)
            if novel is None:
                raise ValueError("小说不存在")
            text = novel.cleaned_text or novel.raw_text or ""
            source_version = str(novel.updated_at.timestamp()) if novel.updated_at else None

        if not text.strip():
            raise ValueError("小说文本为空")

        MAX_CHARS = 50000
        if len(text) > MAX_CHARS:
            logger.warning(f"小说文本长度 {len(text)} 超过 {MAX_CHARS} 字符，后部分将被截断。")
        user_content = text[:MAX_CHARS]

        # Step 2: Check existing data (short read)
        async with async_session_factory() as check_session:
            existing = await self._get_script_chapters_session(check_session, novel_id)
            if existing:
                result_data = await self._build_script_response_session(check_session, novel_id)
                if tracker:
                    await tracker.complete(result_data, "脚本已存在，跳过生成")
                return result_data

        # Step 3: AI call (no session held)
        llm = LLMAdapter(
            api_key=settings.LLM_API_KEY,
            api_base=settings.LLM_API_BASE,
            model=settings.LLM_MODEL or "gpt-4o",
        )
        system_prompt = await get_prompt("novel_preprocess")
        messages = [
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="user", content=user_content),
        ]

        try:
            if tracker:
                await tracker.update_progress(10, "AI 处理中...")
            # 流式调用：增量文本实时推送到任务 stream_output（前端打字机展示），
            # 同时拼接完整内容用于解析
            full_parts: list[str] = []
            async for delta in llm.chat_stream(messages=messages):
                full_parts.append(delta)
                if tracker:
                    await tracker.push_stream(delta)
            result_content = "".join(full_parts)
            if tracker:
                await tracker.flush_stream()
                await tracker.update_progress(50, "AI 处理完成，保存脚本数据...")

            parsed = parse_llm_json(result_content)
            # LLM 可能返回 {"chapters": [...]}，也可能直接返回 [...]；两种都要兼容
            if isinstance(parsed, dict):
                chapters_data = parsed.get("chapters", [])
            else:
                chapters_data = parsed if isinstance(parsed, list) else []

            # Step 4: Short write transaction — save results
            async with async_session_factory() as write_session:
                # Delete old script data
                old_chapters = await self._get_script_chapters_session(write_session, novel_id)
                for ch in old_chapters:
                    await write_session.execute(
                        sa_delete(ScriptShot).where(ScriptShot.chapter_id == ch.id)
                    )
                    await write_session.execute(
                        sa_delete(ScriptChapter).where(ScriptChapter.id == ch.id)
                    )
                await write_session.flush()

                content_hash = hashlib.md5(result_content.encode()).hexdigest()
                for idx, ch_data in enumerate(chapters_data):
                    chapter = ScriptChapter(
                        novel_id=novel_id,
                        title=ch_data.get("chapterTitle", ""),
                        sort_order=idx,
                        source_version=source_version,
                        content_hash=content_hash,
                        sync_status="fresh",
                    )
                    write_session.add(chapter)
                    await write_session.flush()

                    shots = ch_data.get("shots", [])
                    for shot_idx, shot_data in enumerate(shots):
                        shot = ScriptShot(
                            chapter_id=chapter.id,
                            shot_id=shot_data.get("shotId", str(shot_idx + 1).zfill(2)),
                            content=shot_data.get("content", ""),
                            sort_order=shot_idx,
                            source_version=source_version,
                            sync_status="fresh",
                        )
                        write_session.add(shot)
                await write_session.flush()
                await write_session.commit()

            if tracker:
                await tracker.update_progress(90, "保存脚本数据完成")

            # Read back results
            async with async_session_factory() as result_session:
                result_data = await self._build_script_response_session(result_session, novel_id)
            if tracker:
                await tracker.complete(result_data)
            return result_data

        except Exception as e:
            if tracker:
                await tracker.fail(str(e))
            logger.error(f"AI 脚本生成失败: {e}", exc_info=True)
            raise

    # =================================================================
    # Script CRUD (uses shared session from router)
    # =================================================================

    async def get_script(self, novel_id: UUID) -> dict:
        return await self._build_script_response(self.session, novel_id)

    async def save_script(self, novel_id: UUID, chapters_data: list) -> dict:
        novel = await self.novel_repo.get(novel_id)
        if novel is None:
            raise ValueError("小说不存在")

        old_chapters = await self._get_script_chapters(self.session, novel_id)
        for ch in old_chapters:
            await self.session.execute(
                sa_delete(ScriptShot).where(ScriptShot.chapter_id == ch.id)
            )
            await self.session.execute(
                sa_delete(ScriptChapter).where(ScriptChapter.id == ch.id)
            )
        await self.session.flush()

        for idx, ch_data in enumerate(chapters_data):
            chapter = ScriptChapter(
                novel_id=novel_id,
                title=ch_data.get("chapterTitle", ""),
                sort_order=idx,
            )
            self.session.add(chapter)
            await self.session.flush()

            shots = ch_data.get("shots", [])
            for shot_idx, shot_data in enumerate(shots):
                shot = ScriptShot(
                    chapter_id=chapter.id,
                    shot_id=shot_data.get("shotId", str(shot_idx + 1).zfill(2)),
                    content=shot_data.get("content", ""),
                    sort_order=shot_idx,
                )
                self.session.add(shot)
        await self.session.flush()

        return await self._build_script_response(self.session, novel_id)

    async def split_shot(self, novel_id: UUID, chapter_id: UUID, shot_id: str,
                         content_before: str, content_after: str) -> dict:
        result = await self.session.execute(
            select(ScriptShot).where(
                ScriptShot.chapter_id == chapter_id,
                ScriptShot.shot_id == shot_id,
            )
        )
        shot = result.scalar_one_or_none()
        if shot is None:
            raise ValueError(f"镜头 {shot_id} 不存在")

        shot.content = content_before
        await self.session.flush()

        chapters = await self._get_script_chapters(self.session, novel_id)
        target_chapter = next((ch for ch in chapters if ch.id == chapter_id), None)
        if target_chapter is None:
            raise ValueError("章节不存在")

        # shot_id 是【按章】编号的（"01"、"02"…，跨章会重复），因此只能对
        # 本章内、排在被拆分镜头之后的镜头递增；一旦按全局顺序递增，后续每一章的
        # shot_id 都会被整体平移，而分镜/排版里存的旧 shot_id 不变，
        # 按 (章节, shot_id) 关联剧本内容的逻辑就会全部错位。
        subsequent_result = await self.session.execute(
            select(ScriptShot).where(
                ScriptShot.chapter_id == chapter_id,
                ScriptShot.sort_order > shot.sort_order,
            ).order_by(ScriptShot.sort_order.desc())
        )
        shifted_shot_ids = []  # [(旧 shot_id, 新 shot_id)]，按旧编号倒序
        for s in subsequent_result.scalars().all():
            old_shot_id = s.shot_id
            try:
                s.shot_id = str(int(s.shot_id) + 1).zfill(len(s.shot_id))
            except ValueError:
                s.shot_id = f"{s.shot_id}-2"
            shifted_shot_ids.append((old_shot_id, s.shot_id))
            s.sort_order += 1
        await self.session.flush()

        # 同步下游：分镜 / 排版中保存的 shot_id 也要跟着平移，否则关联关系断裂
        if shifted_shot_ids:
            await self._shift_downstream_shot_ids(
                novel_id, target_chapter.sort_order, shifted_shot_ids
            )

        try:
            new_shot_id = str(int(shot_id) + 1).zfill(len(shot_id))
        except ValueError:
            new_shot_id = f"{shot_id}-copy"
        new_shot = ScriptShot(
            chapter_id=chapter_id,
            shot_id=new_shot_id,
            content=content_after,
            sort_order=shot.sort_order + 1,
        )
        self.session.add(new_shot)
        await self.session.flush()

        return await self._build_script_response(self.session, novel_id)

    async def _shift_downstream_shot_ids(
        self, novel_id: UUID, chapter_sort_order: int, shifted: list
    ) -> None:
        """把本章 shot_id 的平移结果同步到分镜 / 排版数据.

        章节之间按 sort_order 对应（分镜、排版章节均按脚本章节顺序生成，
        参见 layout/service.py 的 (chapter_sort_order, shot_id) 关联键）。
        shifted 为 [(旧 shot_id, 新 shot_id)]；映射表在改动前一次性快照，
        每个对象只会命中一次旧编号，不会出现连锁改名。
        """
        sb_result = await self.session.execute(
            select(StoryboardShot)
            .join(StoryboardChapter, StoryboardShot.chapter_id == StoryboardChapter.id)
            .where(
                StoryboardChapter.novel_id == novel_id,
                StoryboardChapter.sort_order == chapter_sort_order,
            )
        )
        sb_by_shot_id = {}
        for s in sb_result.scalars().all():
            sb_by_shot_id.setdefault(s.shot_id, []).append(s)

        layout_result = await self.session.execute(
            select(LayoutShot)
            .join(LayoutPage, LayoutShot.page_id == LayoutPage.id)
            .join(LayoutChapter, LayoutPage.chapter_id == LayoutChapter.id)
            .where(
                LayoutChapter.novel_id == novel_id,
                LayoutChapter.sort_order == chapter_sort_order,
            )
        )
        layout_by_shot_id = {}
        for s in layout_result.scalars().all():
            layout_by_shot_id.setdefault(s.shot_id, []).append(s)

        for old_shot_id, new_shot_id in shifted:
            for s in sb_by_shot_id.get(old_shot_id, []):
                s.shot_id = new_shot_id
            for s in layout_by_shot_id.get(old_shot_id, []):
                s.shot_id = new_shot_id
        await self.session.flush()

    # =================================================================
    # Helpers (work with any session)
    # =================================================================

    async def _get_script_chapters(self, session: AsyncSession, novel_id: UUID):
        return await self._get_script_chapters_session(session, novel_id)

    async def _get_script_chapters_session(self, session: AsyncSession, novel_id: UUID):
        result = await session.execute(
            select(ScriptChapter)
            .where(ScriptChapter.novel_id == novel_id)
            .order_by(ScriptChapter.sort_order)
        )
        return list(result.scalars().all())

    async def _build_script_response(self, session: AsyncSession, novel_id: UUID) -> dict:
        return await self._build_script_response_session(session, novel_id)

    async def _build_script_response_session(self, session: AsyncSession, novel_id: UUID) -> dict:
        chapters = await self._get_script_chapters_session(session, novel_id)
        if not chapters:
            return {"chapters": []}

        chapter_ids = [ch.id for ch in chapters]
        all_shots_result = await session.execute(
            select(ScriptShot)
            .where(ScriptShot.chapter_id.in_(chapter_ids))
            .order_by(ScriptShot.chapter_id, ScriptShot.sort_order)
        )
        from collections import defaultdict
        shots_by_chapter = defaultdict(list)
        for s in all_shots_result.scalars().all():
            shots_by_chapter[s.chapter_id].append(s)

        result = []
        for ch in chapters:
            shots = [
                {
                    "id": str(s.id),
                    "shot_id": s.shot_id,
                    "content": s.content,
                    "sort_order": s.sort_order,
                }
                for s in shots_by_chapter.get(ch.id, [])
            ]
            result.append({
                "id": str(ch.id),
                "title": ch.title,
                "sort_order": ch.sort_order,
                "shots": shots,
            })
        return {"chapters": result}
