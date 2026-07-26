"""Task service - 任务管理 service (migrated from app/services/task_service.py).

新架构规范:
- 不 import app.services.* / app.adapters.* / app.config / app.database (旧路径)
- TaskService 的方法大多是 CRUD 操作，直接使用路由层注入的 session
  （无 AI 调用，无需短事务模式），与 ScriptService 的 CRUD 方法风格一致。
- 状态转换使用 BaseRepository.update_if 做原子 UPDATE，避免旧
  read-then-update 的 TOCTOU 竞态。
"""
import logging
from typing import Optional, List, Tuple
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Task
from app.repositories.task_repo import TaskRepository

logger = logging.getLogger(__name__)


class TaskService:
    """任务管理服务。

    负责任务的创建、查询、取消、重试及队列看板等操作。CRUD 操作直接使用
    路由层注入的 session，由路由层统一控制事务边界（commit/rollback）。
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.task_repo = TaskRepository(session)

    # =================================================================
    # 单任务 CRUD
    # =================================================================

    async def create_task(
        self,
        project_id: UUID,
        task_type: str,
        input_data: dict,
        priority: str = "normal",
    ) -> Task:
        """创建任务，初始状态为 queued。"""
        return await self.task_repo.create(
            project_id=project_id,
            task_type=task_type,
            input_data=input_data,
            priority=priority,
            status="queued",
        )

    async def get_task(self, task_id: UUID) -> Optional[Task]:
        """获取单个任务。"""
        return await self.task_repo.get(task_id)

    async def list_tasks(
        self,
        project_id: Optional[UUID] = None,
        task_type: Optional[str] = None,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> Tuple[List[Task], int]:
        """获取任务列表（支持多维度筛选与排序）。

        签名兼容路由层 ``list_tasks(project_id=None, status=None, skip=0,
        limit=20)`` 的子集调用；``task_type``、``priority``、``sort_by``、
        ``sort_order`` 保留与 ``list_all_tasks`` 端点一致的筛选与排序能力。
        """
        return await self.task_repo.list_filtered(
            skip=skip,
            limit=limit,
            task_type=task_type,
            status=status,
            priority=priority,
            project_id=project_id,
            sort_by=sort_by,
            sort_order=sort_order,
        )

    # =================================================================
    # 状态机：取消 / 重试（原子 UPDATE）
    # =================================================================

    async def cancel_task(self, task_id: UUID) -> Optional[Task]:
        """取消任务（仅 queued/running 状态可取消）。

        使用 ``update_if`` 做原子状态转换，避免 read-then-update 的竞态。
        仅更新 DB 状态；如需同时取消运行中的协程，调用方应额外调用
        ``cancel_background_task``（与现有路由行为保持一致）。
        返回更新后的任务；若状态不允许则返回原任务；任务不存在则返回 None。
        """
        task = await self.task_repo.get(task_id)
        if task is None:
            return None
        if task.status in ("queued", "running"):
            await self.task_repo.update_if(
                task_id,
                conditions={"status": ("queued", "running")},
                status="cancelled",
            )
            return await self.task_repo.get(task_id)
        return task

    async def retry_task(self, task_id: UUID) -> Optional[Task]:
        """重试失败的任务（仅 failed 状态可重试）。

        重置状态为 queued、进度归零并清空错误信息与时间戳。仅更新 DB 状态；
        如需重新派发后台执行，调用方应额外调用 ``spawn_background_task``
        （与现有路由行为保持一致）。
        """
        task = await self.task_repo.get(task_id)
        if task is None:
            return None
        if task.status == "failed":
            await self.task_repo.update_if(
                task_id,
                conditions={"status": "failed"},
                status="queued",
                progress=0,
                error_message=None,
                started_at=None,
                completed_at=None,
            )
            return await self.task_repo.get(task_id)
        return task

    # =================================================================
    # 看板 / 批量操作
    # =================================================================

    async def get_queue_data(self) -> dict:
        """获取队列看板数据（按状态分组）。

        返回结构::

            {
                "queued":    {"items": [...], "total": int},
                "running":   {"items": [...], "total": int},
                "completed": {"items": [...], "total": int},
                "failed":    {"items": [...], "total": int},
                "cancelled": {"items": [...], "total": int},
            }
        """
        statuses = ["queued", "running", "completed", "failed", "cancelled"]
        result: dict = {}
        for st in statuses:
            tasks, total = await self.task_repo.list_filtered(
                status=st, skip=0, limit=50
            )
            result[st] = {
                "items": [_task_to_dict(t) for t in tasks],
                "total": total,
            }
        return result

    async def batch_cancel(self, task_ids: list[UUID]) -> int:
        """批量取消任务，返回成功取消的数量。

        仅 queued/running 状态的任务会被取消；其余任务静默跳过。
        """
        count = 0
        for tid in task_ids:
            if await self.task_repo.update_if(
                tid,
                conditions={"status": ("queued", "running")},
                status="cancelled",
            ):
                count += 1
        return count

    async def batch_retry(self, task_ids: list[UUID]) -> int:
        """批量重试任务，返回成功重试的数量。

        仅 failed 状态的任务会被重试；其余任务静默跳过。
        """
        count = 0
        for tid in task_ids:
            if await self.task_repo.update_if(
                tid,
                conditions={"status": "failed"},
                status="queued",
                progress=0,
                error_message=None,
                started_at=None,
                completed_at=None,
            ):
                count += 1
        return count


def _task_to_dict(task: Task) -> dict:
    """将 Task ORM 对象序列化为字典（与路由层 ``_task_to_dict`` 保持一致）。"""
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
