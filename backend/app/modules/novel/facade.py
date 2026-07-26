"""NovelService facade - 聚合 6 个业务模块的 service。

从 app/services/novel_service.py 迁移而来（C1 重构）。
保留 facade 模式是因为 novels.py 路由需要统一入口访问 6 个模块的方法。
"""
import logging
from typing import Optional, List
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.novel.service import NovelService as _NovelServiceImpl
from app.modules.script.service import ScriptService as _ScriptServiceImpl
from app.modules.storyboard.service import StoryboardService as _StoryboardServiceImpl
from app.modules.layout.service import LayoutService as _LayoutServiceImpl
from app.modules.prompt.service import PromptService as _PromptServiceImpl
from app.modules.generation.service import GenerationService as _GenerationServiceImpl
from app.repositories.novel_repo import NovelRepository, ProjectRepository
from app.schemas.novel_schema import ChapterUpdate

logger = logging.getLogger(__name__)


class NovelService:
    """Facade that delegates to split module services."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.novel_repo = NovelRepository(session)
        self.project_repo = ProjectRepository(session)
        self._novel_svc = _NovelServiceImpl(session)
        self._script_svc = _ScriptServiceImpl(session)
        self._storyboard_svc = _StoryboardServiceImpl(session)
        self._layout_svc = _LayoutServiceImpl(session)
        self._prompt_svc = _PromptServiceImpl(session)
        self._generation_svc = _GenerationServiceImpl(session)

    async def upload_novel(self, project_id: UUID, file_content: bytes, filename: str, title: str = None) -> dict:
        return await self._novel_svc.upload_novel(project_id, file_content, filename, title)

    async def preprocess_novel(self, novel_id: UUID, tracker=None) -> dict:
        return await self._novel_svc.preprocess_novel(novel_id, tracker)

    async def update_novel_text(self, novel_id: UUID, raw_text: str) -> dict:
        return await self._novel_svc.update_novel_text(novel_id, raw_text)

    async def get_novel_detail(self, novel_id: UUID) -> dict:
        return await self._novel_svc.get_novel_detail(novel_id)

    async def list_chapters(self, novel_id: UUID) -> List[dict]:
        return await self._novel_svc.list_chapters(novel_id)

    async def get_chapter_detail(self, chapter_id: UUID) -> dict:
        return await self._novel_svc.get_chapter_detail(chapter_id)

    async def save_editor(self, chapter_id: UUID, paragraphs_data: list, summary: Optional[str] = None) -> dict:
        return await self._novel_svc.save_editor(chapter_id, paragraphs_data, summary)

    async def get_version_history(self, chapter_id: UUID) -> List[dict]:
        return await self._novel_svc.get_version_history(chapter_id)

    async def get_version_detail(self, version_id: UUID) -> dict:
        return await self._novel_svc.get_version_detail(version_id)

    async def restore_version(self, chapter_id: UUID, version_id: UUID) -> dict:
        return await self._novel_svc.restore_version(chapter_id, version_id)

    async def update_chapter(self, chapter_id: UUID, data: ChapterUpdate) -> dict:
        return await self._novel_svc.update_chapter(chapter_id, data)

    async def merge_chapters(self, source_chapter_id: UUID, target_chapter_id: UUID) -> dict:
        return await self._novel_svc.merge_chapters(source_chapter_id, target_chapter_id)

    async def split_chapter(self, chapter_id: UUID, split_at_paragraph_number: str) -> dict:
        return await self._novel_svc.split_chapter(chapter_id, split_at_paragraph_number)

    async def generate_script(self, novel_id: UUID, tracker=None) -> dict:
        return await self._script_svc.generate_script(novel_id, tracker)

    async def get_script(self, novel_id: UUID) -> dict:
        return await self._script_svc.get_script(novel_id)

    async def save_script(self, novel_id: UUID, chapters_data: list) -> dict:
        return await self._script_svc.save_script(novel_id, chapters_data)

    async def split_shot(self, novel_id: UUID, chapter_id: UUID, shot_id: str,
                         content_before: str, content_after: str) -> dict:
        return await self._script_svc.split_shot(novel_id, chapter_id, shot_id, content_before, content_after)

    async def generate_storyboard(self, novel_id: UUID, tracker=None) -> dict:
        return await self._storyboard_svc.generate_storyboard(novel_id, tracker)

    async def get_storyboard(self, novel_id: UUID) -> dict:
        return await self._storyboard_svc.get_storyboard(novel_id)

    async def save_storyboard(self, novel_id: UUID, chapters_data: list) -> dict:
        return await self._storyboard_svc.save_storyboard(novel_id, chapters_data)

    async def generate_layout(self, novel_id: UUID, tracker=None) -> dict:
        return await self._layout_svc.generate_layout(novel_id, tracker)

    async def get_layout(self, novel_id: UUID) -> dict:
        return await self._layout_svc.get_layout(novel_id)

    async def save_layout(self, novel_id: UUID, chapters_data: list) -> dict:
        return await self._layout_svc.save_layout(novel_id, chapters_data)

    async def delete_layout_chapter(self, novel_id: UUID, chapter_id: UUID) -> dict:
        return await self._layout_svc.delete_layout_chapter(novel_id, chapter_id)

    async def match_references(self, novel_id: UUID, project_id: UUID, tracker=None) -> dict:
        return await self._prompt_svc.match_references(novel_id, project_id, tracker)

    async def generate_image_prompts(self, novel_id: UUID, tracker=None) -> dict:
        return await self._prompt_svc.generate_image_prompts(novel_id, tracker)

    async def regenerate_page_prompt(self, novel_id: UUID, page_id: str, tracker=None) -> dict:
        return await self._prompt_svc.regenerate_page_prompt(novel_id, page_id, tracker)

    async def generate_single_page_image(
        self, project_id: UUID, novel_id: UUID, page_id: str,
        reference_ids: Optional[list[str]] = None, tracker=None,
    ) -> dict:
        return await self._generation_svc.generate_single_page_image(
            project_id, novel_id, page_id, reference_ids, tracker
        )

    async def generate_page_images(
        self, project_id: UUID, novel_id: UUID,
        reference_ids: Optional[dict] = None, tracker=None,
    ) -> dict:
        return await self._generation_svc.generate_page_images(
            project_id, novel_id, reference_ids, tracker
        )

    async def delete_all_layout_pages(self, project_id: UUID, novel_id: UUID) -> dict:
        return await self._generation_svc.delete_all_layout_pages(project_id, novel_id)

    async def batch_delete_pages_content(
        self, project_id: UUID, novel_id: UUID,
        start_page: int, end_page: int, delete_type: str,
    ) -> dict:
        return await self._generation_svc.batch_delete_pages_content(
            project_id, novel_id, start_page, end_page, delete_type,
        )

    async def delete_all_script_and_downstream(self, project_id: UUID, novel_id: UUID) -> dict:
        """删除所有脚本及下游数据（分镜、排版、生图提示词、参考图、漫画页图片）. """
        return await self._generation_svc.delete_all_script_and_downstream(project_id, novel_id)

    async def delete_all_storyboard_and_generation(self, project_id: UUID, novel_id: UUID) -> dict:
        """删除所有分镜及下游数据（排版、生图提示词、参考图、漫画页图片）. """
        return await self._generation_svc.delete_all_storyboard_and_generation(project_id, novel_id)

    async def delete_all_layout_and_generation(self, project_id: UUID, novel_id: UUID) -> dict:
        """删除所有排版及下游数据（生图提示词、参考图、漫画页图片），保留分镜. """
        return await self._generation_svc.delete_all_layout_and_generation(project_id, novel_id)
