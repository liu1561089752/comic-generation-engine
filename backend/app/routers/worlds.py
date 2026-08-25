from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from pydantic import BaseModel
from app.core.task_types import TASK_AI_CREATE_WORLD, TASK_AI_EXTRACT_BUILDINGS, TASK_AI_EXTRACT_OUTFITS, TASK_AI_EXTRACT_PROPS, TASK_AI_EXTRACT_SCENES, TASK_GENERATE_BUILDING_IMAGE, TASK_GENERATE_OUTFIT_IMAGE, TASK_GENERATE_PROP_IMAGE, TASK_GENERATE_SCENE_IMAGE
import logging

from app.core.database import get_db, async_session_factory
from app.middleware.auth import get_current_user
from app.modules.world.service import WorldService
from app.infra.task_progress import TaskProgressTracker, find_running_task
from app.infra.task_registry import spawn_background_task
from app.infra.task_dispatcher import register_task_runner as _register
from app.schemas.common import ApiResponse
from app.schemas.world_schema import (
    WorldBuildingUpdate,
    WorldBuildingResponse,
    SceneAssetCreate,
    SceneAssetUpdate,
    SceneAssetResponse,
    PropCreate,
    PropUpdate,
    PropResponse,
    BuildingCreate,
    BuildingUpdate,
    BuildingResponse,
    OutfitCreate,
    OutfitUpdate,
    OutfitResponse,
)

router = APIRouter()


class ExtractScenesRequest(BaseModel):
    novel_text: str


# ======================================================================
# 世界观 AI 后台任务（AI辅助创建 / 一键提取场景/道具/建筑/服装）
# ======================================================================


async def _run_ai_create_world(
    project_id: UUID, novel_text: str, tracker: TaskProgressTracker
):
    """AI辅助创建世界观后台任务 — service 内部短事务写库。"""
    try:
        await tracker.set_running("开始 AI 创建世界观...")
        async with async_session_factory() as session:
            service = WorldService(session)
            world = await service.ai_create_world(project_id, novel_text)
        data = WorldBuildingResponse.model_validate(world).model_dump(mode="json")
        await tracker.complete(data, f"世界观「{world.name}」创建成功")
    except Exception as e:
        logger.exception(f"AI 创建世界观任务失败: {e}")
        await tracker.fail(str(e))


async def _run_ai_extract_scenes(
    world_id: UUID, novel_text: str, tracker: TaskProgressTracker
):
    """一键提取场景后台任务。"""
    try:
        await tracker.set_running("开始提取场景...")
        async with async_session_factory() as session:
            service = WorldService(session)
            assets = await service.ai_extract_scene_assets(world_id, novel_text)
        items = [SceneAssetResponse.model_validate(a).model_dump(mode="json") for a in assets]
        await tracker.complete(
            {"items": items, "total": len(assets)},
            f"成功提取 {len(assets)} 个场景",
        )
    except Exception as e:
        logger.exception(f"提取场景任务失败: {e}")
        await tracker.fail(str(e))


async def _run_ai_extract_props(
    world_id: UUID, novel_text: str, tracker: TaskProgressTracker
):
    """一键提取道具后台任务。"""
    try:
        await tracker.set_running("开始提取道具...")
        async with async_session_factory() as session:
            service = WorldService(session)
            props = await service.ai_extract_props(world_id, novel_text)
        items = [PropResponse.model_validate(p).model_dump(mode="json") for p in props]
        await tracker.complete(
            {"items": items, "total": len(props)},
            f"成功提取 {len(props)} 个道具",
        )
    except Exception as e:
        logger.exception(f"提取道具任务失败: {e}")
        await tracker.fail(str(e))


async def _run_ai_extract_buildings(
    world_id: UUID, novel_text: str, tracker: TaskProgressTracker
):
    """一键提取建筑后台任务。"""
    try:
        await tracker.set_running("开始提取建筑...")
        async with async_session_factory() as session:
            service = WorldService(session)
            buildings = await service.ai_extract_buildings(world_id, novel_text)
        items = [BuildingResponse.model_validate(b).model_dump(mode="json") for b in buildings]
        await tracker.complete(
            {"items": items, "total": len(buildings)},
            f"成功提取 {len(buildings)} 个建筑",
        )
    except Exception as e:
        logger.exception(f"提取建筑任务失败: {e}")
        await tracker.fail(str(e))


