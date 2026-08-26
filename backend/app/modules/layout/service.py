"""Layout service - AI 排版 service (extracted from novel_service.py).

Implements T3 D42: AI calls use short transaction pattern (read → close → AI → new session → write).
Implements T9 problem 4: LayoutChapter/LayoutPage carry source_version + sync_status.
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
from app.models.novel import ScriptChapter, ScriptShot
from app.models.storyboard import StoryboardChapter, StoryboardShot
from app.models.layout import LayoutChapter, LayoutPage, LayoutShot, ImagePrompt, GeneratedImage, ReferenceMatch
from app.repositories import layout_repo
from app.repositories.novel_repo import NovelRepository
from app.infra.prompt_loader import get_prompt

logger = logging.getLogger(__name__)


class LayoutService:
    """排版生成服务."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.novel_repo = NovelRepository(session)

    async def _call_layout_llm(self, chapter_data: dict) -> List[dict]:
        """调用LLM为单个章节生成排版.

        T2: 移除业务层重试循环（adapter 层已有 3 次指数退避重试）。
        校验失败直接抛异常，由 gather(return_exceptions=True) 捕获。

        出错时把 LLM 原始返回内容写入 backend/logs/llm_debug/ 下的 txt 文件，
        便于排查 shot 不匹配 / JSON 解析失败 / pageId 格式异常等问题。
        """
        llm = LLMAdapter(
            api_key=settings.LLM_API_KEY,
            api_base=settings.LLM_API_BASE,
            model=settings.LLM_MODEL or "gpt-4o",
        )

        system_prompt = await get_prompt("layout_generation")
        messages = [
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="user", content=json.dumps(chapter_data, ensure_ascii=False)),
        ]
        result = None
        try:
            result = await llm.chat(messages=messages)
            parsed = parse_llm_json(result.content)
            if isinstance(parsed, dict) and "pages" in parsed:
                pages = parsed["pages"]
            elif isinstance(parsed, list):
                pages = parsed
            else:
                pages = []
            original_shots = {(s["shotId"], s["content"]) for s in chapter_data.get("shots", [])}
            returned_shots = set()
            for page in pages:
                for s in page.get("shots", []):
                    # 提示词约定 INSERT 格的 shotId 形如 "05_INSERT"（原 shotId + _INSERT 后缀），
                    # 不能用 startswith("INSERT") —— 那只会匹配 "INSERT_05" 这种前缀格式，
                    # 反而把真正的 "05_INSERT" 当成普通镜头加入 returned_shots，导致不匹配报错。
                    if not s["shotId"].endswith("_INSERT"):
                        returned_shots.add((s["shotId"], s["content"]))
            if original_shots and original_shots != returned_shots:
                missing = original_shots - returned_shots
                extra = returned_shots - original_shots
                raise ValueError(
                    f"排版生成 shot 不匹配: 缺失={missing}, 多余={extra}"
                )
            pages.sort(key=lambda x: int(x["pageId"].replace("P", "")))
            return pages
        except Exception as e:
            self._dump_layout_llm_failure(chapter_data, result, e)
            raise

    async def _call_layout_llm_stream(
        self,
        chapter_data: dict,
        tracker: Optional[TaskProgressTracker],
        chapter_title: str,
        chapter_idx: int,
        total: int,
    ) -> List[dict]:
        """章节排版的流式 LLM 调用：增量文本实时推送到任务 stream_output。

        多章并行调用时各章用 chapter_idx 作为 stream_key，前端按 key 分组显示。
        校验/失败 dump 逻辑与 _call_layout_llm 保持一致。
        """
        llm = LLMAdapter(
            api_key=settings.LLM_API_KEY,
            api_base=settings.LLM_API_BASE,
            model=settings.LLM_MODEL or "gpt-4o",
        )

        system_prompt = await get_prompt("layout_generation")
        messages = [
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="user", content=json.dumps(chapter_data, ensure_ascii=False)),
        ]
        if tracker:
            await tracker.push_stream(
                stream_key=chapter_idx,
                stream_header=f"第 {chapter_idx + 1}/{total} 章：{chapter_title}",
            )
        parts: list[str] = []
        result_content = ""
        try:
            async for delta in llm.chat_stream(messages=messages):
                parts.append(delta)
                if tracker:
                    await tracker.push_stream(delta, stream_key=chapter_idx)
            if tracker:
                await tracker.flush_stream()
            result_content = "".join(parts)
            parsed = parse_llm_json(result_content)
            if isinstance(parsed, dict) and "pages" in parsed:
                pages = parsed["pages"]
            elif isinstance(parsed, list):
                pages = parsed
            else:
                pages = []
            original_shots = {(s["shotId"], s["content"]) for s in chapter_data.get("shots", [])}
            returned_shots = set()
            for page in pages:
                for s in page.get("shots", []):
                    if not s["shotId"].endswith("_INSERT"):
                        returned_shots.add((s["shotId"], s["content"]))
            if original_shots and original_shots != returned_shots:
                missing = original_shots - returned_shots
                extra = returned_shots - original_shots
                raise ValueError(
                    f"排版生成 shot 不匹配: 缺失={missing}, 多余={extra}"
                )
            pages.sort(key=lambda x: int(x["pageId"].replace("P", "")))
            return pages
        except Exception as e:
            self._dump_layout_llm_failure(chapter_data, result_content, e)
            raise

    def _dump_layout_llm_failure(
        self, chapter_data: dict, result, error: Exception
    ) -> None:
        """排版 LLM 调用失败时，把原始返回内容写入 txt 文件，便于排查.

        文件路径：backend/logs/llm_debug/layout_{时间}_{章节标题}.txt
        """
        try:
            import re
            from datetime import datetime
            from pathlib import Path

            log_dir = Path(__file__).resolve().parents[3] / "logs" / "llm_debug"
            log_dir.mkdir(parents=True, exist_ok=True)

            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            title = chapter_data.get("chapterTitle", "unknown") or "unknown"
            safe_title = re.sub(r'[\\/:*?"<>|]', "_", title)[:50]
            filepath = log_dir / f"layout_{ts}_{safe_title}.txt"

            lines = [
                "=== 排版生成失败 ===",
                f"时间: {datetime.now().isoformat()}",
                f"章节标题: {title}",
                f"错误类型: {type(error).__name__}",
                f"错误信息: {error}",
                "",
                "=== 输入 chapter_data ===",
                json.dumps(chapter_data, ensure_ascii=False, indent=2),
                "",
                "=== LLM 原始返回内容 ===",
            ]
            if isinstance(result, str):
                lines.append(result)
            elif result is not None and hasattr(result, "content"):
                lines.append(result.content)
            else:
                lines.append("(LLM 调用本身失败，没有返回内容)")

            filepath.write_text("\n".join(lines), encoding="utf-8")
            logger.info(f"排版 LLM 失败原始数据已写入: {filepath}")
        except Exception as dump_err:
            logger.warning(f"写入 LLM 失败调试文件时出错: {dump_err}")

    async def generate_layout(self, novel_id: UUID, tracker: Optional[TaskProgressTracker] = None) -> dict:
        """调用LLM为缺少排版数据的章节生成排版.

        行为变更（2026-07-26）：
          - 不再因为已有部分排版数据就跳过全部生成。
          - 对比分镜章节与已有排版章节，只对缺失排版数据的章节调用 AI 生成。
          - 已有排版数据的章节保持不变。

        T3 D42: Uses short transaction pattern:
        1. Short read: get storyboard + script data
        2. Short read: compare storyboard vs existing layout → find missing chapters
        3. AI call (no session held) — only for missing chapters
        4. Short write: save new chapters (keep existing ones)
        """
        if tracker:
            await tracker.set_running("开始生成各章节排版...")

        # Step 1: Short read — get storyboard + script data
        async with async_session_factory() as read_session:
            storyboard_chapters = await self._get_storyboard_chapters_session(read_session, novel_id)
            if not storyboard_chapters:
                raise ValueError("请先生成分镜")

            # 问题 3: shot_id 在每章可能重复（如 "01"、"02"），全局 map 会串章。
            # 改用 (sort_order, shot_id) 组合键，避免跨章覆盖。
            content_map = {}  # {(chapter_sort_order, shot_id): content}
            script_chs = await self._get_script_chapters_session(read_session, novel_id)
            script_chapter_ids = [sc.id for sc in script_chs]
            if script_chapter_ids:
                script_shots_r = await read_session.execute(
                    select(ScriptShot).where(ScriptShot.chapter_id.in_(script_chapter_ids))
                )
                sc_map = {sc.id: sc for sc in script_chs}
                for shot in script_shots_r.scalars().all():
                    sc = sc_map.get(shot.chapter_id)
                    if sc:
                        content_map[(sc.sort_order, shot.shot_id)] = shot.content

            sb_chapter_ids = [ch.id for ch in storyboard_chapters]
            all_sb_shots_r = await read_session.execute(
                select(StoryboardShot)
                .where(StoryboardShot.chapter_id.in_(sb_chapter_ids))
                .order_by(StoryboardShot.chapter_id, StoryboardShot.sort_order)
            )
            sb_shots_by_chapter = {}
            for s in all_sb_shots_r.scalars().all():
                sb_shots_by_chapter.setdefault(s.chapter_id, []).append(s)

            chapters_input = []
            for ch in storyboard_chapters:
                shots_data = []
                for s in sb_shots_by_chapter.get(ch.id, []):
                    shots_data.append({
                        "shotId": s.shot_id,
                        "content": content_map.get((ch.sort_order, s.shot_id), ""),
                        "storyboardDetails": s.storyboard_details,
                    })
                chapters_input.append({
                    "chapterTitle": ch.title,
                    "shots": shots_data,
                    "_sort_order": ch.sort_order,
                })
            source_version = (
                str(storyboard_chapters[0].source_version)
                if storyboard_chapters and storyboard_chapters[0].source_version
                else None
            )

        # Step 2: Compare storyboard vs existing layout — find missing chapters
        async with async_session_factory() as check_session:
            existing_layout = await self._get_layout_chapters_session(check_session, novel_id)
            existing_sort_orders = {ch.sort_order for ch in existing_layout}

            # 找出缺少排版的分镜章节（按 sort_order 匹配）
            missing_chapters = [c for c in chapters_input if c["_sort_order"] not in existing_sort_orders]

            if not missing_chapters:
                # 所有章节已有排版，跳过生成
                result_data = await self._build_layout_response_session(check_session, novel_id)
                if tracker:
                    await tracker.complete(result_data, "所有章节已有排版，跳过生成")
                return result_data

            if tracker:
                await tracker.set_running(
                    f"共 {len(chapters_input)} 个章节，其中 {len(missing_chapters)} 个缺少排版，开始生成..."
                )

        skipped_count = len(chapters_input) - len(missing_chapters)

        try:
            # Step 3: AI call — 多章并行流式（各章 stream_key 区分，前端分组显示）
            tasks = []
            for idx, ch in enumerate(missing_chapters):
                tasks.append(self._call_layout_llm_stream(
                    {"chapterTitle": ch["chapterTitle"], "shots": ch["shots"]},
                    tracker,
                    ch["chapterTitle"], idx, len(missing_chapters),
                ))
            # T2: return_exceptions 防止单章失败导致全批中断
            results = await asyncio.gather(*tasks, return_exceptions=True)

            failed_layout_chapters = []
            valid_results = []
            for idx, pages in enumerate(results):
                if isinstance(pages, Exception):
                    logger.error(f"章节 {missing_chapters[idx]['chapterTitle']} 排版生成失败: {pages}")
                    failed_layout_chapters.append(missing_chapters[idx]["chapterTitle"])
                    continue
                valid_results.append((idx, pages))
            if failed_layout_chapters:
                logger.warning(f"以下章节排版生成失败已跳过: {failed_layout_chapters}")

            if not valid_results:
                # 所有要生成的章节都失败了，返回已有数据
                failed_titles = [c["chapterTitle"] for c in missing_chapters]
                err_msg = (
                    f"排版生成失败：以下 {len(failed_titles)} 个章节全部 AI 调用失败"
                    f"（{', '.join(failed_titles)}），请检查 LLM 配置或稍后重试"
                )
                logger.error(err_msg)
                raise ValueError(err_msg)

            # Step 4: Short write — save new chapters only, keep existing ones
            async with async_session_factory() as write_session:
                content_hash = hashlib.md5(
                    json.dumps([c["chapterTitle"] for c in missing_chapters], ensure_ascii=False).encode()
                ).hexdigest()
                new_chapters = []
                total_missing = len(missing_chapters)
                for save_idx, (ch_idx, pages) in enumerate(valid_results):
                    ch_data = missing_chapters[ch_idx]
                    chapter = LayoutChapter(
                        novel_id=novel_id,
                        title=ch_data["chapterTitle"],
                        sort_order=ch_data["_sort_order"],
                        source_version=source_version,
                        content_hash=content_hash,
                        sync_status="fresh",
                    )
                    write_session.add(chapter)
                    # 新 page 先用临时 page_label（后续全局重新编号）
                    for pi, page in enumerate(pages):
                        page["_temp_label"] = f"TMP{pi}"
                    new_chapters.append((chapter, ch_data, pages, save_idx))

                    if tracker:
                        progress_pct = int((save_idx + 1) / total_missing * 70) + 20
                        ch_title = ch_data["chapterTitle"]
                        await tracker.update_progress(progress_pct, f"章节 {ch_title} 排版完成")

                await write_session.flush()

                all_pages = []
                page_shots = []  # (page, pages_list_index) 暂存
                for chapter, ch_data, pages, save_idx in new_chapters:
                    for page_idx, page in enumerate(pages):
                        all_pages.append(LayoutPage(
                            chapter_id=chapter.id,
                            page_label=page.get("_temp_label", f"TMP{page_idx}"),
                            layout_type=page.get("layoutType", ""),
                            page_purpose=page.get("pagePurpose", ""),
                            visual_focus=page.get("visualFocus", ""),
                            sort_order=page_idx,
                            source_version=source_version,
                            sync_status="fresh",
                        ))
                        page_shots.append((page, len(all_pages) - 1))
                write_session.add_all(all_pages)
                await write_session.flush()

                # 保存 LayoutShot
                all_layout_shots = []
                for page_data, p_idx in page_shots:
                    lp = all_pages[p_idx]
                    for si, shot in enumerate(page_data.get("shots", [])):
                        all_layout_shots.append(LayoutShot(
                            page_id=lp.id,
                            shot_id=shot.get("shotId", ""),
                            sort_order=si,
                        ))
                if all_layout_shots:
                    write_session.add_all(all_layout_shots)
                await write_session.commit()

            # Step 5: 全局重新编号所有页面（按 chapter.sort_order + page.sort_order）
            async with async_session_factory() as renumber_session:
                all_pages_r = await renumber_session.execute(
                    select(LayoutPage)
                    .join(LayoutChapter, LayoutPage.chapter_id == LayoutChapter.id)
                    .where(LayoutChapter.novel_id == novel_id)
                    .order_by(LayoutChapter.sort_order, LayoutPage.sort_order)
                )
                page_counter = 1
                for lp in all_pages_r.scalars().all():
                    lp.page_label = f"P{page_counter}"
                    page_counter += 1
                await renumber_session.commit()
                logger.info(f"排版页面已全局重新编号：共 {page_counter - 1} 页")

            if tracker:
                await tracker.update_progress(90, "保存排版数据完成")

            async with async_session_factory() as result_session:
                result_data = await self._build_layout_response_session(result_session, novel_id)
            if tracker:
                complete_msg = "排版生成完成"
                if failed_layout_chapters:
                    complete_msg += f"，{len(failed_layout_chapters)} 章失败: {', '.join(failed_layout_chapters)}"
                if skipped_count > 0:
                    complete_msg += f"（跳过已存在 {skipped_count} 章）"
                await tracker.complete(result_data, complete_msg)
            return result_data

        except Exception as e:
            if tracker:
                await tracker.fail(str(e))
            logger.error(f"排版生成失败: {e}", exc_info=True)
            raise

    async def get_layout(self, novel_id: UUID) -> dict:
        return await self._build_layout_response(self.session, novel_id)

    async def save_layout(self, novel_id: UUID, chapters_data: list) -> dict:
        novel = await self.novel_repo.get(novel_id)
        if novel is None:
            raise ValueError("小说不存在")

        old_chapters = await self._get_layout_chapters(self.session, novel_id)
        old_chapter_ids = [ch.id for ch in old_chapters]

        # 备份旧的下游数据（按 page_label 映射）
        old_prompt_map = {}   # page_label → full_prompt
        old_image_map = {}    # page_label → image_url
        old_ref_map = {}      # page_label → ref_ids
        if old_chapter_ids:
            old_pages_r = await self.session.execute(
                select(LayoutPage).where(LayoutPage.chapter_id.in_(old_chapter_ids))
            )
            old_page_ids = []
            old_label_map = {}  # page_id → page_label
            for p in old_pages_r.scalars().all():
                old_page_ids.append(p.id)
                old_label_map[p.id] = p.page_label

            if old_page_ids:
                # ImagePrompt
                ip_r = await self.session.execute(
                    select(ImagePrompt).where(ImagePrompt.page_id.in_(old_page_ids))
                )
                for ip in ip_r.scalars().all():
                    lbl = old_label_map.get(ip.page_id)
                    if lbl:
                        old_prompt_map[lbl] = ip.full_prompt

                # GeneratedImage
                gi_r = await self.session.execute(
                    select(GeneratedImage).where(GeneratedImage.page_id.in_(old_page_ids))
                )
                for gi in gi_r.scalars().all():
                    lbl = old_label_map.get(gi.page_id)
                    if lbl and gi.is_selected == "selected":
                        old_image_map[lbl] = gi.image_url

                # ReferenceMatch
                rm_r = await self.session.execute(
                    select(ReferenceMatch).where(ReferenceMatch.page_id.in_(old_page_ids))
                )
                for rm in rm_r.scalars().all():
                    lbl = old_label_map.get(rm.page_id)
                    if lbl:
                        old_ref_map[lbl] = rm.ref_ids

            # 删旧数据
            page_ids_subq = select(LayoutPage.id).where(LayoutPage.chapter_id.in_(old_chapter_ids))
            await self.session.execute(sa_delete(ImagePrompt).where(ImagePrompt.page_id.in_(page_ids_subq)))
            await self.session.execute(sa_delete(ReferenceMatch).where(ReferenceMatch.page_id.in_(page_ids_subq)))
            await self.session.execute(sa_delete(GeneratedImage).where(GeneratedImage.page_id.in_(page_ids_subq)))
            await self.session.execute(sa_delete(LayoutShot).where(LayoutShot.page_id.in_(page_ids_subq)))
            await self.session.execute(
                sa_delete(LayoutPage).where(LayoutPage.chapter_id.in_(old_chapter_ids))
            )
            await self.session.execute(
                sa_delete(LayoutChapter).where(LayoutChapter.id.in_(old_chapter_ids))
            )
        await self.session.flush()

        new_chapters = []
        for idx, ch_data in enumerate(chapters_data):
            new_chapters.append(LayoutChapter(
                novel_id=novel_id,
                title=ch_data.get("chapterTitle", ""),
                sort_order=idx,
            ))
        self.session.add_all(new_chapters)
        await self.session.flush()

        all_pages = []
        page_shots = []
        page_downstream = []  # (page, page_index) for downstream data
        for chapter, ch_data in zip(new_chapters, chapters_data):
            pages = ch_data.get("pages", [])
            for page_idx, page in enumerate(pages):
                all_pages.append(LayoutPage(
                    chapter_id=chapter.id,
                    page_label=page.get("pageId", f"P{page_idx + 1}"),
                    layout_type=page.get("layoutType", ""),
                    page_purpose=page.get("pagePurpose", ""),
                    visual_focus=page.get("visualFocus", ""),
                    sort_order=page_idx,
                ))
                page_shots.append((page, len(all_pages) - 1))
                page_downstream.append((page, len(all_pages) - 1))
        self.session.add_all(all_pages)
        await self.session.flush()

        # 保存 LayoutShot
        all_layout_shots = []
        for page_data, p_idx in page_shots:
            lp = all_pages[p_idx]
            for si, shot in enumerate(page_data.get("shots", [])):
                all_layout_shots.append(LayoutShot(
                    page_id=lp.id,
                    shot_id=shot.get("shotId", ""),
                    sort_order=si,
                ))
        if all_layout_shots:
            self.session.add_all(all_layout_shots)
        await self.session.flush()

        # 保存下游数据（ImagePrompt / GeneratedImage / ReferenceMatch）
        # 优先使用前端传入的值，前端没传或为空则从备份恢复
        for page_data, p_idx in page_downstream:
            lp = all_pages[p_idx]
            page_label = page_data.get("pageId", "")

            prompt_text = page_data.get("imagePrompt") or old_prompt_map.get(page_label) or ""
            if prompt_text:
                self.session.add(ImagePrompt(
                    page_id=lp.id,
                    full_prompt=prompt_text,
                ))

            img_url = page_data.get("imageUrl") or old_image_map.get(page_label) or ""
            if img_url:
                self.session.add(GeneratedImage(
                    page_id=lp.id,
                    image_url=img_url,
                    is_selected="selected",
                ))

            ref_ids = page_data.get("referenceIds") or old_ref_map.get(page_label) or []
            if ref_ids and isinstance(ref_ids, list) and len(ref_ids) > 0:
                self.session.add(ReferenceMatch(
                    page_id=lp.id,
                    ref_ids=ref_ids,
                ))
        await self.session.flush()

        return await self._build_layout_response(self.session, novel_id)

    async def delete_layout_chapter(self, novel_id: UUID, chapter_id: UUID) -> dict:
        """删除指定章节的排版及下游数据（生图提示词、参考图、漫画页图片）."""
        # 校验章节属于该小说
        result = await self.session.execute(
            select(LayoutChapter).where(
                LayoutChapter.id == chapter_id,
                LayoutChapter.novel_id == novel_id,
            )
        )
        chapter = result.scalar_one_or_none()
        if not chapter:
            raise ValueError("排版章节不存在")

        # 先删下游子表（外键依赖 LayoutPage.id），再删 LayoutPage 和 LayoutChapter
        page_ids_subq = select(LayoutPage.id).where(LayoutPage.chapter_id == chapter_id)
        await self.session.execute(
            sa_delete(GeneratedImage).where(GeneratedImage.page_id.in_(page_ids_subq))
        )
        await self.session.execute(
            sa_delete(ReferenceMatch).where(ReferenceMatch.page_id.in_(page_ids_subq))
        )
        await self.session.execute(
            sa_delete(ImagePrompt).where(ImagePrompt.page_id.in_(page_ids_subq))
        )
        await self.session.execute(
            sa_delete(LayoutShot).where(LayoutShot.page_id.in_(page_ids_subq))
        )
        await self.session.execute(
            sa_delete(LayoutPage).where(LayoutPage.chapter_id == chapter_id)
        )
        await self.session.execute(
            sa_delete(LayoutChapter).where(LayoutChapter.id == chapter_id)
        )
        await self.session.commit()
        return {"success": True, "deleted_chapter_id": str(chapter_id)}

    async def _get_script_chapters_session(self, session: AsyncSession, novel_id: UUID):
        result = await session.execute(
            select(ScriptChapter).where(ScriptChapter.novel_id == novel_id).order_by(ScriptChapter.sort_order)
        )
        return list(result.scalars().all())

    async def _get_storyboard_chapters_session(self, session: AsyncSession, novel_id: UUID):
        result = await session.execute(
            select(StoryboardChapter).where(StoryboardChapter.novel_id == novel_id).order_by(StoryboardChapter.sort_order)
        )
        return list(result.scalars().all())

    async def _get_layout_chapters(self, session: AsyncSession, novel_id: UUID):
        return await self._get_layout_chapters_session(session, novel_id)

    async def _get_layout_chapters_session(self, session: AsyncSession, novel_id: UUID):
        return await layout_repo.get_layout_chapters_session(session, novel_id)

    async def _build_layout_response(self, session: AsyncSession, novel_id: UUID) -> dict:
        return await self._build_layout_response_session(session, novel_id)

    async def _build_layout_response_session(self, session: AsyncSession, novel_id: UUID) -> dict:
        return await layout_repo.build_layout_response_session(session, novel_id)
