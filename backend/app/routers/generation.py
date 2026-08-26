"""图片生成相关路由。

C1 重构：废弃 Panel 生图流程，LayoutPage 生图路由已在 novels.py 中接入。
本路由仅保留通用的任务状态查询。
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.core.database import get_db
from app.middleware.auth import get_current_user
from app.repositories.task_repo import TaskRepository
from app.schemas.common import ApiResponse

router = APIRouter()


@router.get("/{project_id}/tasks/{task_id}/status")
async def get_task_status(
    project_id: UUID,
    task_id: UUID,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """查询生成任务状态"""
    task_repo = TaskRepository(db)
    task = await task_repo.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.project_id != project_id:
        raise HTTPException(status_code=404, detail="任务不存在")
    return ApiResponse(data={
        "task_id": str(task.id),
        "task_type": task.task_type,
        "status": task.status,
        "progress": task.progress,
        "error_message": task.error_message,
        "output_data": task.output_data,
        # 流式输出（生成脚本等任务实时文本），前端增量读取
        "stream_output": task.stream_output or "",
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
    })
