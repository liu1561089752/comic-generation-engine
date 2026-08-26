"""Storyboard service - 分镜 service (extracted from novel_service.py).

Implements T3 D42: AI calls use short transaction pattern.
Implements T9 problem 4: StoryboardChapter/StoryboardShot carry source_version + sync_status.
"""
import asyncio
import hashlib
import json
import logging
from typing import Optional, List
from uuid import UUID

from sqlalchemy import select, delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import async_session_factory
from app.core.llm_utils import parse_llm_json
from app.infra.adapters.llm_adapter import LLMAdapter
from app.infra.adapters.base_llm import ChatMessage
from app.infra.task_progress import TaskProgressTracker
from app.models.novel import Novel, ScriptChapter, ScriptShot
from app.models.storyboard import StoryboardChapter, StoryboardShot
from app.repositories.novel_repo import NovelRepository
from app.infra.prompt_loader import get_prompt

logger = logging.getLogger(__name__)


class StoryboardService:
    """分镜生成服务."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.novel_repo = NovelRepository(session)

    async def _call_storyboard_llm(self, chapter_data: dict, novel_text: str = "") -> List[dict]:
        llm = LLMAdapter(
            api_key=settings.LLM_API_KEY,
            api_base=settings.LLM_API_BASE,
            model=settings.LLM_MODEL or "gpt-4o",
        )
        system_prompt = await get_prompt("storyboard_generation")
        user_content = ""
        if novel_text:
            user_content = f"小说原始完整文本：\n{novel_text}\n\n"
        user_content += json.dumps(chapter_data, ensure_ascii=False)
        messages = [
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="user", content=user_content),
        ]
        result = await llm.chat(messages=messages)
        parsed = parse_llm_json(result.content)
        shots = parsed.get("shots", [])
        original_ids = {s["shotId"] for s in chapter_data["shots"]}
        returned_ids = {s["shotId"] for s in shots}
        if original_ids != returned_ids:
            missing = original_ids - returned_ids
            extra = returned_ids - original_ids
            raise ValueError(f"分镜生成 shotId 不匹配: 缺失={missing}, 多余={extra}")
        shots.sort(key=lambda x: int(x["shotId"]))
        return shots

    async def _call_storyboard_llm_stream(
        self,
        chapter_data: dict,
        novel_text: str,
        tracker: Optional[TaskProgressTracker],
        chapter_title: str,
        chapter_idx: int,
        total: int,
    ) -> List[dict]:
        """章节分镜的流式 LLM 调用：增量文本实时推送到任务 stream_output。

        多章并行调用时各章用 chapter_idx 作为 stream_key，前端按 key 分组显示。
        """
        llm = LLMAdapter(
            api_key=settings.LLM_API_KEY,
            api_base=settings.LLM_API_BASE,
            model=settings.LLM_MODEL or "gpt-4o",
        )
        system_prompt = await get_prompt("storyboard_generation")
        user_content = ""
        if novel_text:
            user_content = f"小说原始完整文本：\n{novel_text}\n\n"
        user_content += json.dumps(chapter_data, ensure_ascii=False)
        messages = [
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="user", content=user_content),
        ]
        if tracker:
            await tracker.push_stream(
                stream_key=chapter_idx,
                stream_header=f"第 {chapter_idx + 1}/{total} 章：{chapter_title}",
            )
        parts: list[str] = []
        async for delta in llm.chat_stream(messages=messages):
            parts.append(delta)
            if tracker:
                await tracker.push_stream(delta, stream_key=chapter_idx)
        if tracker:
            await tracker.flush_stream()

        parsed = parse_llm_json("".join(parts))
        shots = parsed.get("shots", [])
        original_ids = {s["shotId"] for s in chapter_data["shots"]}
        returned_ids = {s["shotId"] for s in shots}
        if original_ids != returned_ids:
            missing = original_ids - returned_ids
            extra = returned_ids - original_ids
            raise ValueError(f"分镜生成 shotId 不匹配: 缺失={missing}, 多余={extra}")
        shots.sort(key=lambda x: int(x["shotId"]))
        return shots

    async def generate_storyboard(self, novel_id: UUID, tracker: Optional[TaskProgressTracker] = None) -> dict:
        """T3 D42: Short transaction pattern for AI generation.

        增量补生成：对比脚本章节与已有分镜章节，只对缺失章节调用 AI。
        """
        if tracker:
            await tracker.set_running("开始生成各章节分镜...")

        # Step 1: Short read — get script data as input
        async with async_session_factory() as read_session:
            novel = await read_session.get(Novel, novel_id)
            if novel is None:
                raise ValueError("小说不存在")
            novel_text = novel.raw_text or novel.cleaned_text or ""

            MAX_TEXT_CHARS = 50000
            if len(novel_text) > MAX_TEXT_CHARS:
                logger.warning(f"小说原始文本长度 {len(novel_text)} 超过 {MAX_TEXT_CHARS} 字符，附加到提示词时将被截断。")
                novel_text = novel_text[:MAX_TEXT_CHARS]

            script_chapters = await self._get_script_chapters_session(read_session, novel_id)
            if not script_chapters:
                raise ValueError("请先生成脚本")

            chapter_ids = [ch.id for ch in script_chapters]
            all_shots_result = await read_session.execute(
                select(ScriptShot)
                .where(ScriptShot.chapter_id.in_(chapter_ids))
                .order_by(ScriptShot.chapter_id, ScriptShot.sort_order)
            )
            shots_by_chapter = {}
            for s in all_shots_result.scalars().all():
                shots_by_chapter.setdefault(s.chapter_id, []).append(s)

            chapters_input = []
            for ch in script_chapters:
                shots_data = [
                    {"shotId": s.shot_id, "content": s.content}
                    for s in shots_by_chapter.get(ch.id, [])
                ]
                chapters_input.append({
                    "chapterTitle": ch.title,
                    "shots": shots_data,
                    "_sort_order": ch.sort_order,
                })
            source_version = str(script_chapters[0].source_version) if script_chapters and script_chapters[0].source_version else None

        # Step 2: Filter out chapters that already have storyboard (incremental)
        async with async_session_factory() as check_session:
            existing = await self._get_storyboard_chapters_session(check_session, novel_id)
            existing_titles = {ch.title for ch in existing}
            pending_input = [ch for ch in chapters_input if ch["chapterTitle"] not in existing_titles]

        if not pending_input:
            async with async_session_factory() as result_session:
                result_data = await self._build_storyboard_response_session(result_session, novel_id)
            if tracker:
                await tracker.complete(result_data, "所有章节分镜已存在，跳过生成")
            return result_data

        skipped = len(chapters_input) - len(pending_input)
        if skipped > 0 and tracker:
            await tracker.update_progress(10, f"已有 {skipped} 章分镜，将只生成剩余 {len(pending_input)} 章")

        try:
            # Step 3: AI call — 多章并行流式（各章 stream_key 区分，前端分组显示）
            tasks = []
            for idx, ch in enumerate(pending_input):
                llm_input = {"chapterTitle": ch["chapterTitle"], "shots": ch["shots"]}
                tasks.append(self._call_storyboard_llm_stream(
                    llm_input, novel_text, tracker,
                    ch["chapterTitle"], idx, len(pending_input),
                ))
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Step 4: Short write — save results (M1: commit once after loop, H3: batch inserts)
            async with async_session_factory() as write_session:
                total_chapters = len(pending_input)
                failed_chapters = []
                valid_chapters = []
                for idx, (ch_data, shots) in enumerate(zip(pending_input, results)):
                    if isinstance(shots, Exception):
                        logger.error(f"章节 {ch_data['chapterTitle']} 分镜生成失败: {shots}")
                        failed_chapters.append(ch_data["chapterTitle"])
                        continue
                    chapter = StoryboardChapter(
                        novel_id=novel_id,
                        title=ch_data["chapterTitle"],
                        sort_order=ch_data["_sort_order"],
                        source_version=source_version,
                        sync_status="fresh",
                    )
                    write_session.add(chapter)
                    valid_chapters.append((chapter, ch_data, shots, idx))

                    if tracker:
                        progress_pct = int((idx + 1) / total_chapters * 70) + 20
                        await tracker.update_progress(progress_pct, f"章节 {ch_data['chapterTitle']} 分镜完成")

                await write_session.flush()

                all_shots = []
                for chapter, ch_data, shots, idx in valid_chapters:
                    for shot_idx, shot in enumerate(shots):
                        all_shots.append(StoryboardShot(
                            chapter_id=chapter.id,
                            shot_id=shot.get("shotId", str(shot_idx + 1).zfill(2)),
                            storyboard_details=shot.get("storyboardDetails", ""),
                            sort_order=shot_idx,
                            source_version=source_version,
                            sync_status="fresh",
                        ))
                write_session.add_all(all_shots)
                await write_session.commit()

                if failed_chapters:
                    logger.warning(f"以下章节分镜生成失败已跳过: {failed_chapters}")

            if tracker:
                await tracker.update_progress(90, "保存分镜数据完成")

            async with async_session_factory() as result_session:
                result_data = await self._build_storyboard_response_session(result_session, novel_id)
            if tracker:
                msg = "分镜生成完成"
                if failed_chapters:
                    msg += f"，失败 {len(failed_chapters)} 章: {', '.join(failed_chapters)}"
                if skipped > 0:
                    msg += f"（跳过已存在 {skipped} 章）"
                await tracker.complete(result_data, msg)
            return result_data

        except Exception as e:
            if tracker:
                await tracker.fail(str(e))
            logger.error(f"分镜生成失败: {e}", exc_info=True)
            raise

    async def get_storyboard(self, novel_id: UUID) -> dict:
        return await self._build_storyboard_response(self.session, novel_id)

    async def save_storyboard(self, novel_id: UUID, chapters_data: list) -> dict:
        novel = await self.novel_repo.get(novel_id)
        if novel is None:
            raise ValueError("小说不存在")

        old_chapter_ids = [ch.id for ch in await self._get_storyboard_chapters(self.session, novel_id)]
        if old_chapter_ids:
            await self.session.execute(sa_delete(StoryboardShot).where(StoryboardShot.chapter_id.in_(old_chapter_ids)))
            await self.session.execute(sa_delete(StoryboardChapter).where(StoryboardChapter.id.in_(old_chapter_ids)))
        await self.session.flush()

        new_chapters = []
        for idx, ch_data in enumerate(chapters_data):
            new_chapters.append(StoryboardChapter(
                novel_id=novel_id,
                title=ch_data.get("chapterTitle", ""),
                sort_order=idx,
            ))
        self.session.add_all(new_chapters)
        await self.session.flush()

        all_shots = []
        for chapter, ch_data in zip(new_chapters, chapters_data):
            shots = ch_data.get("shots", [])
            for shot_idx, shot in enumerate(shots):
                all_shots.append(StoryboardShot(
                    chapter_id=chapter.id,
                    shot_id=shot.get("shotId", str(shot_idx + 1).zfill(2)),
                    storyboard_details=shot.get("storyboardDetails", ""),
                    sort_order=shot_idx,
                ))
        self.session.add_all(all_shots)
        await self.session.flush()
        return await self._build_storyboard_response(self.session, novel_id)

    async def _get_script_chapters_session(self, session: AsyncSession, novel_id: UUID):
        result = await session.execute(
            select(ScriptChapter).where(ScriptChapter.novel_id == novel_id).order_by(ScriptChapter.sort_order)
        )
        return list(result.scalars().all())

    async def _get_storyboard_chapters(self, session: AsyncSession, novel_id: UUID):
        return await self._get_storyboard_chapters_session(session, novel_id)

    async def _get_storyboard_chapters_session(self, session: AsyncSession, novel_id: UUID):
        result = await session.execute(
            select(StoryboardChapter).where(StoryboardChapter.novel_id == novel_id).order_by(StoryboardChapter.sort_order)
        )
        return list(result.scalars().all())

    async def _build_storyboard_response(self, session: AsyncSession, novel_id: UUID) -> dict:
        return await self._build_storyboard_response_session(session, novel_id)

    async def _build_storyboard_response_session(self, session: AsyncSession, novel_id: UUID) -> dict:
        result = await session.execute(
            select(StoryboardChapter)
            .options(selectinload(StoryboardChapter.shots))
            .where(StoryboardChapter.novel_id == novel_id)
            .order_by(StoryboardChapter.sort_order)
        )
        chapters = result.scalars().all()
        return {"chapters": [
            {
                "id": str(ch.id),
                "title": ch.title,
                "sort_order": ch.sort_order,
                "shots": [
                    {"id": str(s.id), "shot_id": s.shot_id, "storyboard_details": s.storyboard_details, "sort_order": s.sort_order}
                    for s in ch.shots
                ],
            }
            for ch in chapters
        ]}
