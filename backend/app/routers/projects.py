import asyncio
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.config import settings
from app.middleware.auth import get_current_user
from app.repositories.novel_repo import ProjectRepository, NovelRepository, ChapterRepository
from app.core.base_repository import BaseRepository
from app.models.world import WorldBuilding
from app.models.character import Character
from app.schemas.common import ApiResponse
from app.schemas.project_schema import (
    CreateProjectRequest,
    UpdateProjectRequest,
    DuplicateProjectRequest,
)
from app.routers.dashboard import _get_production_stages

router = APIRouter()


@router.get("/check-name")
async def check_project_name(
    name: str = Query(..., min_length=1, description="项目名称"),
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """检查项目名称是否已存在（重名检测）"""
    project_repo = ProjectRepository(db)
    existing = await project_repo.get_by_name(name, user_id=user_id)
    return ApiResponse(data={"exists": existing is not None})


def _serialize_project(p) -> dict:
    return {
        "id": str(p.id),
        "name": p.name,
        "description": p.description,
        "project_type": p.project_type,
        "status": p.status,
        "cover_image_url": p.cover_image_url,
        "archived_at": p.archived_at.isoformat() if p.archived_at else None,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


def _check_project_owner(project, user_id: str):
    """校验项目归属。归属为空（历史数据）时一律拒绝，不做放行"""
    if str(project.user_id or "") != user_id:
        raise HTTPException(status_code=403, detail="无权访问该项目")


@router.get("")
async def list_projects(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=999, description="每页数量"),
    status: Optional[str] = Query(None, description="筛选状态: active/completed/archived"),
    project_type: Optional[str] = Query(None, alias="type", description="筛选项目类型"),
    date_from: Optional[str] = Query(None, description="创建日期起始 (ISO格式)"),
    date_to: Optional[str] = Query(None, description="创建日期结束 (ISO格式)"),
    sort: str = Query("updated_at", description="排序字段: updated_at/created_at/name"),
    order: str = Query("desc", description="排序方向: asc/desc"),
    view: str = Query("list", description="视图模式: list/grid/compact"),
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取项目列表（支持筛选、排序、分页）"""
    dt_from = None
    if date_from:
        try:
            dt_from = datetime.fromisoformat(date_from)
        except ValueError:
            raise HTTPException(status_code=400, detail="date_from 格式无效，请使用 ISO 格式")
    dt_to = None
    if date_to:
        try:
            dt_to = datetime.fromisoformat(date_to)
        except ValueError:
            raise HTTPException(status_code=400, detail="date_to 格式无效，请使用 ISO 格式")

    allowed_sorts = {"updated_at", "created_at", "name"}
    if sort not in allowed_sorts:
        raise HTTPException(status_code=400, detail=f"排序字段仅支持: {', '.join(sorted(allowed_sorts))}")

    if order not in ("asc", "desc"):
        raise HTTPException(status_code=400, detail="排序方向仅支持 asc 或 desc")

    project_repo = ProjectRepository(db)
    skip = (page - 1) * page_size
    projects, total = await project_repo.list_filtered(
        skip=skip,
        limit=page_size,
        status=status,
        project_type=project_type,
        date_from=dt_from,
        date_to=dt_to,
        sort=sort,
        order=order,
        user_id=user_id,
    )
    return ApiResponse(data={
        "items": [_serialize_project(p) for p in projects],
        "total": total,
        "page": page,
        "page_size": page_size,
        "view": view,
    })


@router.post("")
async def create_project(
    data: CreateProjectRequest,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建项目"""
    project_repo = ProjectRepository(db)
    project = await project_repo.create(
        name=data.name,
        description=data.description,
        project_type=data.project_type or "comic",
        status=data.status or "draft",
        user_id=user_id,
    )
    return ApiResponse(data=_serialize_project(project))


@router.get("/{project_id}")
async def get_project(
    project_id: UUID,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取项目详情（含生产进度）"""
    project_repo = ProjectRepository(db)
    project = await project_repo.get(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    _check_project_owner(project, user_id)
    progress = await project_repo.get_production_progress(project_id)
    # 8 工序生产进度（与工作台生产进度概览同一套算法）
    stages = await _get_production_stages(db, project_id)
    progress["stages"] = stages
    progress["overall_progress"] = sum(s["weight"] for s in stages if s["completed"])
    data = _serialize_project(project)
    data["production_progress"] = progress
    return ApiResponse(data=data)


@router.put("/{project_id}")
async def update_project(
    project_id: UUID,
    data: UpdateProjectRequest,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新项目"""
    project_repo = ProjectRepository(db)
    project = await project_repo.get(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    _check_project_owner(project, user_id)
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    project = await project_repo.update(project_id, **update_data)
    return ApiResponse(data=_serialize_project(project))


@router.delete("/{project_id}")
async def delete_project(
    project_id: UUID,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除项目（同时清理本地存储的图片文件）"""
    project_repo = ProjectRepository(db)
    project = await project_repo.get(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    _check_project_owner(project, user_id)

    import os
    import shutil
    try:
        storage_base = settings.STORAGE_LOCAL_PATH
        if not os.path.isabs(storage_base):
            storage_base = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                storage_base
            )
        project_storage_dir = os.path.join(storage_base, str(project_id))
        if os.path.isdir(project_storage_dir):
            await asyncio.to_thread(shutil.rmtree, project_storage_dir, ignore_errors=True)
    except Exception:
        pass

    await db.delete(project)
    await db.commit()

    return ApiResponse(message="删除成功")


@router.post("/{project_id}/archive")
async def archive_project(
    project_id: UUID,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """归档项目"""
    project_repo = ProjectRepository(db)
    project = await project_repo.get(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    _check_project_owner(project, user_id)
    project = await project_repo.archive(project_id)
    return ApiResponse(data=_serialize_project(project), message="项目已归档")


@router.post("/{project_id}/restore")
async def restore_project(
    project_id: UUID,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """恢复归档"""
    project_repo = ProjectRepository(db)
    project = await project_repo.get(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    _check_project_owner(project, user_id)
    project = await project_repo.restore(project_id)
    return ApiResponse(data=_serialize_project(project), message="项目已恢复")


@router.post("/{project_id}/duplicate")
async def duplicate_project(
    project_id: UUID,
    data: DuplicateProjectRequest,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """复制项目，可选择复制哪些内容"""
    project_repo = ProjectRepository(db)
    original = await project_repo.get(project_id)
    if original is None:
        raise HTTPException(status_code=404, detail="原项目不存在")
    _check_project_owner(original, user_id)

    new_project = await project_repo.create(
        name=data.new_name,
        description=original.description,
        project_type=original.project_type,
        status="draft",
        user_id=user_id,
    )

    if data.copy_world_settings:
        world_repo = BaseRepository(WorldBuilding, db)
        worlds = await world_repo.list_all(project_id=project_id)
        for w in worlds:
            await world_repo.create(
                project_id=new_project.id,
                name=w.name,
                era=w.era,
                description=w.description,
                settings=w.settings,
            )

    if data.copy_characters:
        char_repo = BaseRepository(Character, db)
        chars = await char_repo.list_all(project_id=project_id)
        for c in chars:
            await char_repo.create(
                project_id=new_project.id,
                name=c.name,
                aliases=c.aliases,
                description=c.description,
                role_type=c.role_type,
                stable_key=c.stable_key,
                status="active",
            )

    if data.copy_novel:
        novel_repo = NovelRepository(db)
        chapter_repo = ChapterRepository(db)
        # 每项目仅允许一本小说：复制时只取源项目的第一本
        novels = await novel_repo.list_all(project_id=project_id)
        for n in novels[:1]:
            new_novel = await novel_repo.create(
                project_id=new_project.id,
                title=n.title,
                author=n.author,
                raw_text=n.raw_text,
                cleaned_text=n.cleaned_text,
                word_count=n.word_count,
                format=n.format,
            )
            chapters = await chapter_repo.list_all(novel_id=n.id)
            for ch in chapters:
                await chapter_repo.create(
                    novel_id=new_novel.id,
                    chapter_number=ch.chapter_number,
                    title=ch.title,
                    content=ch.content,
                    status="pending",
                )

    return ApiResponse(
        data=_serialize_project(new_project),
        message=f"项目已复制为「{data.new_name}」",
    )
