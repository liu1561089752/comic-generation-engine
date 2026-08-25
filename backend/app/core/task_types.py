"""任务类型常量（后端唯一来源）。

新增/修改任务类型时只改这里；各 router 的注册、去重、进度追踪统一引用常量，
避免字符串散落导致改名漏改（前端中文标签见 frontend/src/pages/tasks/components/types.ts，
两端使用相同的字符串值）。
"""

# ============ 小说管线 ============
TASK_PREPROCESS_NOVEL = "preprocess_novel"
TASK_GENERATE_SCRIPT = "generate_script"
TASK_GENERATE_STORYBOARD = "generate_storyboard"
TASK_GENERATE_LAYOUT = "generate_layout"
TASK_GENERATE_IMAGE_PROMPTS = "generate_image_prompts"
TASK_REGENERATE_PAGE_PROMPT = "regenerate_page_prompt"
TASK_MATCH_REFERENCES = "match_references"
TASK_GENERATE_SINGLE_IMAGE = "generate_single_image"
TASK_GENERATE_PAGE_IMAGES = "generate_page_images"

# ============ 人物 IP ============
TASK_EXTRACT_CHARACTERS = "extract_characters"
TASK_GENERATE_CHARACTER_IMAGE = "generate_character_image"
TASK_GENERATE_STATE_IMAGE = "generate_state_image"

# ============ 世界观 ============
TASK_AI_CREATE_WORLD = "ai_create_world"
TASK_AI_EXTRACT_SCENES = "ai_extract_scenes"
TASK_AI_EXTRACT_PROPS = "ai_extract_props"
TASK_AI_EXTRACT_BUILDINGS = "ai_extract_buildings"
TASK_AI_EXTRACT_OUTFITS = "ai_extract_outfits"
TASK_GENERATE_SCENE_IMAGE = "generate_scene_image"
TASK_GENERATE_PROP_IMAGE = "generate_prop_image"
TASK_GENERATE_BUILDING_IMAGE = "generate_building_image"
TASK_GENERATE_OUTFIT_IMAGE = "generate_outfit_image"

# ============ 导出 ============
TASK_EXPORT = "export"

ALL_TASK_TYPES = [
    TASK_PREPROCESS_NOVEL,
    TASK_GENERATE_SCRIPT,
    TASK_GENERATE_STORYBOARD,
    TASK_GENERATE_LAYOUT,
    TASK_GENERATE_IMAGE_PROMPTS,
    TASK_REGENERATE_PAGE_PROMPT,
    TASK_MATCH_REFERENCES,
    TASK_GENERATE_SINGLE_IMAGE,
    TASK_GENERATE_PAGE_IMAGES,
    TASK_EXTRACT_CHARACTERS,
    TASK_GENERATE_CHARACTER_IMAGE,
    TASK_GENERATE_STATE_IMAGE,
    TASK_AI_CREATE_WORLD,
    TASK_AI_EXTRACT_SCENES,
    TASK_AI_EXTRACT_PROPS,
    TASK_AI_EXTRACT_BUILDINGS,
    TASK_AI_EXTRACT_OUTFITS,
    TASK_GENERATE_SCENE_IMAGE,
    TASK_GENERATE_PROP_IMAGE,
    TASK_GENERATE_BUILDING_IMAGE,
    TASK_GENERATE_OUTFIT_IMAGE,
    TASK_EXPORT,
]

TASK_LABELS_CN = {
    TASK_PREPROCESS_NOVEL: "预处理小说",
    TASK_GENERATE_SCRIPT: "生成脚本",
    TASK_GENERATE_STORYBOARD: "生成分镜",
    TASK_GENERATE_LAYOUT: "生成排版",
    TASK_GENERATE_IMAGE_PROMPTS: "生成提示词",
    TASK_REGENERATE_PAGE_PROMPT: "重新生成提示词",
    TASK_MATCH_REFERENCES: "匹配参考图",
    TASK_GENERATE_SINGLE_IMAGE: "单页生图",
    TASK_GENERATE_PAGE_IMAGES: "批量生图",
    TASK_EXTRACT_CHARACTERS: "提取角色",
    TASK_GENERATE_CHARACTER_IMAGE: "生成形象",
    TASK_GENERATE_STATE_IMAGE: "生成状态形象",
    TASK_AI_CREATE_WORLD: "创建世界观",
    TASK_AI_EXTRACT_SCENES: "提取场景",
    TASK_AI_EXTRACT_PROPS: "提取道具",
    TASK_AI_EXTRACT_BUILDINGS: "提取建筑",
    TASK_AI_EXTRACT_OUTFITS: "提取服装",
    TASK_GENERATE_SCENE_IMAGE: "生成场景图片",
    TASK_GENERATE_PROP_IMAGE: "生成道具图片",
    TASK_GENERATE_BUILDING_IMAGE: "生成建筑图片",
    TASK_GENERATE_OUTFIT_IMAGE: "生成服装图片",
    TASK_EXPORT: "导出",
}
