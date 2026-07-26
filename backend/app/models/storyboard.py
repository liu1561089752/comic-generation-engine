"""分镜数据库模型"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.core.base_model import VersionedMixin


class StoryboardChapter(VersionedMixin, Base):
    """分镜章节 - 对应脚本章节的分镜数据"""
    __tablename__ = "storyboard_chapters"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    novel_id = Column(UUID(as_uuid=True), ForeignKey("novels.id"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    novel = relationship("Novel", back_populates="storyboard_chapters")
    shots = relationship("StoryboardShot", back_populates="chapter", cascade="all, delete-orphan", order_by="StoryboardShot.sort_order")

    def __repr__(self):
        return f"<StoryboardChapter(id={self.id}, title='{self.title}', novel_id={self.novel_id})>"


class StoryboardShot(VersionedMixin, Base):
    """分镜头 - 每个镜头的分镜描述"""
    __tablename__ = "storyboard_shots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chapter_id = Column(UUID(as_uuid=True), ForeignKey("storyboard_chapters.id"), nullable=False, index=True)
    shot_id = Column(String(10), nullable=False)  # e.g., "01", "02"
    storyboard_details = Column(Text, nullable=False, default="")
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    chapter = relationship("StoryboardChapter", back_populates="shots")

    def __repr__(self):
        return f"<StoryboardShot(id={self.id}, shot_id='{self.shot_id}', chapter_id={self.chapter_id})>"