async def _run_ai_extract_outfits(
    world_id: UUID, novel_text: str, tracker: TaskProgressTracker
):
    """一键提取服装后台任务。"""
    try:
        await tracker.set_running("开始提取服装...")
        async with async_session_factory() as session:
            service = WorldService(session)
            outfits = await service.ai_extract_outfits(world_id, novel_text)
        items = [OutfitResponse.model_validate(o).model_dump(mode="json") for o in outfits]
        await tracker.complete(
            {"items": items, "total": len(outfits)},
            f"成功提取 {len(outfits)} 个服装",
        )
    except Exception as e:
        logger.exception(f"提取服装任务失败: {e}")
        await tracker.fail(str(e))


async def _run_generate_scene_image(
    world_id: UUID, asset_id: UUID, project_id: UUID, tracker: TaskProgressTracker
):
    """生成场景图片后台任务。"""
    try:
        await tracker.set_running("开始生成场景图片...")
        async with async_session_factory() as session:
            service = WorldService(session)
            result = await service.generate_scene_image(asset_id, project_id)
        name = result.get("asset_name", "")
        await tracker.complete(result, f"场景「{name}」图片已生成")
    except Exception as e:
        logger.exception(f"生成场景图片任务失败: {e}")
        await tracker.fail(str(e))


async def _run_generate_prop_image(
    world_id: UUID, prop_id: UUID, project_id: UUID, tracker: TaskProgressTracker
):
    """生成道具图片后台任务。"""
    try:
        await tracker.set_running("开始生成道具图片...")
        async with async_session_factory() as session:
            service = WorldService(session)
            result = await service.generate_prop_image(prop_id, project_id)
        name = result.get("prop_name", "")
        await tracker.complete(result, f"道具「{name}」图片已生成")
    except Exception as e:
        logger.exception(f"生成道具图片任务失败: {e}")
        await tracker.fail(str(e))


async def _run_generate_building_image(
    world_id: UUID, building_id: UUID, project_id: UUID, tracker: TaskProgressTracker
):
    """生成建筑图片后台任务。"""
    try:
        await tracker.set_running("开始生成建筑图片...")
        async with async_session_factory() as session:
            service = WorldService(session)
            result = await service.generate_building_image(building_id, project_id)
        name = result.get("building_name", "")
        await tracker.complete(result, f"建筑「{name}」图片已生成")
    except Exception as e:
        logger.exception(f"生成建筑图片任务失败: {e}")
        await tracker.fail(str(e))


async def _run_generate_outfit_image(
    world_id: UUID, outfit_id: UUID, project_id: UUID, tracker: TaskProgressTracker
):
    """生成服装图片后台任务。"""
    try:
        await tracker.set_running("开始生成服装图片...")
        async with async_session_factory() as session:
            service = WorldService(session)
            result = await service.generate_outfit_image(outfit_id, project_id)
        name = result.get("outfit_name", "")
        await tracker.complete(result, f"服装「{name}」图片已生成")
    except Exception as e:
        logger.exception(f"生成服装图片任务失败: {e}")
        await tracker.fail(str(e))


# 注册任务执行器 — 供 retry 功能重新派发后台任务
@_register(TASK_AI_CREATE_WORLD)
async def _redispatch_ai_create_world(task, tracker):
    novel_text = task.input_data.get("novel_text", "")
    await _run_ai_create_world(task.project_id, novel_text, tracker)


@_register(TASK_AI_EXTRACT_SCENES)
async def _redispatch_ai_extract_scenes(task, tracker):
    world_id = UUID(task.input_data["world_id"])
    novel_text = task.input_data.get("novel_text", "")
    await _run_ai_extract_scenes(world_id, novel_text, tracker)


@_register(TASK_AI_EXTRACT_PROPS)
async def _redispatch_ai_extract_props(task, tracker):
    world_id = UUID(task.input_data["world_id"])
    novel_text = task.input_data.get("novel_text", "")
    await _run_ai_extract_props(world_id, novel_text, tracker)


