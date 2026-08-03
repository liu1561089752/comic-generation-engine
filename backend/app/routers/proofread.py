"""生图提示词校对路由 - 将章节的原始文本、角色对应表、生图提示词发给 LLM 校对。

依赖 Prompt 中心的 "proofread_prompts" 模块作为系统提示词。
"""
import json
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import require_project_novel
from app.infra.adapters.llm_adapter import LLMAdapter
from app.infra.adapters.base_llm import ChatMessage
from app.infra.prompt_loader import get_prompt
from app.middleware.auth import get_current_user
from app.models.novel import Chapter
from app.models.layout import LayoutChapter, ImagePrompt
from app.models.character import Character, CharacterState
from app.schemas.common import ApiResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/{project_id}/novels/{novel_id}/layout-chapters/{layout_chapter_id}/proofread-prompts")
async def proofread_chapter_prompts(
    project_id: UUID,
    novel_id: UUID,
    layout_chapter_id: UUID,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _n = Depends(require_project_novel),
):
    """校对指定排版章节的生图提示词。

    流程：
    1. 获取 LayoutChapter 及其所有页面和生图提示词
    2. 获取章节原始文本（通过 sort_order 匹配 Chapter）
    3. 获取项目下所有角色及其昵称/状态
    4. 组合成用户提示词格式
    5. 从 Prompt 中心读取 system prompt（proofread_prompts 模块）
    6. 调用 LLM 校对
    7. 返回校对结果
    """
    try:
        # Step 1: 获取 LayoutChapter 及其页面
        layout_result = await db.execute(
            select(LayoutChapter)
            .options(selectinload(LayoutChapter.pages))
            .where(LayoutChapter.id == layout_chapter_id, LayoutChapter.novel_id == novel_id)
        )
        layout_chapter = layout_result.scalar_one_or_none()
        if not layout_chapter:
            raise HTTPException(status_code=404, detail="排版章节不存在")

        # 收集该章节的页面生图提示词
        page_shots = []
        for page in layout_chapter.pages:
            ip_result = await db.execute(
                select(ImagePrompt).where(ImagePrompt.page_id == page.id)
            )
            img_prompt = ip_result.scalar_one_or_none()
            prompt_text = img_prompt.full_prompt if img_prompt else ""

            page_shots.append({
                "pageId": page.page_label,
                "imagePrompt": prompt_text,
            })

        # Step 2: 获取章节原始文本（通过 sort_order 匹配 Chapter）
        chapter_result = await db.execute(
            select(Chapter).where(
                Chapter.novel_id == novel_id,
                Chapter.chapter_number == layout_chapter.sort_order,
            )
        )
        chapter = chapter_result.scalar_one_or_none()
        novel_content = chapter.content if chapter else ""
        chapter_title = chapter.title if chapter else layout_chapter.title

        # Step 3: 获取项目下所有角色的大名与昵称对应表
        char_result = await db.execute(
            select(Character)
            .options(selectinload(Character.states))
            .where(Character.project_id == project_id)
        )
        characters = char_result.scalars().all()

        alias_mapping = []
        for ch in characters:
            # 角色主名
            if ch.aliases:
                for alias in [a.strip() for a in ch.aliases.split(",") if a.strip()]:
                    alias_mapping.append({
                        "name": ch.name,
                        "aliasname": alias,
                    })
            # 角色每个状态也放入映射
            for state in (ch.states or []):
                if state.aliases:
                    for alias in [a.strip() for a in state.aliases.split(",") if a.strip()]:
                        alias_mapping.append({
                            "name": state.name,
                            "aliasname": alias,
                        })

        # Step 4: 构建用户提示词
        user_prompt_parts = []

        # 4a. 小说原文
        user_prompt_parts.append("小说原文：")
        user_prompt_parts.append(novel_content)
        user_prompt_parts.append("")

        # 4b. 角色大名与昵称对应表
        user_prompt_parts.append("角色大名与昵称对应表：")
        user_prompt_parts.append(json.dumps(alias_mapping, ensure_ascii=False, indent=2))
        user_prompt_parts.append("")

        # 4c. 待校对的整章生图提示词
        user_prompt_parts.append("待校对的整章生图提示词：")
        user_prompt_parts.append(
            json.dumps({"shots": page_shots}, ensure_ascii=False, indent=2)
        )

        user_prompt = "\n".join(user_prompt_parts)

        # Step 5: 获取系统提示词（从 Prompt 中心读取）
        system_prompt = await get_prompt("proofread_prompts")
        if not system_prompt:
            # 如果用户还没配置系统提示词，使用一个默认的
            system_prompt = (
                "你是一个专业的漫画生图提示词校对专家。你的任务是根据小说原文和角色信息，"
                "校对生图提示词的准确性和一致性。请检查：\n"
                "1. 角色名称是否与原文一致\n"
                "2. 场景描述是否符合原文\n"
                "3. 提示词是否完整、清晰\n"
                "4. 分镜逻辑是否连贯\n\n"
                "请直接返回校对后的生图提示词，保持与原格式完全一致（包含【shotId】等标记）。"
            )

        # Step 6: 调用 LLM
        llm = LLMAdapter(
            api_key=settings.LLM_API_KEY,
            api_base=settings.LLM_API_BASE,
            model=settings.LLM_MODEL or "gpt-4o",
        )

        messages = [
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="user", content=user_prompt),
        ]

        llm_result = await llm.chat(messages=messages)
        proofread_content = llm_result.content

        # Step 7: 返回结果
        return ApiResponse(data={
            "chapter_title": chapter_title,
            "layout_chapter_id": str(layout_chapter_id),
            "original_prompts": page_shots,
            "proofread_content": proofread_content,
            "novel_content_preview": novel_content[:500] if novel_content else "",
            "alias_mapping_count": len(alias_mapping),
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"校对生图提示词失败: {e}")
        raise HTTPException(status_code=500, detail=f"校对失败: {str(e)}")
