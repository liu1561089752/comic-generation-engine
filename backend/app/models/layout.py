"""排版/生图提示词/参考图匹配/图片生成数据模型

模块划分:
- AI排版模块      → LayoutChapter / LayoutPage / LayoutShot
- 生图提示词模块   → ImagePrompt
- 参考图匹配模块   → ReferenceMatch
- 图片生成模块     → GeneratedImage
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey, JSON, Float
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.core.base_model import VersionedMixin


class LayoutChapter(VersionedMixin, Base):
    """排版章节 - 对应分镜章节的排版数据"""
    __tablename__ = "layout_chapters"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    novel_id = Column(UUID(as_uuid=True), ForeignKey("novels.id"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    novel = relationship("Novel", back_populates="layout_chapters")
    pages = relationship("LayoutPage", back_populates="chapter", cascade="all, delete-orphan", order_by="LayoutPage.sort_order")

    def __repr__(self):
        return f"<LayoutChapter(id={self.id}, title='{self.title}', novel_id={self.novel_id})>"


class LayoutPage(VersionedMixin, Base):
    """排版页面 - 每一页的排版信息（仅排版模块数据）"""
    __tablename__ = "layout_pages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chapter_id = Column(UUID(as_uuid=True), ForeignKey("layout_chapters.id"), nullable=False, index=True)
    page_label = Column("page_id", String(10), nullable=False)  # "P1", "P2"...
    layout_type = Column(String(50), nullable=False, default="")
    page_purpose = Column(Text, nullable=False, default="")
    visual_focus = Column(Text, nullable=False, default="")
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    chapter = relationship("LayoutChapter", back_populates="pages")
    shots = relationship("LayoutShot", back_populates="page", cascade="all, delete-orphan", order_by="LayoutShot.sort_order")
    image_prompt = relationship("ImagePrompt", back_populates="page", uselist=False, cascade="all, delete-orphan")
    reference_match = relationship("ReferenceMatch", back_populates="page", uselist=False, cascade="all, delete-orphan")
    generated_images = relationship("GeneratedImage", back_populates="page", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<LayoutPage(id={self.id}, page_label='{self.page_label}', chapter_id={self.chapter_id})>"


class LayoutShot(Base):
    """排版镜头 - shot在页面中的编排关系（不冗余content/storyboardDetails）"""
    __tablename__ = "layout_shots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    page_id = Column(UUID(as_uuid=True), ForeignKey("layout_pages.id"), nullable=False, index=True)
    shot_id = Column(String(50), nullable=False)     # 关联 ScriptShot.shot_id / StoryboardShot.shot_id
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    page = relationship("LayoutPage", back_populates="shots")

    def __repr__(self):
        return f"<LayoutShot(id={self.id}, shot_id='{self.shot_id}', page_id={self.page_id})>"


class ImagePrompt(VersionedMixin, Base):
    """生图提示词 - 对应生图提示词生成模块输出（从LayoutPage拆出）"""
    __tablename__ = "image_prompts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    page_id = Column(UUID(as_uuid=True), ForeignKey("layout_pages.id"), nullable=False, index=True)
    full_prompt = Column(Text, nullable=False, default="")
    version = Column(Integer, default=1)
    model_params = Column(JSON, nullable=True)
    score = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    page = relationship("LayoutPage", back_populates="image_prompt")

    def __repr__(self):
        return f"<ImagePrompt(id={self.id}, page_id={self.page_id}, version={self.version})>"


class ReferenceMatch(Base):
    """参考图匹配结果 - 对应参考图匹配模块输出（从LayoutPage拆出）"""
    __tablename__ = "reference_matches"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    page_id = Column(UUID(as_uuid=True), ForeignKey("layout_pages.id"), nullable=False, index=True)
    ref_ids = Column(JSON, nullable=False, default=list)  # ["ref_id1", "ref_id2"]，最多4个
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    page = relationship("LayoutPage", back_populates="reference_match")

    def __repr__(self):
        return f"<ReferenceMatch(id={self.id}, page_id={self.page_id}, ref_count={len(self.ref_ids or [])})>"


class GeneratedImage(Base):
    """生成图片 - 对应图片生成模块输出（从LayoutPage拆出）"""
    __tablename__ = "generated_images"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    page_id = Column(UUID(as_uuid=True), ForeignKey("layout_pages.id"), nullable=False, index=True)
    image_url = Column(String(500), nullable=False, default="")
    thumbnail_url = Column(String(500), nullable=True)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    seed = Column(Integer, nullable=True)
    model_name = Column(String(100), nullable=True)
    model_params = Column(JSON, nullable=True)
    is_selected = Column(String(20), default="generating")  # generating/generated/selected/failed
    quality_score = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    page = relationship("LayoutPage", back_populates="generated_images")

    def __repr__(self):
        return f"<GeneratedImage(id={self.id}, page_id={self.page_id}, status='{self.is_selected}')>"