@_register(TASK_AI_EXTRACT_BUILDINGS)
async def _redispatch_ai_extract_buildings(task, tracker):
    world_id = UUID(task.input_data["world_id"])
    novel_text = task.input_data.get("novel_text", "")
    await _run_ai_extract_buildings(world_id, novel_text, tracker)


@_register(TASK_AI_EXTRACT_OUTFITS)
async def _redispatch_ai_extract_outfits(task, tracker):
    world_id = UUID(task.input_data["world_id"])
    novel_text = task.input_data.get("novel_text", "")
    await _run_ai_extract_outfits(world_id, novel_text, tracker)


@_register(TASK_GENERATE_SCENE_IMAGE)
async def _redispatch_generate_scene_image(task, tracker):
    world_id = UUID(task.input_data["world_id"])
    asset_id = UUID(task.input_data["asset_id"])
    await _run_generate_scene_image(world_id, asset_id, task.project_id, tracker)


@_register(TASK_GENERATE_PROP_IMAGE)
async def _redispatch_generate_prop_image(task, tracker):
    world_id = UUID(task.input_data["world_id"])
    prop_id = UUID(task.input_data["prop_id"])
    await _run_generate_prop_image(world_id, prop_id, task.project_id, tracker)


@_register(TASK_GENERATE_BUILDING_IMAGE)
async def _redispatch_generate_building_image(task, tracker):
    world_id = UUID(task.input_data["world_id"])
    building_id = UUID(task.input_data["building_id"])
    await _run_generate_building_image(world_id, building_id, task.project_id, tracker)


@_register(TASK_GENERATE_OUTFIT_IMAGE)
async def _redispatch_generate_outfit_image(task, tracker):
    world_id = UUID(task.input_data["world_id"])
    outfit_id = UUID(task.input_data["outfit_id"])
    await _run_generate_outfit_image(world_id, outfit_id, task.project_id, tracker)


# ======================================================================
# AI 辅助创建
# ======================================================================


@router.post("/{project_id}/worlds/ai-assist")
async def ai_assist_world(
    project_id: UUID,
    data: dict,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """AI辅助创建世界观（调用LLM分析小说文本）"""
    from app.infra.adapters.llm_adapter import LLMAdapter
    from app.infra.adapters.base_llm import ChatMessage
    from app.core.config import settings
    from app.infra.prompt_loader import get_prompt
    llm = LLMAdapter(
        api_key=settings.LLM_API_KEY,
        api_base=settings.LLM_API_BASE,
        model=settings.LLM_MODEL or "gpt-4o",
    )
    novel_text = data.get("novel_text", "")
    if not novel_text:
        raise HTTPException(status_code=400, detail="请提供小说文本")
    try:
        system_prompt = await get_prompt("world_extraction", db)
        result = await llm.chat(messages=[
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="user", content=novel_text),
        ])
        from app.core.llm_utils import parse_llm_json
        parsed = parse_llm_json(result.content)
        return ApiResponse(data=parsed)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI分析失败: {str(e)}")


