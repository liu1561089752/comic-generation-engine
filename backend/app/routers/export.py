from uuid import UUID

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.middleware.auth import get_current_user
from app.schemas.common import ApiResponse
from app.modules.export.service import ExportService


class ExportRequest(BaseModel):
    # 默认值必须与前端传值（exportApi.ExportParams.format）及 ExportService 的分支判断一致，
    # 否则不传 format 时长图分支永远走不到。
    format: str = "long_image"
    chapter_id: Optional[UUID] = None
    quality: int = 90
    add_alias: bool = False
    alias_name: str = ""


router = APIRouter()


@router.post("/{project_id}/export")
async def export_project(
    project_id: UUID,
    body: ExportRequest,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """导出项目"""
    service = ExportService(db)
    result = await service.create_export_task(
        project_id,
        body.format,
        chapter_id=body.chapter_id,
        quality=body.quality,
        add_alias=body.add_alias,
        alias_name=body.alias_name,
    )
    return ApiResponse(data=result)


@router.get("/{project_id}/export/history")
async def list_exports(
    project_id: UUID,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取项目的导出历史"""
    service = ExportService(db)
    result = await service.list_exports(project_id)
    return ApiResponse(data=result)


@router.get("/{project_id}/export/{export_id}")
async def get_export_status(
    project_id: UUID,
    export_id: UUID,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取导出任务状态"""
    service = ExportService(db)
    try:
        result = await service.get_export_status(export_id)
        return ApiResponse(data=result)
    except ValueError as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{project_id}/export/{export_id}/cancel")
async def cancel_export(
    project_id: UUID,
    export_id: UUID,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """取消导出任务"""
    service = ExportService(db)
    result = await service.cancel_export(export_id)
    return ApiResponse(data=result)

@router.get("/{project_id}/export/{export_id}/progress")
async def export_progress(
    project_id: UUID,
    export_id: UUID,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取导出进度"""
    service = ExportService(db)
    result = await service.get_export_status(export_id)
    return ApiResponse(data=result)

@router.get("/{project_id}/export/{export_id}/download")
async def download_export(
    project_id: UUID,
    export_id: UUID,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """下载导出文件"""
    service = ExportService(db)
    try:
        file_path, filename = await service.download_export(export_id)
        return FileResponse(file_path, filename=filename)
    except ValueError as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=str(e))
