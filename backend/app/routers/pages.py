from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.core.database import get_db
from app.middleware.auth import get_current_user
from app.modules.page.service import PageService
from app.schemas.common import ApiResponse
from app.schemas.scene_schema import (
    PageCreate,
    PageUpdate,
    PageResponse,
    AutoLayoutRequest,
)

router = APIRouter()


@router.get("/{project_id}/pages")
async def list_pages(
    project_id: UUID,
    chapter_id: Optional[UUID] = Query(None, description="按章节筛选"),
    skip: int = 0,
    limit: int = 50,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取页面列表"""
    service = PageService(db)
    pages, total = await service.list_pages(project_id, chapter_id=chapter_id, skip=skip, limit=limit)
    return ApiResponse(data={
        "items": [PageResponse.model_validate(p).model_dump() for p in pages],
        "total": total,
        "skip": skip,
        "limit": limit,
    })


@router.post("/{project_id}/pages")
async def create_page(
    project_id: UUID,
    data: PageCreate,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建页面"""
    service = PageService(db)
    page = await service.create_page(data)
    return ApiResponse(data=PageResponse.model_validate(page).model_dump())


@router.get("/{project_id}/pages/{page_id}")
async def get_page_detail(
    project_id: UUID,
    page_id: UUID,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取页面详情"""
    service = PageService(db)
    page = await service.get_page(page_id)
    if page is None:
        raise HTTPException(status_code=404, detail="页面不存在")
    return ApiResponse(data=PageResponse.model_validate(page).model_dump())


@router.put("/{project_id}/pages/{page_id}")
async def update_page_layout(
    project_id: UUID,
    page_id: UUID,
    data: PageUpdate,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新页面布局"""
    service = PageService(db)
    page = await service.update_page(page_id, data)
    if page is None:
        raise HTTPException(status_code=404, detail="页面不存在")
    return ApiResponse(data=PageResponse.model_validate(page).model_dump())


@router.delete("/{project_id}/pages/{page_id}")
async def delete_page(
    project_id: UUID,
    page_id: UUID,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除页面"""
    service = PageService(db)
    deleted = await service.delete_page(page_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="页面不存在")
    return ApiResponse(data={"deleted": True})


@router.post("/{project_id}/pages/auto-layout")
async def auto_layout_pages(
    project_id: UUID,
    data: AutoLayoutRequest,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """自动版式规划：为页面分配布局模板"""
    service = PageService(db)
    pages = await service.auto_layout(data)
    return ApiResponse(data={
        "items": [PageResponse.model_validate(p).model_dump() for p in pages],
        "total": len(pages),
    })
