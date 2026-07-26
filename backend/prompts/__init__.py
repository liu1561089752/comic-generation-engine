# AI 提示词注册中心
# 所有传递给 LLM / AI 模型的提示词集中管理在此目录
# 按功能模块拆分，便于审查和修改
#
# 已使用 LLM 的 Agent（prompt 已激活）:
#   storyboard_system, camera_system, layout_system, bubble_system, world_extraction
#
# 未使用 LLM 的 Agent（prompt 预留，标注 TODO）:
#   text_cleaner_system, story_analyzer_system, semantic_splitter_system
#   consistency_checker_system, quality_scorer_system
#
# 非 LLM 但包含 AI prompt 模板:
#   prompt_generator_template (10 层结构化图像生成 Prompt)

# == 已激活的 Prompt（Agent 当前正在使用）==
from prompts.storyboard_system import STORYBOARD_SYSTEM_PROMPT
from prompts.camera_system import CAMERA_SYSTEM_PROMPT
from prompts.layout_system import LAYOUT_SYSTEM_PROMPT
from prompts.bubble_system import BUBBLE_SYSTEM_PROMPT
from prompts.world_extraction import WORLD_EXTRACTION_SYSTEM_PROMPT
from prompts.novel_preprocess_system import NOVEL_PREPROCESS_SYSTEM_PROMPT
from prompts.character_extraction_system import CHARACTER_EXTRACTION_SYSTEM_PROMPT
from prompts.character_image_system import CHARACTER_IMAGE_SYSTEM_PROMPT
from prompts.scene_extraction_system import SCENE_EXTRACTION_SYSTEM_PROMPT
from prompts.prop_extraction_system import PROP_EXTRACTION_SYSTEM_PROMPT
from prompts.building_extraction_system import BUILDING_EXTRACTION_SYSTEM_PROMPT
from prompts.outfit_extraction_system import OUTFIT_EXTRACTION_SYSTEM_PROMPT
from prompts.storyboard_generation_system import STORYBOARD_GENERATION_SYSTEM_PROMPT
from prompts.layout_generation_system import LAYOUT_GENERATION_SYSTEM_PROMPT
from prompts.reference_match_system import REFERENCE_MATCH_SYSTEM_PROMPT
from prompts.AI生成生图提示词_system import AI_IMAGE_PROMPT_GENERATION_SYSTEM_PROMPT
from prompts.comic_page_generation_system import COMIC_PAGE_GENERATION_SYSTEM_PROMPT

# == 预留的 Prompt（Agent 当前为规则引擎，后续升级 LLM 时启用）==
from prompts.text_cleaner_system import TEXT_CLEANER_SYSTEM_PROMPT
from prompts.story_analyzer_system import STORY_ANALYZER_SYSTEM_PROMPT
from prompts.semantic_splitter_system import SEMANTIC_SPLITTER_SYSTEM_PROMPT
from prompts.consistency_checker_system import CONSISTENCY_CHECKER_SYSTEM_PROMPT
from prompts.quality_scorer_system import QUALITY_SCORER_SYSTEM_PROMPT

# == AI Prompt 模板（非 LLM，用于图像生成）==
from prompts.prompt_generator_template import LAYER_TEMPLATES, LAYER_ORDER

__all__ = [
    # 已激活
    "STORYBOARD_SYSTEM_PROMPT",
    "CAMERA_SYSTEM_PROMPT",
    "LAYOUT_SYSTEM_PROMPT",
    "BUBBLE_SYSTEM_PROMPT",
    "WORLD_EXTRACTION_SYSTEM_PROMPT",
    "NOVEL_PREPROCESS_SYSTEM_PROMPT",
    "CHARACTER_EXTRACTION_SYSTEM_PROMPT",
    "CHARACTER_IMAGE_SYSTEM_PROMPT",
    "SCENE_EXTRACTION_SYSTEM_PROMPT",
    "PROP_EXTRACTION_SYSTEM_PROMPT",
    "BUILDING_EXTRACTION_SYSTEM_PROMPT",
    "OUTFIT_EXTRACTION_SYSTEM_PROMPT",
    "STORYBOARD_GENERATION_SYSTEM_PROMPT",
    "LAYOUT_GENERATION_SYSTEM_PROMPT",
    # 预留
    "TEXT_CLEANER_SYSTEM_PROMPT",
    "STORY_ANALYZER_SYSTEM_PROMPT",
    "SEMANTIC_SPLITTER_SYSTEM_PROMPT",
    "CONSISTENCY_CHECKER_SYSTEM_PROMPT",
    "QUALITY_SCORER_SYSTEM_PROMPT",
    # 模板
    "LAYER_TEMPLATES",
    "LAYER_ORDER",
    # 参考图匹配
    "REFERENCE_MATCH_SYSTEM_PROMPT",
    # 生图提示词 & 漫画页面生成
    "AI_IMAGE_PROMPT_GENERATION_SYSTEM_PROMPT",
    "COMIC_PAGE_GENERATION_SYSTEM_PROMPT",
]
