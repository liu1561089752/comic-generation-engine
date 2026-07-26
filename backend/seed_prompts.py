"""将 prompts/ 目录下的所有提示词导入数据库，创建默认模板"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import async_session_factory, engine, Base
import app.models  # noqa: F401
from app.models.prompt_template import PromptTemplate, PromptModule, PROMPT_MODULE_DEFS


# 模块 key → 文件常量名映射
PROMPT_IMPORTS = {
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


async def seed():
    # 确保表存在
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 导入所有提示词常量
    import prompts
    prompt_values = {}
    for key, const_name in PROMPT_IMPORTS.items():
        prompt_values[key] = getattr(prompts, const_name, "")

    async with async_session_factory() as session:
        from sqlalchemy import select

        # 检查是否已有默认模板
        result = await session.execute(
            select(PromptTemplate).where(PromptTemplate.is_default == True)
        )
        existing = result.scalar_one_or_none()
        if existing:
            # 更新已有默认模板的内容
            for module in existing.modules:
                if module.module_key in prompt_values:
                    module.content = prompt_values[module.module_key]
            await session.commit()
            print(f"已更新默认模板: {existing.name}")
            await engine.dispose()
            return

        # 创建默认模板
        template = PromptTemplate(
            name="默认提示词模板",
            description="系统内置提示词，包含所有功能模块的默认提示词",
            is_active=True,
            is_default=True,
        )
        session.add(template)
        await session.flush()

        for i, mod_def in enumerate(PROMPT_MODULE_DEFS):
            module = PromptModule(
                template_id=template.id,
                module_key=mod_def["key"],
                module_label=mod_def["label"],
                category=mod_def["category"],
                content=prompt_values.get(mod_def["key"], ""),
                sort_order=i,
            )
            session.add(module)

        await session.commit()
        print(f"已创建默认模板: {template.name} (active=True)")
        print(f"包含 {len(PROMPT_MODULE_DEFS)} 个模块")

    await engine.dispose()
    print("完成。")


if __name__ == "__main__":
    asyncio.run(seed())
