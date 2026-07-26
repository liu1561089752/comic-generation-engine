from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.core.database import get_db
from app.middleware.auth import get_current_user
from app.modules.scene.service import PanelService
from app.schemas.common import ApiResponse
from app.schemas.scene_schema import (
    PanelCreate,
    PanelUpdate,
    CameraUpdate,
    CompositionUpdate,
    PanelResponse,
    PanelDetailResponse,
    ShotResponse,
    BubbleResponse,
)

router = APIRouter()


@router.post("/{project_id}/scenes/{scene_id}/split")
async def split_scene(
    project_id: UUID,
    scene_id: UUID,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """启动语义切句：调用 SemanticSplitterAgent 拆分 Scene 为 Panel"""
    service = PanelService(db)
    panels = await service.split_scene(scene_id)
    return ApiResponse(data={
        "items": [PanelResponse.model_validate(p).model_dump() for p in panels],
        "total": len(panels),
    })


@router.get("/{project_id}/scenes/{scene_id}/panels")
async def list_panels(
    project_id: UUID,
    scene_id: UUID,
    skip: int = 0,
    limit: int = 20,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取 Scene 的 Panel 列表"""
    service = PanelService(db)
    panels, total = await service.list_panels_by_scene(scene_id, skip=skip, limit=limit)
    return ApiResponse(data={
        "items": [PanelResponse.model_validate(p).model_dump() for p in panels],
        "total": total,
        "skip": skip,
        "limit": limit,
    })


@router.get("/{project_id}/panels/{panel_id}")
async def get_panel_detail(
    project_id: UUID,
    panel_id: UUID,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取 Panel 详情（含关联 Shot/Bubble 列表）"""
    service = PanelService(db)
    panel = await service.get_panel_detail(panel_id)
    if panel is None:
        raise HTTPException(status_code=404, detail="Panel 不存在")
    data = PanelResponse.model_validate(panel).model_dump()
    data["shots"] = [ShotResponse.model_validate(s).model_dump() for s in panel.shots]
    data["bubbles"] = [BubbleResponse.model_validate(b).model_dump() for b in panel.bubbles]
    return ApiResponse(data=data)


@router.put("/{project_id}/panels/{panel_id}")
async def update_panel(
    project_id: UUID,
    panel_id: UUID,
    data: PanelUpdate,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新 Panel（action, emotion, camera_type 等）"""
    service = PanelService(db)
    panel = await service.update_panel(panel_id, data)
    if panel is None:
        raise HTTPException(status_code=404, detail="Panel 不存在")
    return ApiResponse(data=PanelResponse.model_validate(panel).model_dump())


@router.post("/{project_id}/panels/{panel_id}/split")
async def split_panel_manual(
    project_id: UUID,
    panel_id: UUID,
    split_after_paragraph: int = Query(..., description="在此段落位置后拆分"),
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """手动拆分 Panel"""
    service = PanelService(db)
    left, right = await service.split_panel(panel_id, split_after_paragraph)
    if left is None or right is None:
        raise HTTPException(status_code=404, detail="Panel 不存在")
    return ApiResponse(data={
        "left": PanelResponse.model_validate(left).model_dump(),
        "right": PanelResponse.model_validate(right).model_dump(),
    })


@router.put("/{project_id}/panels/{panel_id}/camera")
async def update_panel_camera(
    project_id: UUID,
    panel_id: UUID,
    data: CameraUpdate,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新 Panel 镜头设置（镜头类型、运镜方式）"""
    service = PanelService(db)
    panel = await service.update_panel(panel_id, PanelUpdate(**data.model_dump(exclude_none=True)))
    if panel is None:
        raise HTTPException(status_code=404, detail="Panel 不存在")
    return ApiResponse(data=PanelResponse.model_validate(panel).model_dump())


@router.put("/{project_id}/panels/{panel_id}/composition")
async def update_panel_composition(
    project_id: UUID,
    panel_id: UUID,
    data: CompositionUpdate,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新 Panel 构图设置（构图规则、布局类型）"""
    service = PanelService(db)
    panel = await service.update_panel(panel_id, PanelUpdate(**data.model_dump(exclude_none=True)))
    if panel is None:
        raise HTTPException(status_code=404, detail="Panel 不存在")
    return ApiResponse(data=PanelResponse.model_validate(panel).model_dump())


@router.post("/{project_id}/panels/{panel_id}/merge")
async def merge_panels(
    project_id: UUID,
    panel_id: UUID,
    target_panel_id: UUID = Query(..., description="要合并到当前 Panel 的目标 Panel ID"),
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """合并 Panel：将目标 Panel 合并到当前 Panel"""
    service = PanelService(db)
    merged = await service.merge_panels(panel_id, target_panel_id)
    if merged is None:
        raise HTTPException(status_code=404, detail="Panel 不存在")
    return ApiResponse(data=PanelResponse.model_validate(merged).model_dump())
