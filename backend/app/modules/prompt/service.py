"""Prompt service - 生图提示词 + 参考图匹配 service (extracted from novel_service.py).

Implements T3 D42: AI calls use short transaction pattern (read → close → AI → new session → write).
Implements T9 problem 4: LayoutPage carries source_version + sync_status on prompt regeneration.
"""
import asyncio
import json
import logging
import re
from typing import Optional, Dict
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import async_session_factory
from app.core.llm_utils import parse_llm_json
from app.infra.adapters.llm_adapter import LLMAdapter
from app.infra.adapters.base_llm import ChatMessage
from app.infra.task_progress import TaskProgressTracker
from app.models.layout import LayoutChapter, LayoutPage, ImagePrompt, ReferenceMatch
from app.models.novel import ScriptChapter, ScriptShot
from app.models.storyboard import StoryboardChapter, StoryboardShot
from app.models.world import WorldBuilding, SceneAsset, Prop, Building, Outfit
from app.models.character import Character, CharacterReferenceImage, CharacterState
from app.repositories.novel_repo import NovelRepository
from app.infra.prompt_loader import get_prompt

logger = logging.getLogger(__name__)


class PromptService:
    """生图提示词生成 + 参考图匹配服务."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.novel_repo = NovelRepository(session)

    def _compress_ref_description(self, text: str, max_len: int = 300) -> str:
        """压缩参考图描述：仅去除【画幅要求】段落，其余保留"""
        if not text:
            return ""
        # 只去掉【画幅要求】...到【场景描述】或末尾之间的内容
        cleaned = re.sub(r'[【\[]画幅要求[】\]].*?([【\[]场景描述[】\]]|$)', '', text, flags=re.DOTALL)
        cleaned = cleaned.strip()[:max_len]
        return cleaned

    # =================================================================
    # generate_image_prompts (T3 D42: short transaction pattern)
    # =================================================================

    async def _call_image_prompt_llm(self, pages: list, system_prompt: str) -> dict:
        """调用LLM为一个章节的所有页面批量生成生图提示词.

        发送格式：[{pageId, layoutType, pagePurpose, visualFocus, shots: [{shotId, content, storyboardDetails}]}]
        返回 dict: { page_label -> image_prompt }
        """
        llm = LLMAdapter(
            api_key=settings.LLM_API_KEY,
            api_base=settings.LLM_API_BASE,
            model=settings.LLM_MODEL,
        )

        messages = [
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="user", content=json.dumps(pages, ensure_ascii=False)),
        ]
        result = await llm.chat(messages=messages)
        parsed = parse_llm_json(result.content)
        shots = parsed.get("shots", [])

        prompt_results = {}
        for item in shots:
            page_id = item.get("pageId", "")
            image_prompt = item.get("imagePrompt", "")
            if page_id and image_prompt:
                prompt_results[page_id] = image_prompt
        return prompt_results

    async def generate_image_prompts(self, novel_id: UUID, tracker: Optional[TaskProgressTracker] = None) -> dict:
        """调用LLM为所有排版页面生成生图提示词.

        T3 D42: Uses short transaction pattern:
        1. Short read: get all layout pages
        2. AI calls per chapter (no session held)
        3. Short write: batch update image_prompt
        """
        if tracker:
            await tracker.set_running("开始生成各页面提示词...")

        try:
            system_prompt = await get_prompt("ai_image_prompt_generation")

            # Step 1: Short read — get all layout pages + shot content + storyboard details
            async with async_session_factory() as read_session:
                layout_chapters = await self._get_layout_chapters_session(read_session, novel_id)
                if not layout_chapters:
                    raise ValueError("请先生成排版")

                # 构建 layout chapter 映射
                lc_sort_map = {lc.id: lc.sort_order for lc in layout_chapters}
                lc_title_map = {lc.id: lc.title for lc in layout_chapters}

                # 查询 ScriptShot.content: (chapter_sort_order, shot_id) → content
                content_map = {}
                script_chs = await self._get_script_chapters_session(read_session, novel_id)
                sc_sort_map = {sc.id: sc.sort_order for sc in script_chs}
                sc_ids = list(sc_sort_map.keys())
                if sc_ids:
                    ss_r = await read_session.execute(
                        select(ScriptShot).where(ScriptShot.chapter_id.in_(sc_ids))
                    )
                    for ss in ss_r.scalars().all():
                        sort_order = sc_sort_map.get(ss.chapter_id)
                        if sort_order is not None:
                            content_map[(sort_order, ss.shot_id)] = ss.content

                # 查询 StoryboardShot.storyboard_details: (chapter_sort_order, shot_id) → storyboard_details
                sb_detail_map = {}
                storyboard_chs = await self._get_storyboard_chapters_session(read_session, novel_id)
                sbc_sort_map = {sc.id: sc.sort_order for sc in storyboard_chs}
                sbc_ids = list(sbc_sort_map.keys())
                if sbc_ids:
                    sbs_r = await read_session.execute(
                        select(StoryboardShot).where(StoryboardShot.chapter_id.in_(sbc_ids))
                    )
                    for sbs in sbs_r.scalars().all():
                        sort_order = sbc_sort_map.get(sbs.chapter_id)
                        if sort_order is not None:
                            sb_detail_map[(sort_order, sbs.shot_id)] = sbs.storyboard_details

                all_pages_raw = await self._get_all_pages_for_novel_session(read_session, novel_id)
                all_pages = [
                    {
                        "id": p.id,
                        "chapter_id": p.chapter_id,
                        "page_label": p.page_label,
                        "layout_type": p.layout_type,
                        "page_purpose": p.page_purpose,
                        "visual_focus": p.visual_focus,
                        "shots": [
                            {"shotId": s.shot_id, "sortOrder": s.sort_order}
                            for s in p.shots
                        ],
                        "has_prompt": bool(p.image_prompt),
                    }
                    for p in all_pages_raw
                ]

                # 分页限制：只处理前 100 页
                page_limit_suffix = ""
                if settings.PAGE_LIMIT_ENABLED and len(all_pages) > 100:
                    page_limit_suffix = "（前100页模式）"
                    logger.info(f"PAGE_LIMIT_ENABLED=True，只处理前 100 页（共 {len(all_pages)} 页）")
                    all_pages = all_pages[:100]

            if tracker:
                await tracker.update_progress(0, f"开始生成各页面提示词{page_limit_suffix}...")

            if not all_pages:
                async with async_session_factory() as empty_session:
                    return await self._build_layout_response_session(empty_session, novel_id)

            # 按章节分组
            from collections import defaultdict
            pages_by_chapter: Dict[UUID, list] = defaultdict(list)
            for p in all_pages:
                pages_by_chapter[p["chapter_id"]].append(p)

            # 构建每章的页面列表，shots 嵌入完整 content + storyboardDetails
            chapter_pages_list = []  # [{_ch_id, _pages: [{pageId, layoutType, ..., shots: [{shotId, content, storyboardDetails}]}]}]
            for ch_id, pages_in_ch in pages_by_chapter.items():
                sort_order = lc_sort_map.get(ch_id, 0)
                pages_with_shots = []
                for p in pages_in_ch:
                    page_shots = []
                    for s in p["shots"]:
                        sid = s["shotId"]
                        page_shots.append({
                            "shotId": sid,
                            "content": content_map.get((sort_order, sid), ""),
                            "storyboardDetails": sb_detail_map.get((sort_order, sid), ""),
                        })
                    pages_with_shots.append({
                        "pageId": p["page_label"],
                        "layoutType": p["layout_type"],
                        "pagePurpose": p["page_purpose"],
                        "visualFocus": p["visual_focus"],
                        "shots": page_shots,
                    })
                    p["_chapter_idx"] = len(chapter_pages_list)
                chapter_pages_list.append({
                    "_ch_id": ch_id,
                    "_pages": pages_with_shots,
                })

            prompt_results: Dict[str, str] = {}  # page_label -> image_prompt
            total_chapters = len(chapter_pages_list)
            completed_chapters = 0
            tracker_lock = asyncio.Lock()

            # Step 2: AI calls per chapter (no session held)
            async def process_chapter(ch_data: dict) -> None:
                nonlocal completed_chapters
                ch_id = ch_data["_ch_id"]
                pages_in_ch = pages_by_chapter[ch_id]
                pages_to_generate = [p for p in pages_in_ch if not p.get("has_prompt")]
                if not pages_to_generate:
                    async with tracker_lock:
                        completed_chapters += 1
                        if tracker:
                            pct = int(completed_chapters / total_chapters * 90)
                            await tracker.update_progress(pct, f"已生成 {completed_chapters}/{total_chapters} 章提示词")
                    return
                # 只发送需要生成的页面
                target_labels = {p["page_label"] for p in pages_to_generate}
                ch_payload = [pg for pg in ch_data["_pages"] if pg["pageId"] in target_labels]
                chapter_labels = [p["page_label"] for p in pages_to_generate]
                try:
                    results = await self._call_image_prompt_llm(ch_payload, system_prompt)
                    if results:
                        prompt_results.update(results)
                        logger.info(f"章节 {chapter_labels[0]}~{chapter_labels[-1]} 提示词生成成功")
                except Exception as e:
                    logger.error(f"章节 {chapter_labels} 提示词生成失败: {e}")
                finally:
                    async with tracker_lock:
                        completed_chapters += 1
                        if tracker and total_chapters > 0:
                            pct = int(completed_chapters / total_chapters * 90)
                            await tracker.update_progress(
                                pct, f"已生成 {completed_chapters}/{total_chapters} 章提示词"
                            )

            tasks = [process_chapter(cd) for cd in chapter_pages_list]
            await asyncio.gather(*tasks, return_exceptions=True)

            # Step 3: Short write — batch save ImagePrompt records
            if prompt_results:
                async with async_session_factory() as write_session:
                    # 先查询页面ID
                    all_labels = list(prompt_results.keys())
                    pages_r = await write_session.execute(
                        select(LayoutPage.id, LayoutPage.page_label)
                        .where(LayoutPage.page_label.in_(all_labels))
                        .where(LayoutPage.chapter_id.in_(
                            select(LayoutChapter.id).where(LayoutChapter.novel_id == novel_id)
                        ))
                    )
                    page_id_map = {label: pid for pid, label in pages_r.all()}
                    for page_label, prompt_text in prompt_results.items():
                        page_id = page_id_map.get(page_label)
                        if not page_id:
                            continue
                        # 检查是否已有 ImagePrompt 记录
                        existing_r = await write_session.execute(
                            select(ImagePrompt).where(ImagePrompt.page_id == page_id)
                        )
                        existing = existing_r.scalar_one_or_none()
                        if existing:
                            existing.full_prompt = prompt_text
                        else:
                            write_session.add(ImagePrompt(
                                page_id=page_id,
                                full_prompt=prompt_text,
                            ))
                    await write_session.commit()

            if tracker:
                await tracker.update_progress(90, "保存提示词完成")

            async with async_session_factory() as result_session:
                result_data = await self._build_layout_response_session(result_session, novel_id)
            if tracker:
                await tracker.complete(result_data)
            return result_data
        except Exception as e:
            if tracker:
                await tracker.fail(str(e))
            raise

    async def regenerate_page_prompt(self, novel_id: UUID, page_id: str, tracker: Optional[TaskProgressTracker] = None) -> dict:
        """重新生成指定页面的生图提示词.

        发送该页面所在整个章节的所有页面给 AI，只更新目标页面的提示词。
        T3 D42: Uses short transaction pattern.
        """
        if tracker:
            await tracker.set_running(f"开始重新生成页面 {page_id} 提示词...")

        system_prompt = await get_prompt("ai_image_prompt_generation")

        # Step 1: Short read — get all pages + shot content + storyboard details
        async with async_session_factory() as read_session:
            layout_chapters = await self._get_layout_chapters_session(read_session, novel_id)
            lc_sort_map = {lc.id: lc.sort_order for lc in layout_chapters}
            lc_title_map = {lc.id: lc.title for lc in layout_chapters}

            # 查询 ScriptShot.content
            content_map = {}
            script_chs = await self._get_script_chapters_session(read_session, novel_id)
            sc_sort_map = {sc.id: sc.sort_order for sc in script_chs}
            if sc_sort_map:
                ss_r = await read_session.execute(
                    select(ScriptShot).where(ScriptShot.chapter_id.in_(list(sc_sort_map.keys())))
                )
                for ss in ss_r.scalars().all():
                    so = sc_sort_map.get(ss.chapter_id)
                    if so is not None:
                        content_map[(so, ss.shot_id)] = ss.content

            # 查询 StoryboardShot.storyboard_details
            sb_detail_map = {}
            storyboard_chs = await self._get_storyboard_chapters_session(read_session, novel_id)
            sbc_sort_map = {sc.id: sc.sort_order for sc in storyboard_chs}
            if sbc_sort_map:
                sbs_r = await read_session.execute(
                    select(StoryboardShot).where(StoryboardShot.chapter_id.in_(list(sbc_sort_map.keys())))
                )
                for sbs in sbs_r.scalars().all():
                    so = sbc_sort_map.get(sbs.chapter_id)
                    if so is not None:
                        sb_detail_map[(so, sbs.shot_id)] = sbs.storyboard_details

            all_pages_raw = await self._get_all_pages_for_novel_session(read_session, novel_id)
            all_pages = [
                {
                    "id": p.id,
                    "chapter_id": p.chapter_id,
                    "page_label": p.page_label,
                    "layout_type": p.layout_type,
                    "page_purpose": p.page_purpose,
                    "visual_focus": p.visual_focus,
                    "shots": [
                        {"shotId": s.shot_id, "sortOrder": s.sort_order}
                        for s in p.shots
                    ],
                }
                for p in all_pages_raw
            ]

        # 找到目标页面及其所在章节
        target_page = None
        target_chapter_id = None
        for p in all_pages:
            if p["page_label"] == page_id:
                target_page = p
                target_chapter_id = p["chapter_id"]
                break

        if target_page is None:
            raise ValueError(f"页面 {page_id} 不存在")

        # 构建该章节的完整数据
        sort_order = lc_sort_map.get(target_chapter_id, 0)
        chapter_pages = [p for p in all_pages if p["chapter_id"] == target_chapter_id]
        all_shot_ids = set()
        for p in chapter_pages:
            for s in p["shots"]:
                all_shot_ids.add(s["shotId"])
        chapter_shots = []
        for sid in sorted(all_shot_ids):
            chapter_shots.append({
                "shotId": sid,
                "content": content_map.get((sort_order, sid), ""),
                "storyboardDetails": sb_detail_map.get((sort_order, sid), ""),
            })
        ch_payload = []
        for p in chapter_pages:
            page_shots = []
            for s in p["shots"]:
                sid = s["shotId"]
                page_shots.append({
                    "shotId": sid,
                    "content": content_map.get((sort_order, sid), ""),
                    "storyboardDetails": sb_detail_map.get((sort_order, sid), ""),
                })
            ch_payload.append({
                "pageId": p["page_label"],
                "layoutType": p["layout_type"],
                "pagePurpose": p["page_purpose"],
                "visualFocus": p["visual_focus"],
                "shots": page_shots,
            })

        try:
            # Step 2: AI call — 发送整个章节
            results = await self._call_image_prompt_llm(ch_payload, system_prompt)
            image_prompt = results.get(page_id, "")

            # Step 3: Short write — 只更新目标页面
            if image_prompt:
                async with async_session_factory() as write_session:
                    existing_r = await write_session.execute(
                        select(ImagePrompt).where(ImagePrompt.page_id == target_page["id"])
                    )
                    existing = existing_r.scalar_one_or_none()
                    if existing:
                        existing.full_prompt = image_prompt
                    else:
                        write_session.add(ImagePrompt(
                            page_id=target_page["id"],
                            full_prompt=image_prompt,
                        ))
                    await write_session.commit()
                logger.info(f"页面 {page_id} 提示词已重生")

            async with async_session_factory() as result_session:
                result_data = await self._build_layout_response_session(result_session, novel_id)
            if tracker:
                await tracker.complete(result_data, f"页面 {page_id} 提示词已重新生成")
            return result_data
        except Exception as e:
            if tracker:
                await tracker.fail(str(e))
            raise

    # =================================================================
    # match_references (T3 D42: short transaction pattern)
    # =================================================================

    async def match_references(self, novel_id: UUID, project_id: UUID, tracker: Optional[TaskProgressTracker] = None) -> dict:
        """根据每页的 image_prompt，调用 LLM 智能匹配项目中的参考图.

        T3 D42: Uses short transaction pattern:
        1. Short read: get all pages + all reference resources
        2. Parallel AI calls in batches (no session held)
        3. Short write: update reference_ids
        """
        if tracker:
            await tracker.set_running("开始匹配参考图...")

        try:
            # Step 1: Short read — get all pages + reference resources
            async with async_session_factory() as read_session:
                chapters = await self._get_layout_chapters_session(read_session, novel_id)
                if not chapters:
                    raise ValueError("请先生成排版")

                all_pages_raw = await self._get_all_pages_for_novel_session(read_session, novel_id)
                all_pages = [
                    {
                        "page_label": p.page_label,
                        "image_prompt": p.image_prompt.full_prompt if p.image_prompt else "",
                    }
                    for p in all_pages_raw
                    if p.image_prompt
                    and not (p.reference_match and p.reference_match.ref_ids and len(p.reference_match.ref_ids) > 0)
                ]

                # 分页限制：只处理前 100 页
                if settings.PAGE_LIMIT_ENABLED and len(all_pages) > 100:
                    logger.info(f"PAGE_LIMIT_ENABLED=True，参考图匹配只处理前 100 页（共 {len(all_pages)} 页）")
                    all_pages = all_pages[:100]
                    if tracker:
                        await tracker.update_progress(0, "开始匹配参考图（前100页模式）...")

                if not all_pages:
                    raise ValueError("请先为所有页面生成生图提示词（点击「一键生成提示词」），再进行参考图匹配")

                # Get project's reference resources
                world_result = await read_session.execute(
                    select(WorldBuilding).where(WorldBuilding.project_id == project_id)
                )
                world_ids = [w.id for w in world_result.scalars().all()]

                if not world_ids:
                    raise ValueError("请先在「世界观设定」中创建世界观和参考图")

                references = await self._collect_references(read_session, project_id, world_ids)

            all_refs = sum(len(v) for v in references.values())
            if all_refs == 0:
                raise ValueError("请在「世界观设定」中添加参考图（角色/场景/道具/建筑/服装）")

            # 参考图预算控制——避免候选过多撑爆 LLM token 上限
            MAX_REFS_FOR_LLM = 200
            if all_refs > MAX_REFS_FOR_LLM:
                logger.warning(f"参考图候选总数 {all_refs} 超过预算 {MAX_REFS_FOR_LLM}，将按比例截断各类别")
                ratio = MAX_REFS_FOR_LLM / all_refs
                for cat in references:
                    cap = max(1, int(len(references[cat]) * ratio))
                    references[cat] = references[cat][:cap]

            # Step 2: Parallel AI calls in batches (no session held)
            ref_system_prompt = await get_prompt("reference_match")
            batch_size = 50
            total_pages = len(all_pages)
            final_result = {}
            batch_tasks = []

            for batch_start in range(0, total_pages, batch_size):
                batch_pages = all_pages[batch_start:batch_start + batch_size]
                logger.info(f"参考图匹配: 提交第 {batch_start+1}-{min(batch_start+batch_size, total_pages)} 页")

                pages_data = [
                    {"page_id": p["page_label"], "image_prompt": p["image_prompt"]}
                    for p in batch_pages
                ]

                user_message = json.dumps({
                    "pages": pages_data,
                    "references": references,
                }, ensure_ascii=False)

                async def call_single_batch(msg: str, sp: str = ref_system_prompt) -> dict:
                    llm = LLMAdapter(
                        api_key=settings.LLM_API_KEY,
                        api_base=settings.LLM_API_BASE,
                        model=settings.LLM_MODEL,
                    )
                    messages_batch = [
                        ChatMessage(role="system", content=sp),
                        ChatMessage(role="user", content=msg),
                    ]
                    result = await llm.chat(messages=messages_batch)
                    parsed = parse_llm_json(result.content)
                    if isinstance(parsed, dict):
                        return parsed
                    return {}

                batch_tasks.append(call_single_batch(user_message))

            if batch_tasks:
                results = await asyncio.gather(*batch_tasks, return_exceptions=True)
                for i, res in enumerate(results):
                    if isinstance(res, Exception):
                        logger.error(f"参考图匹配 LLM 调用失败 (batch {i+1}): {res}")
                    elif isinstance(res, dict):
                        final_result.update(res)

                    if tracker:
                        processed = min((i + 1) * batch_size, total_pages)
                        progress_pct = int(processed / total_pages * 90)
                        await tracker.update_progress(progress_pct, f"已匹配 {processed}/{total_pages} 页")

            # Step 3: Short write — update reference_ids
            valid_page_labels = {p["page_label"] for p in all_pages}
            valid_ref_ids = set()
            for cat_refs in references.values():
                for r in cat_refs:
                    valid_ref_ids.add(r["id"])
            MAX_REFS_PER_PAGE = 10

            if final_result:
                async with async_session_factory() as write_session:
                    all_pages = await self._get_all_pages_for_novel_session(write_session, novel_id)
                    saved_count = 0
                    for p in all_pages:
                        if p.page_label in final_result:
                            refs = final_result[p.page_label]
                            if p.page_label not in valid_page_labels:
                                logger.warning(f"参考匹配: 页面 {p.page_label} 不在请求集合中，跳过")
                                continue
                            validated_refs = [
                                r for r in refs
                                if r in valid_ref_ids
                            ][:MAX_REFS_PER_PAGE]
                            if len(refs) != len(validated_refs):
                                logger.warning(
                                    f"参考匹配: 页面 {p.page_label} 有 "
                                    f"{len(refs) - len(validated_refs)} 个无效引用 ID 被过滤"
                                )
                            if p.reference_match:
                                p.reference_match.ref_ids = validated_refs
                            else:
                                write_session.add(ReferenceMatch(
                                    page_id=p.id,
                                    ref_ids=validated_refs,
                                ))
                            saved_count += len(validated_refs)
                    await write_session.commit()
                    logger.info(f"参考图匹配完成: {saved_count} 条匹配记录已保存")

            if tracker:
                await tracker.complete(final_result)
            return final_result
        except Exception as e:
            if tracker:
                await tracker.fail(str(e))
            raise

    async def _collect_references(self, session: AsyncSession, project_id: UUID, world_ids: list) -> dict:
        """Collect all reference resources for a project (read-only)."""
        references = {
            "character": [],
            "character_ref": [],
            "character_state": [],
            "scene_asset": [],
            "prop": [],
            "building": [],
            "outfit": [],
        }

        # characters
        result = await session.execute(
            select(Character).where(Character.project_id == project_id)
        )
        for ch in result.scalars().all():
            references["character"].append({
                "id": str(ch.id),
                "name": ch.name,
                "description": self._compress_ref_description(ch.description or ""),
                "tags": ch.aliases or "",
                "category": "character",
            })

        # 角色多角度参考图 (single join query avoids N+1)
        cri_result = await session.execute(
            select(CharacterReferenceImage, Character)
            .join(Character, CharacterReferenceImage.character_id == Character.id)
            .where(Character.project_id == project_id)
        )
        for cri, char in cri_result.all():
            references["character_ref"].append({
                "id": str(cri.id),
                "name": f"{char.name}-{cri.angle or '参考'}",
                "description": f"{char.name}的{cri.angle or '多角度'}参考图",
                "tags": cri.tags or [],
                "category": "character_ref",
            })

        # CharacterState — each state may have a generated reference image
        cs_result = await session.execute(
            select(CharacterState).where(
                CharacterState.character_id.in_(
                    select(Character.id).where(Character.project_id == project_id)
                )
            )
        )
        for cs in cs_result.scalars().all():
            references["character_state"].append({
                "id": str(cs.id),
                "name": f"{cs.name}",
                "description": cs.description or "",
                "tags": cs.aliases or "",
                "category": "character_state",
            })

        # Batch queries using IN to avoid N+1 (4 queries total instead of 4N)
        sa_result = await session.execute(
            select(SceneAsset).where(SceneAsset.world_id.in_(world_ids))
        )
        for asset in sa_result.scalars().all():
            references["scene_asset"].append({
                "id": str(asset.id),
                "name": asset.name,
                "description": self._compress_ref_description(asset.description or ""),
                "tags": asset.tags or [],
                "category": "scene_asset",
            })

        prop_result = await session.execute(
            select(Prop).where(Prop.world_id.in_(world_ids))
        )
        for prop in prop_result.scalars().all():
            references["prop"].append({
                "id": str(prop.id),
                "name": prop.name,
                "description": self._compress_ref_description(prop.description or ""),
                "tags": prop.tags or [],
                "category": "prop",
            })

        bld_result = await session.execute(
            select(Building).where(Building.world_id.in_(world_ids))
        )
        for building in bld_result.scalars().all():
            references["building"].append({
                "id": str(building.id),
                "name": building.name,
                "description": self._compress_ref_description(building.description or ""),
                "tags": [],
                "category": "building",
            })

        out_result = await session.execute(
            select(Outfit).where(Outfit.world_id.in_(world_ids))
        )
        for outfit in out_result.scalars().all():
            references["outfit"].append({
                "id": str(outfit.id),
                "name": outfit.name,
                "description": self._compress_ref_description(outfit.description or ""),
                "tags": [],
                "category": "outfit",
            })

        return references

    # =================================================================
    # Shared layout helpers
    # =================================================================

    async def _get_layout_chapters_session(self, session: AsyncSession, novel_id: UUID):
        result = await session.execute(
            select(LayoutChapter).where(LayoutChapter.novel_id == novel_id).order_by(LayoutChapter.sort_order)
        )
        return list(result.scalars().all())

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

    async def _get_all_pages_for_novel_session(self, session: AsyncSession, novel_id: UUID) -> list:
        """Get all layout pages for a novel via a single join query (avoids N+1)."""
        result = await session.execute(
            select(LayoutPage)
            .options(
                selectinload(LayoutPage.shots),
                selectinload(LayoutPage.image_prompt),
                selectinload(LayoutPage.reference_match),
                selectinload(LayoutPage.generated_images),
            )
            .join(LayoutChapter, LayoutPage.chapter_id == LayoutChapter.id)
            .where(LayoutChapter.novel_id == novel_id)
            .order_by(LayoutChapter.sort_order, LayoutPage.sort_order)
        )
        return list(result.scalars().all())

    async def _build_layout_response_session(self, session: AsyncSession, novel_id: UUID) -> dict:
        chapters = await self._get_layout_chapters_session(session, novel_id)
        if not chapters:
            return {"chapters": []}

        all_pages = await self._get_all_pages_for_novel_session(session, novel_id)
        from collections import defaultdict
        pages_by_chapter = defaultdict(list)
        for p in all_pages:
            pages_by_chapter[p.chapter_id].append(p)

        result = []
        for ch in chapters:
            pages = [
                {
                    "id": str(p.id),
                    "page_id": p.page_label,
                    "layout_type": p.layout_type,
                    "page_purpose": p.page_purpose,
                    "visual_focus": p.visual_focus,
                    "image_prompt": p.image_prompt.full_prompt if p.image_prompt else "",
                    "image_url": p.generated_images[0].image_url if p.generated_images else "",
                    "reference_ids": p.reference_match.ref_ids if p.reference_match else [],
                    "shots": [
                        {
                            "shotId": s.shot_id,
                            "sortOrder": s.sort_order,
                        }
                        for s in p.shots
                    ],
                    "sort_order": p.sort_order,
                }
                for p in pages_by_chapter.get(ch.id, [])
            ]
            result.append({
                "id": str(ch.id),
                "title": ch.title,
                "sort_order": ch.sort_order,
                "pages": pages,
            })
        return {"chapters": result}
