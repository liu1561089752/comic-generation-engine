from datetime import datetime, timezone
from typing import Optional, List
from uuid import UUID

from sqlalchemy import select, func, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.base import BaseRepository
from app.models.novel import Project, Novel, Chapter, Paragraph, EditorVersion
from app.models.task import Task


class ProjectRepository(BaseRepository[Project]):
    def __init__(self, session: AsyncSession):
        super().__init__(Project, session)

    async def get_by_name(self, name: str, user_id: Optional[str] = None) -> Optional[Project]:
        """按名称查找项目（用于重名检测）"""
        query = select(Project).where(Project.name == name)
        if user_id:
            query = query.where(Project.user_id == user_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def archive(self, project_id: UUID) -> Optional[Project]:
        """归档项目"""
        return await self.update(project_id, status="archived", archived_at=datetime.now(timezone.utc))

    async def restore(self, project_id: UUID) -> Optional[Project]:
        """恢复归档"""
        return await self.update(project_id, status="active", archived_at=None)

    async def list_filtered(
        self,
        skip: int = 0,
        limit: int = 20,
        status: Optional[str] = None,
        project_type: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        sort: str = "updated_at",
        order: str = "desc",
        user_id: Optional[str] = None,
    ) -> tuple[List[Project], int]:
        """带筛选和排序的项目列表查询"""
        query = select(self.model)
        count_query = select(func.count()).select_from(self.model)

        # 动态构建筛选条件
        conditions = []
        if user_id is not None:
            conditions.append(self.model.user_id == user_id)
        if status is not None:
            conditions.append(self.model.status == status)
        if project_type is not None:
            conditions.append(self.model.project_type == project_type)
        if date_from is not None:
            conditions.append(self.model.created_at >= date_from)
        if date_to is not None:
            conditions.append(self.model.created_at <= date_to)

        if conditions:
            filter_clause = and_(*conditions)
            query = query.where(filter_clause)
            count_query = count_query.where(filter_clause)

        # 总记录数
        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        # 排序
        sort_column = getattr(self.model, sort, self.model.updated_at)
        order_method = sort_column.desc() if order == "desc" else sort_column.asc()
        query = query.offset(skip).limit(limit).order_by(order_method)

        result = await self.session.execute(query)
        return list(result.scalars().all()), total

    async def get_production_progress(self, project_id: UUID) -> dict:
        """获取项目生产进度统计"""
        # Scene/Panel/Page/Image 模型已删除，仅保留任务统计
        results = {}

        # 任务统计
        task_counts = {"total": 0, "queued": 0, "running": 0, "completed": 0, "failed": 0}
        task_result = await self.session.execute(
            select(func.count(), Task.status).where(
                Task.project_id == project_id
            ).group_by(Task.status)
        )
        for count, status in task_result:
            task_counts[status] = count
            task_counts["total"] += count
        results["tasks"] = task_counts

        # Scene/Panel/Image/Page 统计 - 模型已删除，返回 0
        results["total_scenes"] = 0
        results["total_panels"] = 0
        results["total_images"] = 0
        results["total_pages"] = 0

        return results


class NovelRepository(BaseRepository[Novel]):
    def __init__(self, session: AsyncSession):
        super().__init__(Novel, session)


class ChapterRepository(BaseRepository[Chapter]):
    def __init__(self, session: AsyncSession):
        super().__init__(Chapter, session)
    
    async def get_max_chapter_number(self, novel_id: UUID) -> int:
        """获取小说当前最大章节编号"""
        result = await self.session.execute(
            select(func.max(Chapter.chapter_number)).where(Chapter.novel_id == novel_id)
        )
        max_num = result.scalar()
        return max_num or 0
    
    async def list(
        self, skip: int = 0, limit: int = 20, **filters
    ) -> tuple[List[Chapter], int]:
        """获取章节列表（按章节号升序排列）"""
        query = select(Chapter)
        count_query = select(func.count()).select_from(Chapter)
        for key, value in filters.items():
            if hasattr(Chapter, key) and value is not None:
                query = query.where(getattr(Chapter, key) == value)
                count_query = count_query.where(getattr(Chapter, key) == value)
        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0
        query = query.offset(skip).limit(limit).order_by(Chapter.chapter_number.asc())
        result = await self.session.execute(query)
        return list(result.scalars().all()), total


class ParagraphRepository(BaseRepository[Paragraph]):
    def __init__(self, session: AsyncSession):
        super().__init__(Paragraph, session)

    async def list_by_chapter(self, chapter_id: UUID) -> List[Paragraph]:
        """获取章节的所有段落（按编号排序）"""
        result = await self.session.execute(
            select(Paragraph)
            .where(Paragraph.chapter_id == chapter_id)
            .order_by(Paragraph.sort_order, Paragraph.paragraph_number)
        )
        return list(result.scalars().all())

    async def list_by_chapter_ids(self, chapter_ids: list) -> dict:
        """批量查询多个章节的段落，返回 {chapter_id: [paragraphs]}"""
        from sqlalchemy import select as sa_select
        from app.models.novel import Paragraph
        result = await self.session.execute(
            sa_select(Paragraph)
            .where(Paragraph.chapter_id.in_(chapter_ids))
            .order_by(Paragraph.sort_order)
        )
        paragraphs = result.scalars().all()
        grouped = {}
        for p in paragraphs:
            grouped.setdefault(p.chapter_id, []).append(p)
        return grouped

    async def delete_by_chapter(self, chapter_id: UUID) -> None:
        """删除章节的所有段落"""
        from sqlalchemy import delete as sa_delete
        await self.session.execute(
            sa_delete(Paragraph).where(Paragraph.chapter_id == chapter_id)
        )
        await self.session.flush()


class EditorVersionRepository(BaseRepository[EditorVersion]):
    def __init__(self, session: AsyncSession):
        super().__init__(EditorVersion, session)

    async def list_by_chapter(self, chapter_id: UUID, limit: int = 50) -> List[EditorVersion]:
        """获取章节的版本历史"""
        result = await self.session.execute(
            select(EditorVersion)
            .where(EditorVersion.chapter_id == chapter_id)
            .order_by(desc(EditorVersion.version_number))
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_max_version(self, chapter_id: UUID) -> int:
        """获取章节最大版本号"""
        result = await self.session.execute(
            select(func.max(EditorVersion.version_number)).where(EditorVersion.chapter_id == chapter_id)
        )
        max_ver = result.scalar()
        return max_ver or 0