@router.post("/{project_id}/worlds/ai-create")
async def ai_create_world(
    project_id: UUID,
    data: dict,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """AI自动创建世界观（后台任务，纳入任务中心管理）"""
    novel_text = data.get("novel_text", "")
    if not novel_text:
        raise HTTPException(status_code=400, detail="请提供小说文本")
    existing = await find_running_task(db, project_id, TASK_AI_CREATE_WORLD)
    if existing:
        return ApiResponse(data={"task_id": str(existing.id), "message": "已有正在执行的 AI 创建世界观任务"})
    tracker = await TaskProgressTracker.create(
        db, project_id, TASK_AI_CREATE_WORLD,
        "AI创建世界观", {"novel_text": novel_text}
    )
    spawn_background_task(
        tracker.task.id,
        _run_ai_create_world(project_id, novel_text, tracker),
    )
    return ApiResponse(data={"task_id": str(tracker.task.id)})


# ======================================================================
# 世界观 CRUD
# ======================================================================


@router.get("/{project_id}/worlds")
async def list_worlds(
    project_id: UUID,
    skip: int = 0,
    limit: int = 20,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取世界观列表"""
    service = WorldService(db)
    worlds, total = await service.list_worlds(project_id, skip=skip, limit=limit)
    return ApiResponse(data={
        "items": [WorldBuildingResponse.model_validate(w).model_dump() for w in worlds],
        "total": total,
        "skip": skip,
        "limit": limit,
    })


@router.get("/{project_id}/worlds/{world_id}")
async def get_world(
    project_id: UUID,
    world_id: UUID,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取世界观详情"""
    service = WorldService(db)
    world = await service.get_world(world_id)
    if world is None:
        raise HTTPException(status_code=404, detail="世界观不存在")
    return ApiResponse(data=WorldBuildingResponse.model_validate(world).model_dump())


@router.put("/{project_id}/worlds/{world_id}")
async def update_world(
    project_id: UUID,
    world_id: UUID,
    data: WorldBuildingUpdate,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新世界观"""
    service = WorldService(db)
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    world = await service.update_world(world_id, update_data)
    if world is None:
        raise HTTPException(status_code=404, detail="世界观不存在")
    return ApiResponse(data=WorldBuildingResponse.model_validate(world).model_dump())


@router.delete("/{project_id}/worlds/{world_id}")
async def delete_world(
    project_id: UUID,
    world_id: UUID,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除世界观"""
    service = WorldService(db)
    deleted = await service.delete_world(world_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="世界观不存在")
    return ApiResponse(data={"deleted": True})


# ======================================================================
# 场景资产
# ======================================================================


@router.get("/{project_id}/worlds/{world_id}/scene-assets")
async def list_scene_assets(
    project_id: UUID,
    world_id: UUID,
    skip: int = 0,
    limit: int = 20,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取场景资产列表"""
    service = WorldService(db)
    assets, total = await service.list_scene_assets(world_id, skip=skip, limit=limit)
    return ApiResponse(data={
        "items": [SceneAssetResponse.model_validate(a).model_dump() for a in assets],
        "total": total,
    })


@router.post("/{project_id}/worlds/{world_id}/scene-assets")
async def create_scene_asset(
    project_id: UUID,
    world_id: UUID,
    data: SceneAssetCreate,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建场景资产"""
    service = WorldService(db)
    asset = await service.create_scene_asset(world_id, data)
    return ApiResponse(data=SceneAssetResponse.model_validate(asset).model_dump())


@router.put("/{project_id}/worlds/{world_id}/scene-assets/{asset_id}")
async def update_scene_asset(
    project_id: UUID,
    world_id: UUID,
    asset_id: UUID,
    data: SceneAssetUpdate,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新场景资产"""
    service = WorldService(db)
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    asset = await service.update_scene_asset(asset_id, update_data)
    if asset is None:
        raise HTTPException(status_code=404, detail="场景资产不存在")
    return ApiResponse(data=SceneAssetResponse.model_validate(asset).model_dump())


@router.delete("/{project_id}/worlds/{world_id}/scene-assets/{asset_id}")
async def delete_scene_asset(
    project_id: UUID,
    world_id: UUID,
    asset_id: UUID,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除场景资产"""
    service = WorldService(db)
    deleted = await service.delete_scene_asset(asset_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="场景资产不存在")
    return ApiResponse(data={"deleted": True})


@router.post("/{project_id}/worlds/{world_id}/scene-assets/ai-extract")
async def ai_extract_scenes(
    project_id: UUID,
    world_id: UUID,
    data: ExtractScenesRequest,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """从小说文本中提取场景资产（后台任务，纳入任务中心管理）"""
    novel_text = data.novel_text
    if not novel_text:
        raise HTTPException(status_code=400, detail="请提供小说文本")
    existing = await find_running_task(db, project_id, TASK_AI_EXTRACT_SCENES)
    if existing:
        return ApiResponse(data={"task_id": str(existing.id), "message": "已有正在执行的提取场景任务"})
    tracker = await TaskProgressTracker.create(
        db, project_id, TASK_AI_EXTRACT_SCENES,
        "提取场景", {"world_id": str(world_id), "novel_text": novel_text}
    )
    spawn_background_task(
        tracker.task.id,
        _run_ai_extract_scenes(world_id, novel_text, tracker),
    )
    return ApiResponse(data={"task_id": str(tracker.task.id)})


@router.post("/{project_id}/worlds/{world_id}/scene-assets/{asset_id}/generate-image")
async def generate_scene_image(
    project_id: UUID,
    world_id: UUID,
    asset_id: UUID,
    user_id: str = Depends(get_current_user),  # D48: 补全认证
    db: AsyncSession = Depends(get_db),
):
    """生成场景资产图片（后台任务，纳入任务中心管理）"""
    existing = await find_running_task(db, project_id, TASK_GENERATE_SCENE_IMAGE)
    if existing:
        return ApiResponse(data={"task_id": str(existing.id), "message": "已有正在执行的生成场景图片任务"})
    tracker = await TaskProgressTracker.create(
        db, project_id, TASK_GENERATE_SCENE_IMAGE,
        "生成场景图片", {"world_id": str(world_id), "asset_id": str(asset_id)}
    )
    spawn_background_task(
        tracker.task.id,
        _run_generate_scene_image(world_id, asset_id, project_id, tracker),
    )
    return ApiResponse(data={"task_id": str(tracker.task.id)})


# ======================================================================
# 道具
# ======================================================================


@router.get("/{project_id}/worlds/{world_id}/props")
async def list_props(
    project_id: UUID,
    world_id: UUID,
    skip: int = 0,
    limit: int = 20,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取道具列表"""
    service = WorldService(db)
    props, total = await service.list_props(world_id, skip=skip, limit=limit)
    return ApiResponse(data={
        "items": [PropResponse.model_validate(p).model_dump() for p in props],
        "total": total,
    })


@router.post("/{project_id}/worlds/{world_id}/props")
async def create_prop(
    project_id: UUID,
    world_id: UUID,
    data: PropCreate,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建道具"""
    service = WorldService(db)
    prop = await service.create_prop(world_id, data)
    return ApiResponse(data=PropResponse.model_validate(prop).model_dump())


@router.put("/{project_id}/worlds/{world_id}/props/{prop_id}")
async def update_prop(
    project_id: UUID,
    world_id: UUID,
    prop_id: UUID,
    data: PropUpdate,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新道具"""
    service = WorldService(db)
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    prop = await service.update_prop(prop_id, update_data)
    if prop is None:
        raise HTTPException(status_code=404, detail="道具不存在")
    return ApiResponse(data=PropResponse.model_validate(prop).model_dump())


@router.delete("/{project_id}/worlds/{world_id}/props/{prop_id}")
async def delete_prop(
    project_id: UUID,
    world_id: UUID,
    prop_id: UUID,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除道具"""
    service = WorldService(db)
    deleted = await service.delete_prop(prop_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="道具不存在")
    return ApiResponse(data={"deleted": True})


@router.post("/{project_id}/worlds/{world_id}/props/ai-extract")
async def ai_extract_props(
    project_id: UUID,
    world_id: UUID,
    data: ExtractScenesRequest,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """从小说文本中提取道具（后台任务，纳入任务中心管理）"""
    novel_text = data.novel_text
    if not novel_text:
        raise HTTPException(status_code=400, detail="请提供小说文本")
    existing = await find_running_task(db, project_id, TASK_AI_EXTRACT_PROPS)
    if existing:
        return ApiResponse(data={"task_id": str(existing.id), "message": "已有正在执行的提取道具任务"})
    tracker = await TaskProgressTracker.create(
        db, project_id, TASK_AI_EXTRACT_PROPS,
        "提取道具", {"world_id": str(world_id), "novel_text": novel_text}
    )
    spawn_background_task(
        tracker.task.id,
        _run_ai_extract_props(world_id, novel_text, tracker),
    )
    return ApiResponse(data={"task_id": str(tracker.task.id)})


@router.post("/{project_id}/worlds/{world_id}/props/{prop_id}/generate-image")
async def generate_prop_image(
    project_id: UUID,
    world_id: UUID,
    prop_id: UUID,
    user_id: str = Depends(get_current_user),  # D48: 补全认证
    db: AsyncSession = Depends(get_db),
):
    """生成道具图片（后台任务，纳入任务中心管理）"""
    existing = await find_running_task(db, project_id, TASK_GENERATE_PROP_IMAGE)
    if existing:
        return ApiResponse(data={"task_id": str(existing.id), "message": "已有正在执行的生成道具图片任务"})
    tracker = await TaskProgressTracker.create(
        db, project_id, TASK_GENERATE_PROP_IMAGE,
        "生成道具图片", {"world_id": str(world_id), "prop_id": str(prop_id)}
    )
    spawn_background_task(
        tracker.task.id,
        _run_generate_prop_image(world_id, prop_id, project_id, tracker),
    )
    return ApiResponse(data={"task_id": str(tracker.task.id)})


# ======================================================================
# 建筑
# ======================================================================


@router.get("/{project_id}/worlds/{world_id}/buildings")
async def list_buildings(
    project_id: UUID,
    world_id: UUID,
    skip: int = 0,
    limit: int = 20,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取建筑列表"""
    service = WorldService(db)
    buildings, total = await service.list_buildings(world_id, skip=skip, limit=limit)
    return ApiResponse(data={
        "items": [BuildingResponse.model_validate(b).model_dump() for b in buildings],
        "total": total,
    })


@router.post("/{project_id}/worlds/{world_id}/buildings")
async def create_building(
    project_id: UUID,
    world_id: UUID,
    data: BuildingCreate,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建建筑"""
    service = WorldService(db)
    building = await service.create_building(world_id, data)
    return ApiResponse(data=BuildingResponse.model_validate(building).model_dump())


@router.put("/{project_id}/worlds/{world_id}/buildings/{building_id}")
async def update_building(
    project_id: UUID,
    world_id: UUID,
    building_id: UUID,
    data: BuildingUpdate,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新建筑"""
    service = WorldService(db)
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    building = await service.update_building(building_id, update_data)
    if building is None:
        raise HTTPException(status_code=404, detail="建筑不存在")
    return ApiResponse(data=BuildingResponse.model_validate(building).model_dump())


@router.delete("/{project_id}/worlds/{world_id}/buildings/{building_id}")
async def delete_building(
    project_id: UUID,
    world_id: UUID,
    building_id: UUID,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除建筑"""
    service = WorldService(db)
    deleted = await service.delete_building(building_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="建筑不存在")
    return ApiResponse(data={"deleted": True})


@router.post("/{project_id}/worlds/{world_id}/buildings/ai-extract")
async def ai_extract_buildings(
    project_id: UUID,
    world_id: UUID,
    data: ExtractScenesRequest,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """从小说文本中提取建筑（后台任务，纳入任务中心管理）"""
    novel_text = data.novel_text
    if not novel_text:
        raise HTTPException(status_code=400, detail="请提供小说文本")
    existing = await find_running_task(db, project_id, TASK_AI_EXTRACT_BUILDINGS)
    if existing:
        return ApiResponse(data={"task_id": str(existing.id), "message": "已有正在执行的提取建筑任务"})
    tracker = await TaskProgressTracker.create(
        db, project_id, TASK_AI_EXTRACT_BUILDINGS,
        "提取建筑", {"world_id": str(world_id), "novel_text": novel_text}
    )
    spawn_background_task(
        tracker.task.id,
        _run_ai_extract_buildings(world_id, novel_text, tracker),
    )
    return ApiResponse(data={"task_id": str(tracker.task.id)})


@router.post("/{project_id}/worlds/{world_id}/buildings/{building_id}/generate-image")
async def generate_building_image(
    project_id: UUID,
    world_id: UUID,
    building_id: UUID,
    user_id: str = Depends(get_current_user),  # D48: 补全认证
    db: AsyncSession = Depends(get_db),
):
    """生成建筑图片（后台任务，纳入任务中心管理）"""
    existing = await find_running_task(db, project_id, TASK_GENERATE_BUILDING_IMAGE)
    if existing:
        return ApiResponse(data={"task_id": str(existing.id), "message": "已有正在执行的生成建筑图片任务"})
    tracker = await TaskProgressTracker.create(
        db, project_id, TASK_GENERATE_BUILDING_IMAGE,
        "生成建筑图片", {"world_id": str(world_id), "building_id": str(building_id)}
    )
    spawn_background_task(
        tracker.task.id,
        _run_generate_building_image(world_id, building_id, project_id, tracker),
    )
    return ApiResponse(data={"task_id": str(tracker.task.id)})


# ======================================================================
# 服装
# ======================================================================


@router.get("/{project_id}/worlds/{world_id}/outfits")
async def list_outfits(
    project_id: UUID,
    world_id: UUID,
    skip: int = 0,
    limit: int = 20,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取服装列表"""
    service = WorldService(db)
    outfits, total = await service.list_outfits(world_id, skip=skip, limit=limit)
    return ApiResponse(data={
        "items": [OutfitResponse.model_validate(o).model_dump() for o in outfits],
        "total": total,
    })


@router.post("/{project_id}/worlds/{world_id}/outfits")
async def create_outfit(
    project_id: UUID,
    world_id: UUID,
    data: OutfitCreate,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建服装"""
    service = WorldService(db)
    outfit = await service.create_outfit(world_id, data)
    return ApiResponse(data=OutfitResponse.model_validate(outfit).model_dump())


@router.put("/{project_id}/worlds/{world_id}/outfits/{outfit_id}")
async def update_outfit(
    project_id: UUID,
    world_id: UUID,
    outfit_id: UUID,
    data: OutfitUpdate,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新服装"""
    service = WorldService(db)
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    outfit = await service.update_outfit(outfit_id, update_data)
    if outfit is None:
        raise HTTPException(status_code=404, detail="服装不存在")
    return ApiResponse(data=OutfitResponse.model_validate(outfit).model_dump())


@router.delete("/{project_id}/worlds/{world_id}/outfits/{outfit_id}")
async def delete_outfit(
    project_id: UUID,
    world_id: UUID,
    outfit_id: UUID,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除服装"""
    service = WorldService(db)
    deleted = await service.delete_outfit(outfit_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="服装不存在")
    return ApiResponse(data={"deleted": True})


@router.post("/{project_id}/worlds/{world_id}/outfits/ai-extract")
async def ai_extract_outfits(
    project_id: UUID,
    world_id: UUID,
    data: ExtractScenesRequest,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """从小说文本中提取服装（后台任务，纳入任务中心管理）"""
    novel_text = data.novel_text
    if not novel_text:
        raise HTTPException(status_code=400, detail="请提供小说文本")
    existing = await find_running_task(db, project_id, TASK_AI_EXTRACT_OUTFITS)
    if existing:
        return ApiResponse(data={"task_id": str(existing.id), "message": "已有正在执行的提取服装任务"})
    tracker = await TaskProgressTracker.create(
        db, project_id, TASK_AI_EXTRACT_OUTFITS,
        "提取服装", {"world_id": str(world_id), "novel_text": novel_text}
    )
    spawn_background_task(
        tracker.task.id,
        _run_ai_extract_outfits(world_id, novel_text, tracker),
    )
    return ApiResponse(data={"task_id": str(tracker.task.id)})


@router.post("/{project_id}/worlds/{world_id}/outfits/{outfit_id}/generate-image")
async def generate_outfit_image(
    project_id: UUID,
    world_id: UUID,
    outfit_id: UUID,
    user_id: str = Depends(get_current_user),  # D48: 补全认证
    db: AsyncSession = Depends(get_db),
):
    """生成服装图片（后台任务，纳入任务中心管理）"""
    existing = await find_running_task(db, project_id, TASK_GENERATE_OUTFIT_IMAGE)
    if existing:
        return ApiResponse(data={"task_id": str(existing.id), "message": "已有正在执行的生成服装图片任务"})
    tracker = await TaskProgressTracker.create(
        db, project_id, TASK_GENERATE_OUTFIT_IMAGE,
        "生成服装图片", {"world_id": str(world_id), "outfit_id": str(outfit_id)}
    )
    spawn_background_task(
        tracker.task.id,
        _run_generate_outfit_image(world_id, outfit_id, project_id, tracker),
    )
    return ApiResponse(data={"task_id": str(tracker.task.id)})
