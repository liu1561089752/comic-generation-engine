"""提示词加载器：从数据库读取生效模板的模块提示词。

使用方式（在 async service 中）：
    from app.infra.prompt_loader import get_prompt
    prompt = await get_prompt("character_extraction", db=session)

如果不传 db 参数，会自动创建临时 session。

带有内存缓存，避免重复查询数据库。
"""
from typing import Optional
import logging
import time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory
from app.models.prompt_template import PromptTemplate, PromptModule

logger = logging.getLogger(__name__)

# 内存缓存：module_key -> (content, timestamp)
_prompt_cache: dict[str, tuple[str, float]] = {}
_prompt_cache_ttl = 60.0  # 缓存有效期 60 秒


async def get_prompt(module_key: str, db: Optional[AsyncSession] = None) -> str:
    """从数据库读取生效模板的指定模块提示词。

    Args:
        module_key: 模块标识（如 "character_extraction"）
        db: 可选的数据库 session，不传则自动创建

    Returns:
        提示词内容字符串，未找到时返回空字符串。
    """
    # 检查缓存
    now = time.monotonic()
    cached = _prompt_cache.get(module_key)
    if cached is not None and now - cached[1] < _prompt_cache_ttl:
        return cached[0]

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
            _prompt_cache[module_key] = (content, time.monotonic())
            return content
    except Exception as e:
        logger.warning(f"从数据库读取提示词失败({module_key}): {e}")

    logger.warning(f"提示词模块 '{module_key}' 在数据库中不存在或为空，返回空字符串")
    return ""


def clear_prompt_cache() -> None:
    """清除提示词缓存（在模板更新后调用）。"""
    _prompt_cache.clear()
    logger.info("提示词缓存已清除")


def set_prompt_cache_ttl(ttl: float) -> None:
    """设置缓存有效期（秒）。"""
    global _prompt_cache_ttl
    _prompt_cache_ttl = ttl
