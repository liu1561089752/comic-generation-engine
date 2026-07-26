"""Scene service - 剧情拆解 service (extracted from app/services/scene_service.py).

Implements T3 D42: AI calls (analyze_chapter, split_scene) use short transaction
pattern (short read -> close -> AI call -> short write -> commit).

Migration notes (new architecture):
- Agents imported from app.infra.agents.* (app.agents.* are compat shims)
- async_session_factory from app.core.database
- Repositories reuse app.repositories.scene_repo (wraps app.core.base_repository)
"""
import logging
from typing import Optional, List, Tuple
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import async_session_factory
from app.infra.agents.story_analyzer import StoryAnalyzerAgent
from app.infra.agents.semantic_splitter import SemanticSplitterAgent
from app.infra.agents.base_agent import AgentContext
from app.models.scene import Scene, Panel
from app.models.novel import Chapter
from app.repositories.scene_repo import SceneRepository, PanelRepository
from app.schemas.scene_schema import (
    SceneCreate,
    SceneUpdate,
    PanelCreate,
    PanelUpdate,
)

logger = logging.getLogger(__name__)


# ======================================================================
# SceneService
# ======================================================================


class SceneService:
    """剧情（Scene）服务：章节分析 + Scene CRUD."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.scene_repo = SceneRepository(session)
        self.panel_repo = PanelRepository(session)

    # ------------------------------------------------------------------
    # 剧情分析（AI 方法 - 短事务模式）
    # ------------------------------------------------------------------

    async def analyze_chapter(self, chapter_id: UUID) -> List[Scene]:
        """调用 StoryAnalyzerAgent 分析章节，创建 Scene 对象。

        短事务模式：
        1. Short read: 读取章节数据
        2. AI call: 调用 StoryAnalyzerAgent（不持有 session）
        3. Short write: 创建 Scene 并提交
        """
        # Step 1: Short read — get chapter data
        async with async_session_factory() as read_session:
            result = await read_session.execute(
                select(Chapter).where(Chapter.id == chapter_id)
            )
            chapter = result.scalar_one_or_none()
            if chapter is None:
                logger.warning(f"Chapter 不存在: {chapter_id}")
                return []
            chapter_text = chapter.content or ""
            chapter_title = chapter.title or ""

        # Step 2: AI call (no session held)
        agent = StoryAnalyzerAgent()
        context = AgentContext(task_id=str(chapter_id), max_retries=3)
        agent_result = await agent.process(
            context,
            chapter_text=chapter_text,
            chapter_title=chapter_title,
        )

        if not agent_result.success:
            logger.error(f"剧情分析失败: {agent_result.error}")
            return []

        # Step 3: Short write — create scenes
        scenes: List[Scene] = []
        async with async_session_factory() as write_session:
            scene_repo = SceneRepository(write_session)
            for scene_data in agent_result.data.get("scenes", []):
                scene = await scene_repo.create(
                    chapter_id=chapter_id,
                    scene_number=scene_data.get("scene_number", 1),
                    description=scene_data.get("description", ""),
                    start_paragraph_id=scene_data.get("start_paragraph"),
                    end_paragraph_id=scene_data.get("end_paragraph"),
                    characters=scene_data.get("characters", []),
                    location=scene_data.get("location", ""),
                    mood=scene_data.get("mood", "neutral"),
                    status="pending",
                )
                scenes.append(scene)
            await write_session.commit()

        return scenes

    # ------------------------------------------------------------------
    # Scene CRUD
    # ------------------------------------------------------------------

    async def create_scene(self, data: SceneCreate) -> Scene:
        return await self.scene_repo.create(**data.model_dump())

    async def get_scene(self, scene_id: UUID) -> Optional[Scene]:
        return await self.scene_repo.get(scene_id)

    async def get_scene_detail(self, scene_id: UUID) -> Optional[Scene]:
        """获取 Scene 详情 + 关联 Panel 列表"""
        result = await self.session.execute(
            select(Scene)
            .where(Scene.id == scene_id)
            .options(selectinload(Scene.panels))
        )
        return result.scalar_one_or_none()

    async def list_scenes_by_chapter(
        self, chapter_id: UUID, skip: int = 0, limit: int = 20
    ) -> Tuple[List[Scene], int]:
        return await self.scene_repo.list(
            chapter_id=chapter_id, skip=skip, limit=limit
        )

    async def update_scene(self, scene_id: UUID, data: SceneUpdate) -> Optional[Scene]:
        update_data = {k: v for k, v in data.model_dump().items() if v is not None}
        return await self.scene_repo.update(scene_id, **update_data)

    async def delete_scene(self, scene_id: UUID) -> bool:
        return await self.scene_repo.delete(scene_id)


# ======================================================================
# PanelService
# ======================================================================


class PanelService:
    """分镜（Panel）服务：语义切句 + Panel CRUD + 手动拆分/合并."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.scene_repo = SceneRepository(session)
        self.panel_repo = PanelRepository(session)

    # ------------------------------------------------------------------
    # 语义切句（AI 方法 - 短事务模式）
    # ------------------------------------------------------------------

    async def split_scene(self, scene_id: UUID) -> List[Panel]:
        """调用 SemanticSplitterAgent 拆分 Scene 为 Panel。

        短事务模式：
        1. Short read: 读取 Scene + Chapter 数据
        2. AI call: 调用 SemanticSplitterAgent（不持有 session）
        3. Short write: 创建 Panel + 更新 Scene 状态并提交
        """
        # Step 1: Short read — get scene + chapter
        async with async_session_factory() as read_session:
            result = await read_session.execute(
                select(Scene).where(Scene.id == scene_id)
            )
            scene = result.scalar_one_or_none()
            if scene is None:
                logger.warning(f"Scene 不存在: {scene_id}")
                return []

            chapter_result = await read_session.execute(
                select(Chapter).where(Chapter.id == scene.chapter_id)
            )
            chapter = chapter_result.scalar_one_or_none()
            if chapter is None or not chapter.content:
                logger.warning(f"Chapter 不存在或无内容: {scene.chapter_id}")
                return []

            # Capture needed data before session closes
            scene_characters = scene.characters or []
            start_paragraph_id = scene.start_paragraph_id
            end_paragraph_id = scene.end_paragraph_id
            chapter_content = chapter.content

        # Extract scene text from chapter content
        paragraphs = [p.strip() for p in chapter_content.split("\n") if p.strip()]
        start = (start_paragraph_id or 1) - 1
        end = end_paragraph_id or len(paragraphs)
        scene_text = "\n".join(paragraphs[start:end])

        # Step 2: AI call (no session held)
        agent = SemanticSplitterAgent()
        context = AgentContext(task_id=str(scene_id), max_retries=3)
        agent_result = await agent.process(
            context,
            scene_text=scene_text,
            scene_id=str(scene_id),
            characters=scene_characters,
        )

        if not agent_result.success:
            logger.error(f"语义切句失败: {agent_result.error}")
            return []

        # Step 3: Short write — create panels + update scene status
        panels: List[Panel] = []
        async with async_session_factory() as write_session:
            scene_repo = SceneRepository(write_session)
            panel_repo = PanelRepository(write_session)
            for panel_data in agent_result.data.get("panels", []):
                panel = await panel_repo.create(
                    scene_id=scene_id,
                    panel_number=panel_data.get("panel_number", 1),
                    source_text=panel_data.get("text", ""),
                    characters=panel_data.get("characters", []),
                    action=panel_data.get("action", ""),
                    emotion=panel_data.get("emotion", ""),
                    status="pending",
                )
                panels.append(panel)
            await scene_repo.update(scene_id, status="analyzed")
            await write_session.commit()

        return panels

    # ------------------------------------------------------------------
    # Panel CRUD
    # ------------------------------------------------------------------

    async def create_panel(self, data: PanelCreate) -> Panel:
        return await self.panel_repo.create(**data.model_dump())

    async def get_panel(self, panel_id: UUID) -> Optional[Panel]:
        return await self.panel_repo.get(panel_id)

    async def get_panel_detail(self, panel_id: UUID) -> Optional[Panel]:
        """获取 Panel 详情 + 关联 Shot / Bubble 列表"""
        return await self.panel_repo.get(
            panel_id,
            options=[selectinload(Panel.shots), selectinload(Panel.bubbles)],
        )

    async def list_panels_by_scene(
        self, scene_id: UUID, skip: int = 0, limit: int = 20
    ) -> Tuple[List[Panel], int]:
        return await self.panel_repo.list(scene_id=scene_id, skip=skip, limit=limit)

    async def update_panel(self, panel_id: UUID, data: PanelUpdate) -> Optional[Panel]:
        update_data = {k: v for k, v in data.model_dump().items() if v is not None}
        return await self.panel_repo.update(panel_id, **update_data)

    async def delete_panel(self, panel_id: UUID) -> bool:
        return await self.panel_repo.delete(panel_id)

    # ------------------------------------------------------------------
    # 手动拆分 / 合并 Panel
    # ------------------------------------------------------------------

    async def split_panel(
        self, panel_id: UUID, split_after_paragraph: int
    ) -> Tuple[Optional[Panel], Optional[Panel]]:
        """手动拆分 Panel：在指定段落位置将原 Panel 拆分为两个 Panel。

        返回 (left_panel, right_panel)。后续 Panel 序号自动 +1。
        使用 list_all() 获取同 scene 下全部 Panel 以整理序号。
        """
        panel = await self.panel_repo.get(panel_id)
        if panel is None:
            return None, None

        scene_id = panel.scene_id
        source_text = panel.source_text or ""
        panel_number = panel.panel_number

        # 创建右侧新 Panel（序号 +1，后续 Panel 序号自动 +1）
        right_panel = await self.panel_repo.create(
            scene_id=scene_id,
            panel_number=panel_number + 1,
            source_text=source_text,
            start_paragraph_id=split_after_paragraph + 1,
            end_paragraph_id=panel.end_paragraph_id,
            characters=panel.characters,
            action=panel.action,
            emotion=panel.emotion,
            camera_type=panel.camera_type,
            camera_movement=panel.camera_movement,
            composition=panel.composition,
            layout_type=panel.layout_type,
            beat=panel.beat,
            status="pending",
        )

        # 更新原 Panel 的 end_paragraph_id
        await self.panel_repo.update(panel_id, end_paragraph_id=split_after_paragraph)

        # 后续 Panel 序号 +1（用 list_all 而非假分页）
        remaining = await self.panel_repo.list_all(scene_id=scene_id)
        for p in remaining:
            if (
                p.id != panel_id
                and p.id != right_panel.id
                and p.panel_number > panel_number
            ):
                await self.panel_repo.update(p.id, panel_number=p.panel_number + 1)

        return panel, right_panel

    async def merge_panels(
        self, panel_id: UUID, target_panel_id: UUID
    ) -> Optional[Panel]:
        """手动合并 Panel：将 target_panel 合并到 panel_id 所在 Panel。

        返回合并后的 Panel。使用 list_all() 获取全部 Panel 以重新整理序号。
        """
        panel = await self.panel_repo.get(panel_id)
        target = await self.panel_repo.get(target_panel_id)
        if panel is None or target is None:
            return None

        # 合并 source_text
        merged_text = (panel.source_text or "") + "\n" + (target.source_text or "")
        await self.panel_repo.update(
            panel_id,
            source_text=merged_text,
            end_paragraph_id=target.end_paragraph_id,
        )

        # 删除目标 Panel
        await self.panel_repo.delete(target_panel_id)

        # 重新整理序号（用 list_all 而非假分页）
        remaining = await self.panel_repo.list_all(scene_id=panel.scene_id)
        sorted_panels = sorted(remaining, key=lambda p: p.panel_number)
        for idx, p in enumerate(sorted_panels, start=1):
            if p.panel_number != idx:
                await self.panel_repo.update(p.id, panel_number=idx)

        return await self.panel_repo.get(panel_id)
