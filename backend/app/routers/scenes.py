from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.core.database import get_db
from app.middleware.auth import get_current_user
from app.modules.scene.service import SceneService
from app.schemas.common import ApiResponse
from app.schemas.scene_schema import (
    SceneCreate,
    SceneUpdate,
    SceneResponse,
    SceneDetailResponse,
    PanelResponse,
)

router = APIRouter()


@router.post("/{project_id}/chapters/{chapter_id}/analyze")
async def analyze_chapter(
    project_id: UUID,
    chapter_id: UUID,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """启动剧情分析：调用 StoryAnalyzerAgent 分析章节并创建 Scene"""
    service = SceneService(db)
    scenes = await service.analyze_chapter(chapter_id)
    return ApiResponse(data={
        "items": [SceneResponse.model_validate(s).model_dump() for s in scenes],
        "total": len(scenes),
    })


@router.get("/{project_id}/chapters/{chapter_id}/scenes")
async def list_scenes(
    project_id: UUID,
    chapter_id: UUID,
    skip: int = 0,
    limit: int = 20,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取章节的 Scene 列表"""
    service = SceneService(db)
    scenes, total = await service.list_scenes_by_chapter(chapter_id, skip=skip, limit=limit)
    return ApiResponse(data={
        "items": [SceneResponse.model_validate(s).model_dump() for s in scenes],
        "total": total,
        "skip": skip,
        "limit": limit,
    })


@router.get("/{project_id}/scenes/{scene_id}")
async def get_scene_detail(
    project_id: UUID,
    scene_id: UUID,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取 Scene 详情（含关联 Panel 列表）"""
    service = SceneService(db)
    scene = await service.get_scene_detail(scene_id)
    if scene is None:
        raise HTTPException(status_code=404, detail="Scene 不存在")
    data = SceneResponse.model_validate(scene).model_dump()
    data["panels"] = [PanelResponse.model_validate(p).model_dump() for p in scene.panels]
    return ApiResponse(data=data)


@router.put("/{project_id}/scenes/{scene_id}")
async def update_scene(
    project_id: UUID,
    scene_id: UUID,
    data: SceneUpdate,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新 Scene 信息"""
    service = SceneService(db)
    scene = await service.update_scene(scene_id, data)
    if scene is None:
        raise HTTPException(status_code=404, detail="Scene 不存在")
    return ApiResponse(data=SceneResponse.model_validate(scene).model_dump())
