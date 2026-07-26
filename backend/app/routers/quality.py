from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.core.database import get_db
from app.middleware.auth import get_current_user
from app.modules.quality.service import QualityService
from app.schemas.common import ApiResponse


class QualityReportRequest(BaseModel):
    scope: str = "all"
    panel_ids: Optional[list[str]] = None


class ImageReviewRequest(BaseModel):
    note: str = ""


router = APIRouter()


@router.post("/{project_id}/images/{image_id}/check-consistency")
async def check_consistency(
    project_id: UUID,
    image_id: UUID,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """启动一致性检测：比对角色外观特征与人物 IP 设定"""
    # Image 模型已删除，返回空结果
    return ApiResponse(data={})


@router.get("/{project_id}/images/{image_id}/consistency-report")
async def get_consistency_report(
    project_id: UUID,
    image_id: UUID,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取一致性检测报告"""
    # Image 模型已删除，返回空结果
    return ApiResponse(data={})


@router.post("/{project_id}/images/{image_id}/quality-score")
async def score_quality(
    project_id: UUID,
    image_id: UUID,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """AI 质量评分：多维度质量评估"""
    # Image 模型已删除，返回空结果
    return ApiResponse(data={})


@router.get("/{project_id}/quality-check/pending")
async def list_pending_reviews(
    project_id: UUID,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取待审核的 Panel 列表"""
    service = QualityService(db)
    panels = await service.list_pending_reviews(project_id)
    return ApiResponse(data={
        "items": [
            {
                "id": str(p.id),
                "panel_number": p.panel_number,
                "status": p.status,
                "scene_id": str(p.scene_id) if p.scene_id else None,
            }
            for p in panels
        ],
        "total": len(panels),
    })


@router.post("/{project_id}/quality-check/{panel_id}/review")
async def submit_review(
    project_id: UUID,
    panel_id: UUID,
    action: str = Query(..., description="审核动作: approve/reject/rework"),
    note: str = Query("", description="审核备注"),
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """提交审核结果"""
    service = QualityService(db)
    result = await service.submit_review(panel_id, action, note)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return ApiResponse(data=result)


# ========== 新增 Type 12 质量报告端点 ==========


@router.get("/{project_id}/quality/reports")
async def list_quality_reports(
    project_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取质量检测报告列表"""
    service = QualityService(db)
    reports = await service.list_reports(project_id, skip, limit)
    return ApiResponse(data=reports)


@router.get("/{project_id}/quality/reports/{report_id}")
async def get_quality_report_detail(
    project_id: UUID,
    report_id: UUID,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取质量检测报告详情"""
    service = QualityService(db)
    report = await service.get_report_detail(report_id)
    if "error" in report:
        raise HTTPException(status_code=404, detail=report["error"])
    return ApiResponse(data=report)


@router.post("/{project_id}/quality/reports")
async def trigger_quality_report(
    project_id: UUID,
    body: QualityReportRequest,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """触发质量检测：一致性 + 质量评分"""
    service = QualityService(db)
    scope = body.scope  # all, consistency, quality
    panel_ids = body.panel_ids
    result = await service.create_report(project_id, scope, panel_ids)
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return ApiResponse(data=result)


@router.post("/{project_id}/quality/{image_id}/approve")
async def approve_image(
    project_id: UUID,
    image_id: UUID,
    body: ImageReviewRequest = ImageReviewRequest(),
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """审核通过图片"""
    service = QualityService(db)
    result = await service.approve_image(image_id, body.note)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return ApiResponse(data=result)


@router.post("/{project_id}/quality/{image_id}/reject")
async def reject_image(
    project_id: UUID,
    image_id: UUID,
    body: ImageReviewRequest = ImageReviewRequest(),
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """审核打回图片"""
    service = QualityService(db)
    result = await service.reject_image(image_id, body.note)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return ApiResponse(data=result)
