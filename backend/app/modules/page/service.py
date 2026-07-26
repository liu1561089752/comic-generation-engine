"""Page service - 页面与版式 service (migrated from app/services/page_service.py).

新架构规范:
- 不 import app.services.* / app.adapters.* / app.config / app.database（旧路径）
- CRUD 通过 BaseRepository（app.core.base_repository），直接以 Page 模型实例化
- 短事务模式仅用于 AI 调用场景；本模块无 AI 调用，CRUD 使用路由传入的共享 session
- 构造函数保持 def __init__(self, session: AsyncSession)，路由用 PageService(db) 创建
"""
import logging
from typing import Optional, List, Tuple
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_repository import BaseRepository
from app.models.page import Page
from app.models.novel import Chapter, Novel
from app.schemas.scene_schema import PageCreate, PageUpdate, AutoLayoutRequest

logger = logging.getLogger(__name__)

# Webtoon 模板定义：每种模板对应的画格布局
LAYOUT_TEMPLATES = {
    "single":   {"name": "单格", "panels": 1, "grid": [{"rows": 1, "cols": 1}]},
    "double":   {"name": "双格", "panels": 2, "grid": [{"rows": 1, "cols": 1}, {"rows": 1, "cols": 1}]},
    "triple":   {"name": "三格", "panels": 3, "grid": [{"rows": 1, "cols": 1}, {"rows": 1, "cols": 1}, {"rows": 1, "cols": 1}]},
    "quad":     {"name": "四格", "panels": 4, "grid": [{"rows": 2, "cols": 2}]},
    "fullpage": {"name": "整页", "panels": 1, "grid": [{"rows": 1, "cols": 1}], "fullscreen": True},
    "cross":    {"name": "跨格", "panels": 2, "grid": [{"rows": 1, "cols": 2}]},
}


class PageService:
    """页面 CRUD 与自动版式规划服务。"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.page_repo = BaseRepository(Page, session)

    # ------------------------------------------------------------------
    # Page CRUD
    # ------------------------------------------------------------------

    async def create_page(self, data: PageCreate) -> Page:
        """创建页面。"""
        return await self.page_repo.create(**data.model_dump())

    async def get_page(self, page_id: UUID) -> Optional[Page]:
        """根据 ID 获取页面。"""
        return await self.page_repo.get(page_id)

    async def list_pages(
        self,
        project_id: UUID,
        chapter_id: Optional[UUID] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> Tuple[List[Page], int]:
        """列出项目下所有页面，可按章节筛选。

        Page 模型本身没有 project_id 字段，需通过 Chapter → Novel 关联到 Project：
            Page.chapter_id → Chapter.id
            Chapter.novel_id → Novel.id
            Novel.project_id → Project.id
        """
        list_query = (
            select(Page)
            .join(Chapter, Page.chapter_id == Chapter.id)
            .join(Novel, Chapter.novel_id == Novel.id)
            .where(Novel.project_id == project_id)
        )
        count_query = (
            select(func.count(Page.id))
            .join(Chapter, Page.chapter_id == Chapter.id)
            .join(Novel, Chapter.novel_id == Novel.id)
            .where(Novel.project_id == project_id)
        )

        if chapter_id is not None:
            list_query = list_query.where(Page.chapter_id == chapter_id)
            count_query = count_query.where(Page.chapter_id == chapter_id)

        list_query = list_query.order_by(Page.page_number.asc()).offset(skip).limit(limit)

        result = await self.session.execute(list_query)
        count_result = await self.session.execute(count_query)
        total = count_result.scalar() or 0
        return list(result.scalars().all()), total

    async def update_page(self, page_id: UUID, data: PageUpdate) -> Optional[Page]:
        """更新页面布局/状态。仅写入非 None 字段。"""
        update_data = {k: v for k, v in data.model_dump().items() if v is not None}
        return await self.page_repo.update(page_id, **update_data)

    async def delete_page(self, page_id: UUID) -> bool:
        """删除页面。"""
        return await self.page_repo.delete(page_id)

    # ------------------------------------------------------------------
    # 自动版式规划
    # ------------------------------------------------------------------

    async def auto_layout(self, request: AutoLayoutRequest) -> List[Page]:
        """自动版式规划：根据所选模板为指定页面分配布局。

        - 若 request.page_ids 非空：仅处理这些页面
        - 否则若 request.chapter_id 非空：处理该章节下所有页面（按 page_number 升序）
        - 否则查询所有页面（按 page_number 升序）
        选定模板后写入 layout_template / panel_layout，并将状态置为 planned。
        """
        if request.page_ids:
            pages: List[Page] = []
            for pid in request.page_ids:
                page = await self.page_repo.get(pid)
                if page is not None:
                    pages.append(page)
        elif request.chapter_id:
            result = await self.session.execute(
                select(Page)
                .where(Page.chapter_id == request.chapter_id)
                .order_by(Page.page_number.asc())
            )
            pages = list(result.scalars().all())
        else:
            result = await self.session.execute(
                select(Page).order_by(Page.page_number.asc())
            )
            pages = list(result.scalars().all())

        template = request.template or "triple"
        template_config = LAYOUT_TEMPLATES.get(template, LAYOUT_TEMPLATES["triple"])

        panel_count = template_config["panels"]
        grid = template_config["grid"]
        panel_layout = {
            "template": template,
            "template_name": template_config["name"],
            "panel_count": panel_count,
            "grid": grid,
        }

        updated_pages: List[Page] = []
        for page in pages:
            await self.page_repo.update(
                page.id,
                layout_template=template,
                panel_layout=panel_layout,
                status="planned",
            )
            updated_page = await self.page_repo.get(page.id)
            if updated_page is not None:
                updated_pages.append(updated_page)

        return updated_pages
