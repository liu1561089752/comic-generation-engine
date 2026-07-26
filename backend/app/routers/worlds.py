from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from pydantic import BaseModel

from app.core.database import get_db
from app.middleware.auth import get_current_user
from app.modules.world.service import WorldService
from app.schemas.common import ApiResponse
from app.schemas.world_schema import (
    WorldBuildingCreate,
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
    StyleTemplateCreate,
    StyleTemplateUpdate,
    StyleTemplateResponse,
)

router = APIRouter()


class ExtractScenesRequest(BaseModel):
    novel_text: str


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
    """AI自动创建世界观（直接读取小说文本，自动保存到数据库）"""
    service = WorldService(db)
    novel_text = data.get("novel_text", "")
    if not novel_text:
        raise HTTPException(status_code=400, detail="请提供小说文本")
    try:
        world = await service.ai_create_world(project_id, novel_text)
        return ApiResponse(data=WorldBuildingResponse.model_validate(world).model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI自动创建失败: {str(e)}")


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


@router.post("/{project_id}/worlds")
async def create_world(
    project_id: UUID,
    data: WorldBuildingCreate,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建世界观"""
    service = WorldService(db)
    world = await service.create_world(project_id, data)
    return ApiResponse(data=WorldBuildingResponse.model_validate(world).model_dump())


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
    """从小说文本中提取场景资产"""
    service = WorldService(db)
    novel_text = data.novel_text
    if not novel_text:
        raise HTTPException(status_code=400, detail="请提供小说文本")
    try:
        assets = await service.ai_extract_scene_assets(world_id, novel_text)
        return ApiResponse(data={
            "items": [SceneAssetResponse.model_validate(a).model_dump() for a in assets],
            "total": len(assets),
        })
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI分析失败: {str(e)}")


@router.post("/{project_id}/worlds/{world_id}/scene-assets/{asset_id}/generate-image")
async def generate_scene_image(
    project_id: UUID,
    world_id: UUID,
    asset_id: UUID,
    user_id: str = Depends(get_current_user),  # D48: 补全认证
    db: AsyncSession = Depends(get_db),
):
    """生成场景资产图片"""
    service = WorldService(db)
    try:
        result = await service.generate_scene_image(asset_id, project_id)
        return ApiResponse(data=result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


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
    """从小说文本中提取道具"""
    service = WorldService(db)
    novel_text = data.novel_text
    if not novel_text:
        raise HTTPException(status_code=400, detail="请提供小说文本")
    try:
        props = await service.ai_extract_props(world_id, novel_text)
        return ApiResponse(data={
            "items": [PropResponse.model_validate(p).model_dump() for p in props],
            "total": len(props),
        })
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI分析失败: {str(e)}")


@router.post("/{project_id}/worlds/{world_id}/props/{prop_id}/generate-image")
async def generate_prop_image(
    project_id: UUID,
    world_id: UUID,
    prop_id: UUID,
    user_id: str = Depends(get_current_user),  # D48: 补全认证
    db: AsyncSession = Depends(get_db),
):
    """生成道具图片"""
    service = WorldService(db)
    try:
        result = await service.generate_prop_image(prop_id, project_id)
        return ApiResponse(data=result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


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
    """从小说文本中提取建筑"""
    service = WorldService(db)
    novel_text = data.novel_text
    if not novel_text:
        raise HTTPException(status_code=400, detail="请提供小说文本")
    try:
        buildings = await service.ai_extract_buildings(world_id, novel_text)
        return ApiResponse(data={
            "items": [BuildingResponse.model_validate(b).model_dump() for b in buildings],
            "total": len(buildings),
        })
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI分析失败: {str(e)}")


@router.post("/{project_id}/worlds/{world_id}/buildings/{building_id}/generate-image")
async def generate_building_image(
    project_id: UUID,
    world_id: UUID,
    building_id: UUID,
    user_id: str = Depends(get_current_user),  # D48: 补全认证
    db: AsyncSession = Depends(get_db),
):
    """生成建筑图片"""
    service = WorldService(db)
    try:
        result = await service.generate_building_image(building_id, project_id)
        return ApiResponse(data=result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


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
    """从小说文本中提取服装"""
    service = WorldService(db)
    novel_text = data.novel_text
    if not novel_text:
        raise HTTPException(status_code=400, detail="请提供小说文本")
    try:
        outfits = await service.ai_extract_outfits(world_id, novel_text)
        return ApiResponse(data={
            "items": [OutfitResponse.model_validate(o).model_dump() for o in outfits],
            "total": len(outfits),
        })
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI分析失败: {str(e)}")


@router.post("/{project_id}/worlds/{world_id}/outfits/{outfit_id}/generate-image")
async def generate_outfit_image(
    project_id: UUID,
    world_id: UUID,
    outfit_id: UUID,
    user_id: str = Depends(get_current_user),  # D48: 补全认证
    db: AsyncSession = Depends(get_db),
):
    """生成服装图片"""
    service = WorldService(db)
    try:
        result = await service.generate_outfit_image(outfit_id, project_id)
        return ApiResponse(data=result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


# ======================================================================
# 风格模板
# ======================================================================


@router.get("/{project_id}/style-templates")
async def list_templates(
    project_id: UUID,
    skip: int = 0,
    limit: int = 20,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取风格模板列表"""
    service = WorldService(db)
    templates, total = await service.list_templates(project_id, skip=skip, limit=limit)
    return ApiResponse(data={
        "items": [StyleTemplateResponse.model_validate(t).model_dump() for t in templates],
        "total": total,
        "skip": skip,
        "limit": limit,
    })


@router.post("/{project_id}/style-templates")
async def create_template(
    project_id: UUID,
    data: StyleTemplateCreate,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建风格模板"""
    service = WorldService(db)
    template = await service.create_template(project_id, data)
    return ApiResponse(data=StyleTemplateResponse.model_validate(template).model_dump())


@router.get("/{project_id}/style-templates/{template_id}")
async def get_template(
    project_id: UUID,
    template_id: UUID,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取风格模板详情"""
    service = WorldService(db)
    template = await service.get_template(template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="风格模板不存在")
    return ApiResponse(data=StyleTemplateResponse.model_validate(template).model_dump())


@router.put("/{project_id}/style-templates/{template_id}")
async def update_template(
    project_id: UUID,
    template_id: UUID,
    data: StyleTemplateUpdate,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新风格模板"""
    service = WorldService(db)
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    template = await service.update_template(project_id, template_id, update_data)
    if template is None:
        raise HTTPException(status_code=404, detail="风格模板不存在")
    return ApiResponse(data=StyleTemplateResponse.model_validate(template).model_dump())


@router.delete("/{project_id}/style-templates/{template_id}")
async def delete_template(
    project_id: UUID,
    template_id: UUID,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除风格模板"""
    service = WorldService(db)
    deleted = await service.delete_template(template_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="风格模板不存在")
    return ApiResponse(data={"deleted": True})


@router.post("/{project_id}/style-templates/{template_id}/set-default")
async def set_default_template(
    project_id: UUID,
    template_id: UUID,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """设为默认模板"""
    service = WorldService(db)
    template = await service.set_default_template(project_id, template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="风格模板不存在")
    return ApiResponse(data=StyleTemplateResponse.model_validate(template).model_dump())
