from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, desc, update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.core.database import get_db
from app.middleware.auth import get_current_user
from app.repositories.task_repo import TaskRepository
from app.models.task import Task
from pydantic import BaseModel

from app.schemas.common import ApiResponse
from app.infra.task_registry import cancel_background_task, spawn_background_task
from app.infra.task_progress import TaskProgressTracker
from app.infra.task_dispatcher import get_task_runner, redispatch_task


class BatchIdsRequest(BaseModel):
    task_ids: list[str]


router = APIRouter()
global_router = APIRouter()


def _task_to_dict(task: Task) -> dict:
    return {
        "id": str(task.id),
        "project_id": str(task.project_id) if task.project_id else None,
        "task_type": task.task_type,
        "status": task.status,
        "priority": task.priority,
        "progress": task.progress,
        "input_data": task.input_data,
        "output_data": task.output_data,
        "logs": task.logs or [],
        "error_message": task.error_message,
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
    }


# ─────────────────────────────────────────────
# 项目级任务路由（向后兼容）
# ─────────────────────────────────────────────

@router.get("/{project_id}/tasks")
async def list_tasks(
    project_id: UUID,
    task_type: Optional[str] = Query(None, description="按任务类型筛选"),
    status: Optional[str] = Query(None, description="按状态筛选"),
    priority: Optional[str] = Query(None, description="按优先级筛选"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取任务列表（可按类型/状态/优先级筛选）"""
    repo = TaskRepository(db)
    filters = {"project_id": project_id}
    if task_type:
        filters["task_type"] = task_type
    if status:
        filters["status"] = status
    if priority:
        filters["priority"] = priority

    tasks, total = await repo.list(skip=skip, limit=limit, **filters)
    return ApiResponse(data={
        "items": [_task_to_dict(t) for t in tasks],
        "total": total,
        "skip": skip,
        "limit": limit,
    })


@router.get("/{project_id}/tasks/{task_id}")
async def get_task_detail(
    project_id: UUID,
    task_id: UUID,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取任务详情"""
    repo = TaskRepository(db)
    task = await repo.get(task_id)
    if task is None or task.project_id != project_id:
        raise HTTPException(status_code=404, detail="任务不存在")
    return ApiResponse(data=_task_to_dict(task))


@router.post("/{project_id}/tasks/{task_id}/cancel")
async def cancel_task(
    project_id: UUID,
    task_id: UUID,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """取消任务"""
    repo = TaskRepository(db)
    task = await repo.get(task_id)
    if task is None or task.project_id != project_id:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.status not in ("queued", "running"):
        raise HTTPException(status_code=400, detail=f"当前状态 '{task.status}' 不允许取消")

    # D39: 同时取消运行中的协程，不只是改 DB 状态
    await cancel_background_task(task_id)
    task = await repo.update(task_id, status="cancelled")
    return ApiResponse(data=_task_to_dict(task))


@router.post("/{project_id}/tasks/{task_id}/retry")
async def retry_task(
    project_id: UUID,
    task_id: UUID,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """重试任务"""
    repo = TaskRepository(db)
    task = await repo.get(task_id)
    if task is None or task.project_id != project_id:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.status != "failed":
        raise HTTPException(status_code=400, detail=f"当前状态 '{task.status}' 不允许重试")

    runner = get_task_runner(task.task_type)
    if runner is None:
        raise HTTPException(
            status_code=400,
            detail=f"任务类型 '{task.task_type}' 不支持重试"
        )

    task = await repo.update(
        task_id,
        status="queued",
        progress=0,
        error_message=None,
        started_at=None,
        completed_at=None,
    )
    await db.commit()

    tracker = TaskProgressTracker(task)
    spawn_background_task(task_id, redispatch_task(task, tracker))
    return ApiResponse(data=_task_to_dict(task))


# ─────────────────────────────────────────────
# 全局任务路由（提供给任务中心使用）
# ─────────────────────────────────────────────

@global_router.get("")
async def list_all_tasks(
    task_type: Optional[str] = Query(None, description="按任务类型筛选"),
    status: Optional[str] = Query(None, description="按状态筛选"),
    priority: Optional[str] = Query(None, description="按优先级筛选"),
    project_id: Optional[UUID] = Query(None, description="按项目筛选"),
    date_from: Optional[str] = Query(None, description="开始时间范围（起始）"),
    date_to: Optional[str] = Query(None, description="开始时间范围（结束）"),
    sort_by: Optional[str] = Query("created_at", description="排序字段"),
    sort_order: Optional[str] = Query("desc", description="排序方向"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """增强的任务列表，支持多维度筛选和排序（仅当前用户项目的任务）"""
    from app.models.novel import Project
    repo = TaskRepository(db)
    query = select(Task)
    count_query = select(func.count()).select_from(Task)

    # 仅当前用户项目的任务
    user_project_ids = select(Project.id).where(Project.user_id == user_id)
    query = query.where(Task.project_id.in_(user_project_ids))
    count_query = count_query.where(Task.project_id.in_(user_project_ids))

    if task_type:
        query = query.where(Task.task_type == task_type)
        count_query = count_query.where(Task.task_type == task_type)
    if status:
        query = query.where(Task.status == status)
        count_query = count_query.where(Task.status == status)
    if priority:
        query = query.where(Task.priority == priority)
        count_query = count_query.where(Task.priority == priority)
    if project_id:
        query = query.where(Task.project_id == project_id)
        count_query = count_query.where(Task.project_id == project_id)
    if date_from:
        try:
            dt_from = datetime.fromisoformat(date_from)
            query = query.where(Task.created_at >= dt_from)
            count_query = count_query.where(Task.created_at >= dt_from)
        except ValueError:
            pass
    if date_to:
        try:
            dt_to = datetime.fromisoformat(date_to)
            query = query.where(Task.created_at <= dt_to)
            count_query = count_query.where(Task.created_at <= dt_to)
        except ValueError:
            pass

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    ALLOWED_SORT_FIELDS = {
        "created_at": Task.created_at,
        "updated_at": Task.updated_at,
        "priority": Task.priority,
        "status": Task.status,
        "task_type": Task.task_type,
        "progress": Task.progress,
    }
    sort_column = ALLOWED_SORT_FIELDS.get(sort_by, Task.created_at)
    if sort_order == "asc":
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())

    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)
    result = await db.execute(query)
    tasks = list(result.scalars().all())

    return ApiResponse(data={
        "items": [_task_to_dict(t) for t in tasks],
        "total": total,
        "page": page,
        "page_size": page_size,
    })


@global_router.get("/queue")
async def get_queue_kanban(
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取队列看板数据（按状态分组，仅当前用户项目的任务）"""
    from app.models.novel import Project
    repo = TaskRepository(db)

    user_project_ids = select(Project.id).where(Project.user_id == user_id).scalar_subquery()

    statuses = ["queued", "running", "completed", "failed"]
    result = {}

    for status in statuses:
        query = select(Task).where(Task.status == status, Task.project_id.in_(user_project_ids))
        count_query = select(func.count()).select_from(Task).where(Task.status == status, Task.project_id.in_(user_project_ids))
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0
        query = query.order_by(Task.priority, desc(Task.created_at)).offset(0).limit(50)
        rows = await db.execute(query)
        tasks = list(rows.scalars().all())
        result[status] = {
            "items": [_task_to_dict(t) for t in tasks],
            "total": total,
        }

    # 已取消的任务
    cancelled_query = select(Task).where(Task.status == "cancelled", Task.project_id.in_(user_project_ids))
    cancelled_count = select(func.count()).select_from(Task).where(Task.status == "cancelled", Task.project_id.in_(user_project_ids))
    total_result = await db.execute(cancelled_count)
    cancelled_total = total_result.scalar() or 0
    cancelled_query = cancelled_query.order_by(desc(Task.created_at)).offset(0).limit(50)
    rows = await db.execute(cancelled_query)
    cancelled_tasks = list(rows.scalars().all())
    result["cancelled"] = {
        "items": [_task_to_dict(t) for t in cancelled_tasks],
        "total": cancelled_total,
    }

    return ApiResponse(data=result)


async def _check_task_belongs_to_user(task, user_id: str, db: AsyncSession):
    """校验任务所属的项目是否属于当前用户"""
    if task.project_id:
        from app.models.novel import Project
        result = await db.execute(
            select(Project.id).where(Project.id == task.project_id, Project.user_id == user_id)
        )
        if result.scalar_one_or_none() is None:
            raise HTTPException(status_code=403, detail="无权访问该任务")


@global_router.get("/{task_id}")
async def get_global_task_detail(
    task_id: UUID,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取任务详情（含日志、产出）"""
    repo = TaskRepository(db)
    task = await repo.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    await _check_task_belongs_to_user(task, user_id, db)
    return ApiResponse(data=_task_to_dict(task))


@global_router.post("/{task_id}/cancel")
async def cancel_global_task(
    task_id: UUID,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """取消任务"""
    repo = TaskRepository(db)
    task = await repo.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    await _check_task_belongs_to_user(task, user_id, db)
    if task.status not in ("queued", "running"):
        raise HTTPException(status_code=400, detail=f"当前状态 '{task.status}' 不允许取消")

    # D39: 同时取消运行中的协程
    await cancel_background_task(task_id)
    task = await repo.update(task_id, status="cancelled")
    return ApiResponse(data=_task_to_dict(task))


@global_router.post("/{task_id}/retry")
async def retry_global_task(
    task_id: UUID,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """重试任务"""
    repo = TaskRepository(db)
    task = await repo.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    await _check_task_belongs_to_user(task, user_id, db)
    if task.status != "failed":
        raise HTTPException(status_code=400, detail=f"当前状态 '{task.status}' 不允许重试")

    runner = get_task_runner(task.task_type)
    if runner is None:
        raise HTTPException(
            status_code=400,
            detail=f"任务类型 '{task.task_type}' 不支持重试"
        )

    task = await repo.update(
        task_id,
        status="queued",
        progress=0,
        error_message=None,
        started_at=None,
        completed_at=None,
    )
    await db.commit()

    tracker = TaskProgressTracker(task)
    spawn_background_task(task_id, redispatch_task(task, tracker))
    return ApiResponse(data=_task_to_dict(task))


@global_router.post("/batch-cancel")
async def batch_cancel_tasks(
    body: BatchIdsRequest,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """批量取消任务（仅当前用户项目的任务）"""
    from app.models.novel import Project
    repo = TaskRepository(db)
    results = {"succeeded": [], "failed": []}

    valid_uuids: dict[UUID, str] = {}
    for tid in body.task_ids:
        try:
            valid_uuids[UUID(tid)] = tid
        except (ValueError, TypeError):
            results["failed"].append({"id": tid, "reason": "无效的任务ID"})

    if not valid_uuids:
        return ApiResponse(data=results)

    result = await db.execute(
        select(Task).where(Task.id.in_(list(valid_uuids.keys())))
    )
    tasks_by_id = {t.id: t for t in result.scalars().all()}

    # 获取当前用户的项目 ID 集合
    user_project_ids_result = await db.execute(
        select(Project.id).where(Project.user_id == user_id)
    )
    user_project_ids = set(row[0] for row in user_project_ids_result)

    cancelled_ids: list[UUID] = []
    for task_uuid, tid in valid_uuids.items():
        task = tasks_by_id.get(task_uuid)
        if task is None:
            results["failed"].append({"id": tid, "reason": "任务不存在"})
            continue
        if task.project_id and task.project_id not in user_project_ids:
            results["failed"].append({"id": tid, "reason": "无权操作该任务"})
            continue
        if task.status not in ("queued", "running"):
            results["failed"].append({"id": tid, "reason": f"当前状态 '{task.status}' 不允许取消"})
            continue
        await cancel_background_task(task_uuid)
        cancelled_ids.append(task_uuid)
        results["succeeded"].append(tid)

    if cancelled_ids:
        await db.execute(
            sa_update(Task)
            .where(Task.id.in_(cancelled_ids))
            .values(status="cancelled")
        )

    return ApiResponse(data=results)


@global_router.post("/batch-retry")
async def batch_retry_tasks(
    body: BatchIdsRequest,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """批量重试任务（仅当前用户项目的任务）"""
    from app.models.novel import Project
    repo = TaskRepository(db)
    results = {"succeeded": [], "failed": []}

    valid_uuids: dict[UUID, str] = {}
    for tid in body.task_ids:
        try:
            valid_uuids[UUID(tid)] = tid
        except (ValueError, TypeError):
            results["failed"].append({"id": tid, "reason": "无效的任务ID"})

    if not valid_uuids:
        return ApiResponse(data=results)

    result = await db.execute(
        select(Task).where(Task.id.in_(list(valid_uuids.keys())))
    )
    tasks_by_id = {t.id: t for t in result.scalars().all()}

    # 获取当前用户的项目 ID 集合
    user_project_ids_result = await db.execute(
        select(Project.id).where(Project.user_id == user_id)
    )
    user_project_ids = set(row[0] for row in user_project_ids_result)

    for task_uuid, tid in valid_uuids.items():
        try:
            task = tasks_by_id.get(task_uuid)
            if task is None:
                results["failed"].append({"id": tid, "reason": "任务不存在"})
                continue
            if task.project_id and task.project_id not in user_project_ids:
                results["failed"].append({"id": tid, "reason": "无权操作该任务"})
                continue
            if task.status != "failed":
                results["failed"].append({"id": tid, "reason": f"当前状态 '{task.status}' 不允许重试"})
                continue
            runner = get_task_runner(task.task_type)
            if runner is None:
                results["failed"].append({"id": tid, "reason": f"任务类型 '{task.task_type}' 不支持重试"})
                continue
            task = await repo.update(
                task_uuid,
                status="queued",
                progress=0,
                error_message=None,
                started_at=None,
                completed_at=None,
            )
            await db.commit()

            tracker = TaskProgressTracker(task)
            spawn_background_task(task_uuid, redispatch_task(task, tracker))
            results["succeeded"].append(tid)
        except Exception as e:
            results["failed"].append({"id": tid, "reason": str(e)})

    return ApiResponse(data=results)
