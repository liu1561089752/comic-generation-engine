"""提示词模板数据模型 - Prompt 中心

一套 PromptTemplate 包含多个 PromptModule，
每个 Module 对应一个功能块（脚本拆分、角色提取等）的提示词。
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Text, Boolean, Integer, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


# 模块定义：key → (label, category)
PROMPT_MODULE_DEFS = [
    # 核心流水线
    {"key": "novel_preprocess",            "label": "脚本拆分",       "category": "core"},
    {"key": "storyboard_generation",       "label": "分镜描述",       "category": "core"},
    {"key": "layout_generation",           "label": "AI排版",         "category": "core"},
    {"key": "ai_image_prompt_generation",  "label": "生图提示词生成",  "category": "core"},
    {"key": "reference_match",             "label": "匹配参考图",     "category": "core"},
    # 提取类
    {"key": "character_extraction",        "label": "角色提取",       "category": "extraction"},
    {"key": "scene_extraction",            "label": "场景提取",       "category": "extraction"},
    {"key": "prop_extraction",             "label": "道具提取",       "category": "extraction"},
    {"key": "building_extraction",         "label": "建筑提取",       "category": "extraction"},
    {"key": "outfit_extraction",           "label": "服饰提取",       "category": "extraction"},
    {"key": "world_extraction",            "label": "世界观提取",     "category": "extraction"},
    # 生成类
    {"key": "comic_page_generation",       "label": "漫画页面生成",   "category": "generation"},
    {"key": "character_image",             "label": "角色形象生成",   "category": "generation"},
    # 内部 Agent
    {"key": "storyboard_system",           "label": "分镜系统",       "category": "internal"},
    {"key": "camera_system",               "label": "镜头系统",       "category": "internal"},
    {"key": "layout_system",               "label": "排版系统",       "category": "internal"},
    {"key": "bubble_system",               "label": "气泡系统",       "category": "internal"},
    # 校对类
    {"key": "proofread_prompts",           "label": "生图提示词校对", "category": "internal"},
]


class PromptTemplate(Base):
    """提示词模板 - 一套完整的提示词集合"""
    __tablename__ = "prompt_templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    cover_image_url = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=False, index=True)
    is_default = Column(Boolean, default=False)       # 系统默认模板不可删除
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    modules = relationship("PromptModule", back_populates="template", cascade="all, delete-orphan", order_by="PromptModule.sort_order")

    def __repr__(self):
        return f"<PromptTemplate(id={self.id}, name='{self.name}', active={self.is_active})>"


class PromptModule(Base):
    """模板下的各模块提示词"""
    __tablename__ = "prompt_modules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    template_id = Column(UUID(as_uuid=True), ForeignKey("prompt_templates.id"), nullable=False, index=True)
    module_key = Column(String(50), nullable=False)      # novel_preprocess, character_extraction, ...
    module_label = Column(String(100), nullable=False)   # 脚本拆分, 角色提取, ...
    category = Column(String(50), nullable=True)          # core/extraction/generation/internal
    content = Column(Text, nullable=False, default="")    # 提示词内容（可能几千字）
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("template_id", "module_key", name="uq_prompt_modules_template_module"),
    )

    template = relationship("PromptTemplate", back_populates="modules")

    def __repr__(self):
        return f"<PromptModule(id={self.id}, key='{self.module_key}', template_id={self.template_id})>"
