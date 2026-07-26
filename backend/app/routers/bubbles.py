from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload
from uuid import UUID

from app.core.database import get_db
from app.middleware.auth import get_current_user
from app.models.bubble import Bubble
from app.schemas.common import ApiResponse
from app.schemas.bubble_schema import (
    BubbleCreate,
    BubbleUpdate,
    BubbleResponse,
    BubbleBatchUpdate,
)

router = APIRouter()


# ======================================================================
# Bubble CRUD
# ======================================================================


@router.get("/{project_id}/panels/{panel_id}/bubbles")
async def list_bubbles(
    project_id: UUID,
    panel_id: UUID,
    bubble_type: str = Query("", description="按类型筛选: dialogue/narration/thinking/sfx"),
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取 Panel 的气泡列表"""
    query = select(Bubble).where(Bubble.panel_id == panel_id).order_by(Bubble.order)
    if bubble_type:
        query = query.where(Bubble.bubble_type == bubble_type)
    result = await db.execute(query)
    bubbles = result.scalars().all()
    return ApiResponse(data={
        "items": [BubbleResponse.model_validate(b).model_dump() for b in bubbles],
        "total": len(bubbles),
    })


@router.post("/{project_id}/panels/{panel_id}/bubbles")
async def create_bubble(
    project_id: UUID,
    panel_id: UUID,
    data: BubbleCreate,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建气泡"""
    bubble = Bubble(
        panel_id=panel_id,
        bubble_type=data.bubble_type,
        text=data.text,
        speaker=data.speaker,
        speaker_id=data.speaker_id,
        order=data.order,
        style=data.style,
        font=data.font,
        font_size=data.font_size,
        position_x=data.position_x,
        position_y=data.position_y,
        width=data.width,
        height=data.height,
    )
    db.add(bubble)
    await db.flush()
    await db.refresh(bubble)
    return ApiResponse(data=BubbleResponse.model_validate(bubble).model_dump())


@router.get("/{project_id}/panels/{panel_id}/bubbles/{bubble_id}")
async def get_bubble(
    project_id: UUID,
    panel_id: UUID,
    bubble_id: UUID,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取气泡详情"""
    result = await db.execute(
        select(Bubble).where(Bubble.id == bubble_id, Bubble.panel_id == panel_id)
    )
    bubble = result.scalar_one_or_none()
    if bubble is None:
        raise HTTPException(status_code=404, detail="气泡不存在")
    return ApiResponse(data=BubbleResponse.model_validate(bubble).model_dump())


@router.put("/{project_id}/panels/{panel_id}/bubbles/{bubble_id}")
async def update_bubble(
    project_id: UUID,
    panel_id: UUID,
    bubble_id: UUID,
    data: BubbleUpdate,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新气泡"""
    result = await db.execute(
        select(Bubble).where(Bubble.id == bubble_id, Bubble.panel_id == panel_id)
    )
    bubble = result.scalar_one_or_none()
    if bubble is None:
        raise HTTPException(status_code=404, detail="气泡不存在")

    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    for key, value in update_data.items():
        setattr(bubble, key, value)

    await db.flush()
    await db.refresh(bubble)
    return ApiResponse(data=BubbleResponse.model_validate(bubble).model_dump())


@router.delete("/{project_id}/panels/{panel_id}/bubbles/{bubble_id}")
async def delete_bubble(
    project_id: UUID,
    panel_id: UUID,
    bubble_id: UUID,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除气泡"""
    result = await db.execute(
        select(Bubble).where(Bubble.id == bubble_id, Bubble.panel_id == panel_id)
    )
    bubble = result.scalar_one_or_none()
    if bubble is None:
        raise HTTPException(status_code=404, detail="气泡不存在")

    await db.delete(bubble)
    await db.flush()
    return ApiResponse(data={"deleted": True})


@router.put("/{project_id}/panels/{panel_id}/bubbles/batch-order")
async def batch_update_bubbles(
    project_id: UUID,
    panel_id: UUID,
    data: BubbleBatchUpdate,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """批量更新气泡（用于拖拽排序）"""
    bubble_ids = [b.id for b in data.bubbles if b.id is not None]
    if not bubble_ids:
        return ApiResponse(data={"updated": True})

    result = await db.execute(
        select(Bubble).where(
            Bubble.id.in_(bubble_ids),
            Bubble.panel_id == panel_id,
        )
    )
    bubbles_by_id = {b.id: b for b in result.scalars().all()}

    for bubble_data in data.bubbles:
        if bubble_data.id is None:
            continue
        bubble = bubbles_by_id.get(bubble_data.id)
        if bubble is None:
            continue
        update_data = {k: v for k, v in bubble_data.model_dump().items() if v is not None}
        for key, value in update_data.items():
            setattr(bubble, key, value)

    await db.flush()
    return ApiResponse(data={"updated": True})
