from datetime import datetime
from typing import Optional, List
from uuid import UUID

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.base import BaseRepository
from app.models.task import Task


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
