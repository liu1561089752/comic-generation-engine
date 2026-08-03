from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from pydantic import BaseModel

from app.core.database import get_db
from app.middleware.auth import get_current_user
from app.modules.character.service import CharacterService
from app.schemas.common import ApiResponse
from app.schemas.character_schema import (
    CharacterCreate,
    CharacterUpdate,
    CharacterResponse,
    CharacterDetailResponse,
    CharacterRelationCreate,
    CharacterRelationResponse,
    CharacterOutfitCreate,
    CharacterOutfitResponse,
    CharacterReferenceImageCreate,
    CharacterReferenceImageResponse,
)
from app.models.character import CharacterState


class ExtractCharactersRequest(BaseModel):
    novel_text: str

router = APIRouter()
global_router = APIRouter()


# ======================================================================
# 人物 CRUD
# ======================================================================


@router.get("/{project_id}/characters")
async def list_characters(
    project_id: UUID,
    skip: int = 0,
    limit: int = 20,
    search: str = Query(""),
    role_type: str = Query(""),
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取人物IP列表"""
    from sqlalchemy import select
    from app.models.character import CharacterReferenceImage, CharacterState
    service = CharacterService(db)
    characters, total = await service.list_characters(project_id, skip=skip, limit=limit, search=search, role_type=role_type)

    # 批量查询各角色的状态和默认形象图
    char_ids = [c.id for c in characters]
    states_result = await db.execute(
        select(CharacterState).where(CharacterState.character_id.in_(char_ids)).order_by(CharacterState.sort_order)
    )
    all_states = states_result.scalars().all()
    state_ids = [s.id for s in all_states]

    # 批量查询状态参考图
    state_ref_images = {}
    if state_ids:
        ref_r = await db.execute(
            select(CharacterReferenceImage).where(
                CharacterReferenceImage.character_id.in_(char_ids),
                CharacterReferenceImage.state_id.in_(state_ids),
            )
        )
        for ref in ref_r.scalars().all():
            if ref.state_id:
                state_ref_images[str(ref.state_id)] = ref.image_url

    states_map: dict = {}
    for s in all_states:
        cid = str(s.character_id)
        sid_str = str(s.id)
        states_map.setdefault(cid, []).append({
            "id": sid_str,
            "character_id": cid,
            "name": s.name,
            "aliases": s.aliases,
            "description": s.description,
            "sort_order": s.sort_order,
            "image_url": state_ref_images.get(sid_str),
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "updated_at": s.updated_at.isoformat() if s.updated_at else None,
        })

    items = []
    for c in characters:
        d = CharacterResponse.model_validate(c).model_dump()
        cid_str = str(c.id)
        d["states"] = states_map.get(cid_str, [])
        ref_result = await db.execute(
            select(CharacterReferenceImage).where(
                CharacterReferenceImage.character_id == c.id,
                CharacterReferenceImage.state_id.is_(None),
            ).limit(1)
        )
        ref_img = ref_result.scalar_one_or_none()
        if ref_img:
            d["image_url"] = ref_img.image_url
        items.append(d)
    return ApiResponse(data={
        "items": items,
        "total": total,
        "skip": skip,
        "limit": limit,
    })


@router.post("/{project_id}/characters")
async def create_character(
    project_id: UUID,
    data: CharacterCreate,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建人物IP"""
    service = CharacterService(db)
    try:
        character = await service.create_character(project_id, data)
        return ApiResponse(data=CharacterResponse.model_validate(character).model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{project_id}/characters/{character_id}")
async def get_character(
    project_id: UUID,
    character_id: UUID,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取人物详情"""
    from sqlalchemy import select
    service = CharacterService(db)
    character = await service.get_character(character_id)
    if character is None:
        raise HTTPException(status_code=404, detail="人物不存在")
    # 获取关联的服装、参考图和状态
    outfits, _ = await service.list_outfits(character_id)
    ref_images, _ = await service.list_reference_images(character_id)
    states_result = await db.execute(
        select(CharacterState).where(CharacterState.character_id == character_id).order_by(CharacterState.sort_order)
    )
    states = states_result.scalars().all()

    # 批量查询状态参考图
    from app.models.character import CharacterReferenceImage
    state_ids = [s.id for s in states]
    state_ref_images = {}
    if state_ids:
        ref_r = await db.execute(
            select(CharacterReferenceImage).where(
                CharacterReferenceImage.character_id == character_id,
                CharacterReferenceImage.state_id.in_(state_ids),
            )
        )
        for ref in ref_r.scalars().all():
            if ref.state_id:
                state_ref_images[str(ref.state_id)] = ref.image_url

    data = CharacterDetailResponse.model_validate(character).model_dump()
    data["outfits"] = [CharacterOutfitResponse.model_validate(o).model_dump() for o in outfits]
    data["reference_images"] = [CharacterReferenceImageResponse.model_validate(r).model_dump() for r in ref_images]
    data["states"] = [
        {
            "id": str(s.id),
            "character_id": str(s.character_id),
            "name": s.name,
            "aliases": s.aliases,
            "description": s.description,
            "sort_order": s.sort_order,
            "image_url": state_ref_images.get(str(s.id)),
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "updated_at": s.updated_at.isoformat() if s.updated_at else None,
        }
        for s in states
    ]
    return ApiResponse(data=data)


@router.put("/{project_id}/characters/{character_id}")
async def update_character(
    project_id: UUID,
    character_id: UUID,
    data: CharacterUpdate,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新人物IP"""
    service = CharacterService(db)
    # 过滤掉 None 值的字段，避免把已有值覆盖为空
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    character = await service.update_character(character_id, update_data)
    if character is None:
        raise HTTPException(status_code=404, detail="人物不存在")
    return ApiResponse(data=CharacterResponse.model_validate(character).model_dump())


@router.delete("/{project_id}/characters/{character_id}")
async def delete_character(
    project_id: UUID,
    character_id: UUID,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除人物IP"""
    service = CharacterService(db)
    deleted = await service.delete_character(character_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="人物不存在")
    return ApiResponse(data={"deleted": True})


# ======================================================================
# 全局路由（不依赖项目ID）
# ======================================================================


@global_router.get("")
async def list_all_characters(
    skip: int = 0,
    limit: int = 20,
    search: str = Query(""),
    role_type: str = Query(""),
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户所有项目的角色列表"""
    from app.models.novel import Project
    service = CharacterService(db)
    characters, total = await service.list_all_characters(
        skip=skip, limit=limit, search=search, role_type=role_type,
        project_ids_query=select(Project.id).where(Project.user_id == user_id),
    )
    return ApiResponse(data={
        "items": [
            CharacterResponse.model_validate(c).model_dump() for c in characters
        ],
        "total": total,
        "skip": skip,
        "limit": limit,
    })


# ======================================================================
# 人物关系
# ======================================================================


@router.get("/{project_id}/characters/{character_id}/relations")
async def list_relations(
    project_id: UUID,
    character_id: UUID,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取人物关系列表"""
    service = CharacterService(db)
    relations = await service.list_relations(character_id)
    return ApiResponse(data={
        "items": [
            CharacterRelationResponse.model_validate(r).model_dump() for r in relations
        ],
        "total": len(relations),
    })


@router.post("/{project_id}/characters/{character_id}/relations")
async def create_relation(
    project_id: UUID,
    character_id: UUID,
    data: CharacterRelationCreate,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建人物关系"""
    service = CharacterService(db)
    # 校验关联的角色是否存在
    target_char = await service.get_character(data.character_b_id)
    if target_char is None:
        raise HTTPException(status_code=404, detail="关联的目标人物不存在")
    relation = await service.create_relation(project_id, character_id, data)
    return ApiResponse(data=CharacterRelationResponse.model_validate(relation).model_dump())


# ======================================================================
# 人物服装
# ======================================================================


@router.get("/{project_id}/characters/{character_id}/outfits")
async def list_outfits(
    project_id: UUID,
    character_id: UUID,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取人物服装列表"""
    service = CharacterService(db)
    outfits, total = await service.list_outfits(character_id)
    return ApiResponse(data={
        "items": [
            CharacterOutfitResponse.model_validate(o).model_dump() for o in outfits
        ],
        "total": total,
    })


@router.post("/{project_id}/characters/{character_id}/outfits")
async def create_outfit(
    project_id: UUID,
    character_id: UUID,
    data: CharacterOutfitCreate,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """添加人物服装"""
    service = CharacterService(db)
    outfit = await service.create_outfit(character_id, data)
    return ApiResponse(data=CharacterOutfitResponse.model_validate(outfit).model_dump())


# ======================================================================
# 人物参考图
# ======================================================================


@router.get("/{project_id}/characters/{character_id}/reference-images")
async def list_reference_images(
    project_id: UUID,
    character_id: UUID,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取人物参考图列表"""
    service = CharacterService(db)
    images, total = await service.list_reference_images(character_id)
    return ApiResponse(data={
        "items": [
            CharacterReferenceImageResponse.model_validate(img).model_dump() for img in images
        ],
        "total": total,
    })


@router.post("/{project_id}/characters/{character_id}/reference-images")
async def create_reference_image(
    project_id: UUID,
    character_id: UUID,
    data: CharacterReferenceImageCreate,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """上传人物参考图"""
    service = CharacterService(db)
    image = await service.create_reference_image(character_id, data)
    return ApiResponse(data=CharacterReferenceImageResponse.model_validate(image).model_dump())


@router.post("/{project_id}/characters/extract")
async def extract_characters(
    project_id: UUID,
    data: ExtractCharactersRequest,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """从小说文本中提取角色"""
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"===== 路由收到提取请求, novel_text长度={len(data.novel_text)} =====")
    service = CharacterService(db)
    try:
        characters = await service.extract_characters_from_novel(project_id, data.novel_text)
        return ApiResponse(data={
            "items": [
                CharacterResponse.model_validate(c).model_dump() for c in characters
            ],
            "total": len(characters),
        })
    except ValueError as e:
        logger.info(f"===== 路由捕获 ValueError: {e} =====")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{project_id}/characters/{character_id}/generate-image")
async def generate_character_image(
    project_id: UUID,
    character_id: UUID,
    user_id: str = Depends(get_current_user),  # D48: 补全认证
    db: AsyncSession = Depends(get_db),
):
    """生成角色形象"""
    service = CharacterService(db)
    try:
        result = await service.generate_character_image(character_id, project_id)
        return ApiResponse(data=result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/{project_id}/characters/{character_id}/states/{state_id}/generate-image")
async def generate_state_image(
    project_id: UUID,
    character_id: UUID,
    state_id: UUID,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """生成角色状态形象（以角色主图为参考）"""
    service = CharacterService(db)
    try:
        result = await service.generate_state_image(character_id, state_id, project_id)
        return ApiResponse(data=result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
