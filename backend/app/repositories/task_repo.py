import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List
from uuid import UUID

from sqlalchemy import select, func, and_, update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory
from app.infra.task_registry import cancel_background_task
from app.repositories.base import BaseRepository
from app.models.task import Task

logger = logging.getLogger(__name__)

# 任务超时阈值
STUCK_TASK_TIMEOUT_MINUTES = 30


async def cleanup_stuck_tasks() -> int:
    """自动清理卡住的任务。

    将超过 STUCK_TASK_TIMEOUT_MINUTES 分钟仍处于 queued/running 状态的任务
    标记为 failed。

    根据项目记忆，stuck 任务常见于 task_type='generate_page_images'，
    但也清理其他所有卡住的任务类型。

    Returns:
        清理的任务数量
    """
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=STUCK_TASK_TIMEOUT_MINUTES)
    cleaned = 0

    async with async_session_factory() as sess:
        # 查找所有卡住的任务
        result = await sess.execute(
            select(Task).where(
                Task.status.in_(["queued", "running"]),
                Task.updated_at < cutoff,
            )
        )
        stuck_tasks = list(result.scalars().all())

        if not stuck_tasks:
            logger.info("没有卡住的任务需要清理")
            return 0

        task_ids = [t.id for t in stuck_tasks]
        logger.warning(
            f"发现 {len(stuck_tasks)} 个卡住的任务 (超过 {STUCK_TASK_TIMEOUT_MINUTES} 分钟)："
            f"{[(str(t.id)[:8], t.task_type, t.status) for t in stuck_tasks]}"
        )

        # 先取消对应的后台协程
        for tid in task_ids:
            try:
                await cancel_background_task(tid)
            except Exception as e:
                logger.warning(f"取消后台任务 {tid} 失败: {e}")

        # 批量更新为 failed
        await sess.execute(
            sa_update(Task)
            .where(Task.id.in_(task_ids))
            .values(
                status="failed",
                error_message=(
                    f"自动清理：任务卡住超过 {STUCK_TASK_TIMEOUT_MINUTES} 分钟，"
                    "请重试或联系管理员"
                ),
                completed_at=datetime.now(timezone.utc),
            )
        )
        await sess.commit()
        cleaned = len(stuck_tasks)
        logger.info(f"已自动清理 {cleaned} 个卡住的任务")

    return cleaned


class TaskRepository(BaseRepository[Task]):
    def __init__(self, session: AsyncSession):
        super().__init__(Task, session)

    async def list_filtered(
        self,
        skip: int = 0,
        limit: int = 20,
        task_type: Optional[str] = None,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        project_id: Optional[UUID] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> tuple[List[Task], int]:
        """带筛选和排序的任务列表查询"""
        query = select(self.model)
        count_query = select(func.count()).select_from(self.model)

        conditions = []
        if task_type is not None:
            conditions.append(self.model.task_type == task_type)
        if status is not None:
            conditions.append(self.model.status == status)
        if priority is not None:
            conditions.append(self.model.priority == priority)
        if project_id is not None:
            conditions.append(self.model.project_id == project_id)
        if date_from is not None:
            conditions.append(self.model.created_at >= date_from)
        if date_to is not None:
            conditions.append(self.model.created_at <= date_to)

        if conditions:
            filter_clause = and_(*conditions)
            query = query.where(filter_clause)
            count_query = count_query.where(filter_clause)

        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        sort_column = getattr(self.model, sort_by, self.model.created_at)
        order_method = sort_column.desc() if sort_order == "desc" else sort_column.asc()
        query = query.offset(skip).limit(limit).order_by(order_method)

        result = await self.session.execute(query)
        return list(result.scalars().all()), total

    async def get_queue_status(self) -> dict:
        """获取各状态任务数量统计。

        D50: 用单条 GROUP BY 查询替代 5 次 COUNT 往返。
        """
        statuses = ["queued", "running", "completed", "failed", "cancelled"]
        result = await self.session.execute(
            select(self.model.status, func.count()).group_by(self.model.status)
        )
        counts = {row[0]: row[1] for row in result}
        return {s: counts.get(s, 0) for s in statuses}
