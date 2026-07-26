"""提示词加载器：从数据库读取生效模板的模块提示词，回退到文件提示词。

使用方式（在 async service 中）：
    from app.infra.prompt_loader import get_prompt
    prompt = await get_prompt("character_extraction", db=session)

如果不传 db 参数，会自动创建临时 session。
如果数据库中没有生效模板或对应模块为空，回退到 prompts/ 目录下的文件常量。
"""
from typing import Optional
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory
from app.models.prompt_template import PromptTemplate, PromptModule

logger = logging.getLogger(__name__)

# 模块 key → 文件常量名映射（回退用）
_MODULE_CONST_MAP = {
    "novel_preprocess":            "NOVEL_PREPROCESS_SYSTEM_PROMPT",
    "storyboard_generation":       "STORYBOARD_GENERATION_SYSTEM_PROMPT",
    "layout_generation":           "LAYOUT_GENERATION_SYSTEM_PROMPT",
    "ai_image_prompt_generation":  "AI_IMAGE_PROMPT_GENERATION_SYSTEM_PROMPT",
    "reference_match":             "REFERENCE_MATCH_SYSTEM_PROMPT",
    "character_extraction":        "CHARACTER_EXTRACTION_SYSTEM_PROMPT",
    "scene_extraction":            "SCENE_EXTRACTION_SYSTEM_PROMPT",
    "prop_extraction":             "PROP_EXTRACTION_SYSTEM_PROMPT",
    "building_extraction":         "BUILDING_EXTRACTION_SYSTEM_PROMPT",
    "outfit_extraction":           "OUTFIT_EXTRACTION_SYSTEM_PROMPT",
    "world_extraction":            "WORLD_EXTRACTION_SYSTEM_PROMPT",
    "comic_page_generation":       "COMIC_PAGE_GENERATION_SYSTEM_PROMPT",
    "character_image":             "CHARACTER_IMAGE_SYSTEM_PROMPT",
    "storyboard_system":           "STORYBOARD_SYSTEM_PROMPT",
    "camera_system":               "CAMERA_SYSTEM_PROMPT",
    "layout_system":               "LAYOUT_SYSTEM_PROMPT",
    "bubble_system":               "BUBBLE_SYSTEM_PROMPT",
}


def _get_file_prompt(module_key: str) -> str:
    """从 prompts/ 包读取文件常量作为回退。"""
    const_name = _MODULE_CONST_MAP.get(module_key)
    if not const_name:
        return ""
    try:
        import prompts
        return getattr(prompts, const_name, "")
    except Exception:
        return ""


async def get_prompt(module_key: str, db: Optional[AsyncSession] = None) -> str:
    """从数据库读取生效模板的指定模块提示词。

    Args:
        module_key: 模块标识（如 "character_extraction"）
        db: 可选的数据库 session，不传则自动创建

    Returns:
        提示词内容字符串。如果 DB 中没有，回退到文件常量。
    """
    async def _query(session: AsyncSession) -> Optional[str]:
        result = await session.execute(
            select(PromptModule.content)
            .join(PromptTemplate, PromptModule.template_id == PromptTemplate.id)
            .where(
                PromptTemplate.is_active.is_(True),
                PromptModule.module_key == module_key,
            )
        )
        row = result.first()
        return row[0] if row else None

    try:
        if db is not None:
            content = await _query(db)
        else:
            async with async_session_factory() as session:
                content = await _query(session)

        if content:
            return content
    except Exception as e:
        logger.warning(f"从数据库读取提示词失败({module_key}): {e}，回退到文件常量")

    # 回退到文件常量
    return _get_file_prompt(module_key)
