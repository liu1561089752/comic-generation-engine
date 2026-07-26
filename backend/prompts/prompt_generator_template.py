# Agent ⑧ Prompt 生成器 — 10 层结构化模板
# 用途: 聚合所有上游数据，组装分层的图像生成 Prompt（用于 Stable Diffusion / Midjourney）
# 使用的 agent: PromptGeneratorAgent（纯模板引擎，无需 LLM）
# 说明: 此文件定义了每层的模板格式和字段映射规则，可直接修改以调整输出 Prompt 结构

# 层序号与 Prompt Agent.md 规范保持一致
LAYER_TEMPLATES = {
    "character": (
        "角色描述层",
        "格式: {name}, {appearance}, {expression}, wearing {outfit}",
    ),
    "environment": (
        "环境背景层",
        "格式: {background_description}, {location_type}, {time_period}",
    ),
    "action": (
        "动作描写层",
        "格式: {action_description}, {pose}, {interaction_with_environment}",
    ),
    "emotion": (
        "情绪氛围层",
        "格式: {mood}, {atmosphere}, {emotional_tone}",
    ),
    "camera": (
        "镜头视角层",
        "格式: {camera_type}, {camera_angle}, {shot_size}",
    ),
    "lighting": (
        "光照效果层",
        "格式: {lighting_style}, {light_source}, {shadow_type}",
    ),
    "composition": (
        "构图方式层",
        "格式: {composition_rule}, {focus_point}, {framing}",
    ),
    "webtoon_style": (
        "画风风格层",
        "格式: {art_style}, {line_art_style}, {color_palette}, {rendering_style}",
    ),
    "bubble": (
        "气泡文字层",
        "格式: {bubble_text}, {bubble_position}, {bubble_type}",
    ),
    "negative": (
        "负面提示层",
        "格式: {negative_prompt_content}",
    ),
}

LAYER_ORDER = [
    "character", "environment", "action", "emotion",
    "camera", "lighting", "composition",
    "webtoon_style", "bubble", "negative",
]
