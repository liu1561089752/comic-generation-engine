"""Layout repository - data access for layout entities.

Extracted shared methods originally duplicated across layout/service.py
and generation/service.py.
"""
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.layout import LayoutChapter, LayoutPage, LayoutShot
from app.models.novel import ScriptChapter, ScriptShot
from app.models.storyboard import StoryboardChapter, StoryboardShot


async def get_layout_chapters_session(session: AsyncSession, novel_id: UUID):
    """Get all layout chapters for a novel, ordered by sort_order."""
    result = await session.execute(
        select(LayoutChapter)
        .where(LayoutChapter.novel_id == novel_id)
        .order_by(LayoutChapter.sort_order)
    )
    return list(result.scalars().all())


async def _get_script_chapters_session(session: AsyncSession, novel_id: UUID):
    """Get all script chapters for a novel."""
    result = await session.execute(
        select(ScriptChapter)
        .where(ScriptChapter.novel_id == novel_id)
        .order_by(ScriptChapter.sort_order)
    )
    return list(result.scalars().all())


async def _get_storyboard_chapters_session(session: AsyncSession, novel_id: UUID):
    """Get all storyboard chapters for a novel."""
    result = await session.execute(
        select(StoryboardChapter)
        .where(StoryboardChapter.novel_id == novel_id)
        .order_by(StoryboardChapter.sort_order)
    )
    return list(result.scalars().all())


async def build_layout_response_session(session: AsyncSession, novel_id: UUID) -> dict:
    """Build the full layout response including chapters/pages/shots with enriched data.

    Queries LayoutChapter with selectinload for pages -> shots, image_prompt,
    reference_match, generated_images. Then enriches each shot with
    ScriptShot.content and StoryboardShot.storyboard_details.
    """
    result = await session.execute(
        select(LayoutChapter)
        .options(
            selectinload(LayoutChapter.pages)
            .selectinload(LayoutPage.shots),
            selectinload(LayoutChapter.pages)
            .selectinload(LayoutPage.image_prompt),
            selectinload(LayoutChapter.pages)
            .selectinload(LayoutPage.reference_match),
            selectinload(LayoutChapter.pages)
            .selectinload(LayoutPage.generated_images),
        )
        .where(LayoutChapter.novel_id == novel_id)
        .order_by(LayoutChapter.sort_order)
    )
    chapters = result.scalars().all()

    # Batch query LayoutShot to build shot map: page_id -> shot list
    all_page_ids = [p.id for ch in chapters for p in ch.pages]
    shot_map = {}
    if all_page_ids:
        shots_r = await session.execute(
            select(LayoutShot).where(LayoutShot.page_id.in_(all_page_ids))
            .order_by(LayoutShot.sort_order)
        )
        for ls in shots_r.scalars().all():
            shot_map.setdefault(str(ls.page_id), []).append({
                "shotId": ls.shot_id,
                "sortOrder": ls.sort_order,
            })

    # Build ScriptShot.content mapping: (chapter_sort_order, shot_id) -> content
    content_map = {}
    script_chs = await _get_script_chapters_session(session, novel_id)
    script_chapter_ids = [sc.id for sc in script_chs]
    sc_sort_map = {sc.id: sc.sort_order for sc in script_chs}
    if script_chapter_ids:
        script_shots_r = await session.execute(
            select(ScriptShot).where(ScriptShot.chapter_id.in_(script_chapter_ids))
        )
        for ss in script_shots_r.scalars().all():
            sort_order = sc_sort_map.get(ss.chapter_id)
            if sort_order is not None:
                content_map[(sort_order, ss.shot_id)] = ss.content

    # Build StoryboardShot.storyboard_details mapping:
    #   (chapter_sort_order, shot_id) -> storyboard_details
    sb_detail_map = {}
    storyboard_chs = await _get_storyboard_chapters_session(session, novel_id)
    sb_chapter_ids = [sc.id for sc in storyboard_chs]
    sb_sort_map = {sc.id: sc.sort_order for sc in storyboard_chs}
    if sb_chapter_ids:
        sb_shots_r = await session.execute(
            select(StoryboardShot).where(StoryboardShot.chapter_id.in_(sb_chapter_ids))
        )
        for sbs in sb_shots_r.scalars().all():
            sort_order = sb_sort_map.get(sbs.chapter_id)
            if sort_order is not None:
                sb_detail_map[(sort_order, sbs.shot_id)] = sbs.storyboard_details

    # Build chapter sort_order lookup: page_id -> chapter.sort_order
    ch_sort_map = {ch.id: ch.sort_order for ch in chapters}

    return {"chapters": [
        {
            "id": str(ch.id),
            "title": ch.title,
            "sort_order": ch.sort_order,
            "pages": [
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
                            **s,
                            "content": content_map.get((ch_sort_map.get(ch.id), s["shotId"]), ""),
                            "storyboardDetails": sb_detail_map.get((ch_sort_map.get(ch.id), s["shotId"]), ""),
                        }
                        for s in shot_map.get(str(p.id), [])
                    ],
                    "sort_order": p.sort_order,
                }
                for p in ch.pages
            ],
        }
        for ch in chapters
    ]}
