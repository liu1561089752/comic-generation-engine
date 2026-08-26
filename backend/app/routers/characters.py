from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from pydantic import BaseModel
from app.core.task_types import TASK_EXTRACT_CHARACTERS, TASK_GENERATE_CHARACTER_IMAGE, TASK_GENERATE_STATE_IMAGE
import logging

from app.core.database import get_db, async_session_factory
from app.middleware.auth import get_current_user
from app.modules.character.service import CharacterService
from app.infra.task_progress import TaskProgressTracker, find_running_task
from app.infra.task_registry import spawn_background_task
from app.infra.task_dispatcher import register_task_runner as _register
from app.infra.task_concurrency import get_image_task_semaphore
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
    CharacterStateUpdate,
)
from app.models.character import CharacterState

logger = logging.getLogger(__name__)


class ExtractCharactersRequest(BaseModel):
    novel_text: str

router = APIRouter()
global_router = APIRouter()


# ======================================================================
# 角色 AI 后台任务（提取角色 / 生成形象 / 生成状态形象）
# ======================================================================


async def _run_extract_characters(
    project_id: UUID, novel_text: str, tracker: TaskProgressTracker
):
    """一键提取角色后台任务 — service 内部短事务写库。"""
    try:
        await tracker.set_running("开始提取角色...")
        async with async_session_factory() as session:
            service = CharacterService(session)
            characters = await service.extract_characters_from_novel(project_id, novel_text)
        items = [
            CharacterResponse.model_validate(c).model_dump(mode="json") for c in characters
        ]
        await tracker.complete(
            {"items": items, "total": len(characters)},
            f"成功提取 {len(characters)} 个角色",
        )
    except Exception as e:
        logger.exception(f"提取角色任务失败: {e}")
        await tracker.fail(str(e))


async def _run_generate_character_image(
    project_id: UUID, character_id: UUID, tracker: TaskProgressTracker
):
    """生成角色形象后台任务。

    每类型最多 2 个并发（信号量），拿不到执行权时任务保持 queued 排队，
    前面的任务完成后自动补位。
    """
    async with get_image_task_semaphore(TASK_GENERATE_CHARACTER_IMAGE):
        try:
            await tracker.set_running("开始生成角色形象...")
            async with async_session_factory() as session:
                service = CharacterService(session)
                result = await service.generate_character_image(character_id, project_id)
            name = result.get("character_name", "")
            await tracker.complete(result, f"角色「{name}」形象已生成")
        except Exception as e:
            logger.exception(f"生成角色形象任务失败: {e}")
            await tracker.fail(str(e))


async def _run_generate_state_image(
    project_id: UUID, character_id: UUID, state_id: UUID, tracker: TaskProgressTracker
):
    """生成角色状态形象后台任务（每类型最多 2 个并发，其余排队）。"""
    async with get_image_task_semaphore(TASK_GENERATE_STATE_IMAGE):
        try:
            await tracker.set_running("开始生成状态形象...")
            async with async_session_factory() as session:
                service = CharacterService(session)
                result = await service.generate_state_image(character_id, state_id, project_id)
            name = result.get("state_name", "")
            await tracker.complete(result, f"状态「{name}」形象已生成")
        except Exception as e:
            logger.exception(f"生成状态形象任务失败: {e}")
            await tracker.fail(str(e))


# 注册任务执行器 — 供 retry 功能重新派发后台任务
@_register(TASK_EXTRACT_CHARACTERS)
async def _redispatch_extract_characters(task, tracker):
    novel_text = task.input_data.get("novel_text", "")
    await _run_extract_characters(task.project_id, novel_text, tracker)


@_register(TASK_GENERATE_CHARACTER_IMAGE)
async def _redispatch_generate_character_image(task, tracker):
    character_id = UUID(task.input_data["character_id"])
    await _run_generate_character_image(task.project_id, character_id, tracker)


@_register(TASK_GENERATE_STATE_IMAGE)
async def _redispatch_generate_state_image(task, tracker):
    character_id = UUID(task.input_data["character_id"])
    state_id = UUID(task.input_data["state_id"])
    await _run_generate_state_image(task.project_id, character_id, state_id, tracker)


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
    """从小说文本中提取角色（后台任务，纳入任务中心管理）"""
    if not data.novel_text:
        raise HTTPException(status_code=400, detail="请提供小说文本")
    logger.info(f"===== 路由收到提取请求, novel_text长度={len(data.novel_text)} =====")
    existing = await find_running_task(db, project_id, TASK_EXTRACT_CHARACTERS)
    if existing:
        return ApiResponse(data={"task_id": str(existing.id), "message": "已有正在执行的提取角色任务"})
    tracker = await TaskProgressTracker.create(
        db, project_id, TASK_EXTRACT_CHARACTERS,
        "提取角色", {"novel_text": data.novel_text}
    )
    spawn_background_task(
        tracker.task.id,
        _run_extract_characters(project_id, data.novel_text, tracker),
    )
    return ApiResponse(data={"task_id": str(tracker.task.id)})


@router.post("/{project_id}/characters/{character_id}/generate-image")
async def generate_character_image(
    project_id: UUID,
    character_id: UUID,
    user_id: str = Depends(get_current_user),  # D48: 补全认证
    db: AsyncSession = Depends(get_db),
):
    """生成角色形象（后台任务，纳入任务中心管理；每类型最多 2 个并发，其余排队）"""
    tracker = await TaskProgressTracker.create(
        db, project_id, TASK_GENERATE_CHARACTER_IMAGE,
        "生成角色形象", {"character_id": str(character_id)}
    )
    spawn_background_task(
        tracker.task.id,
        _run_generate_character_image(project_id, character_id, tracker),
    )
    return ApiResponse(data={"task_id": str(tracker.task.id)})


@router.post("/{project_id}/characters/{character_id}/states/{state_id}/generate-image")
async def generate_state_image(
    project_id: UUID,
    character_id: UUID,
    state_id: UUID,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """生成角色状态形象（以角色主图为参考，后台任务；每类型最多 2 个并发，其余排队）"""
    tracker = await TaskProgressTracker.create(
        db, project_id, TASK_GENERATE_STATE_IMAGE,
        "生成状态形象", {"character_id": str(character_id), "state_id": str(state_id)}
    )
    spawn_background_task(
        tracker.task.id,
        _run_generate_state_image(project_id, character_id, state_id, tracker),
    )
    return ApiResponse(data={"task_id": str(tracker.task.id)})


@router.put("/{project_id}/characters/{character_id}/states/{state_id}")
async def update_character_state(
    project_id: UUID,
    character_id: UUID,
    state_id: UUID,
    data: CharacterStateUpdate,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新角色状态的描述等信息（AI 提取后的人工修正）"""
    service = CharacterService(db)
    # 过滤掉 None 值的字段，避免把已有值覆盖为空
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    state = await service.update_state(character_id, state_id, update_data)
    if state is None:
        raise HTTPException(status_code=404, detail="角色状态不存在")
    return ApiResponse(data={
        "id": str(state.id),
        "character_id": str(state.character_id),
        "name": state.name,
        "aliases": state.aliases,
        "description": state.description,
        "sort_order": state.sort_order,
        "created_at": state.created_at.isoformat() if state.created_at else None,
        "updated_at": state.updated_at.isoformat() if state.updated_at else None,
    })
