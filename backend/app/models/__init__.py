# 模型注册中心 - 所有模型需在此导入以确保 Base.metadata 能发现它们

# === 基础 ===
from app.models.novel import Project, Novel, Chapter, Paragraph, EditorVersion, ScriptChapter, ScriptShot
from app.models.task import Task
from app.models.system import SystemLog, Plugin, Notification, LLMConfig, ImageGenConfig
from app.models.user import User

# === 分镜线 ===
from app.models.storyboard import StoryboardChapter, StoryboardShot

# === 排版/生图/匹配/图片生成线 ===
from app.models.layout import (
    LayoutChapter, LayoutPage, LayoutShot,
    ImagePrompt, ReferenceMatch, GeneratedImage,
)

# === 世界观资产线 ===
from app.models.world import WorldBuilding, SceneAsset, Prop, Building, Outfit, StyleTemplate

# === 角色线 ===
from app.models.character import (
    Character, CharacterState, CharacterRelation,
    CharacterOutfit, CharacterReferenceImage,
)

# === 提示词模板线 ===
from app.models.prompt_template import PromptTemplate, PromptModule

all_models = [
    # 基础
    Project, Novel, Chapter, Paragraph, EditorVersion, ScriptChapter, ScriptShot,
    Task,
    SystemLog, Plugin, Notification, LLMConfig, ImageGenConfig,
    User,
    # 分镜线
    StoryboardChapter, StoryboardShot,
    # 排版/生图/匹配/图片生成线
    LayoutChapter, LayoutPage, LayoutShot,
    ImagePrompt, ReferenceMatch, GeneratedImage,
    # 世界观资产线
    WorldBuilding, SceneAsset, Prop, Building, Outfit, StyleTemplate,
    # 角色线
    Character, CharacterState, CharacterRelation,
    CharacterOutfit, CharacterReferenceImage,
    # 提示词模板线
    PromptTemplate, PromptModule,
]
