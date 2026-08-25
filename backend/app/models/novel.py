import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.core.base_model import VersionedMixin


class Project(Base):
    __tablename__ = "projects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    project_type = Column(String(20), default="comic")
    status = Column(String(20), default="draft")
    cover_image_url = Column(String(500), nullable=True)
    archived_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    novels = relationship("Novel", back_populates="project", cascade="all, delete-orphan")
    user = relationship("User", back_populates="projects")
    characters = relationship("Character", back_populates="project", cascade="all, delete-orphan")
    world_buildings = relationship("WorldBuilding", back_populates="project", cascade="all, delete-orphan")
    tasks = relationship("Task", back_populates="project", cascade="all, delete-orphan")
    character_relations = relationship("CharacterRelation", back_populates="project", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Project(id={self.id}, name='{self.name}', status='{self.status}')>"


class Novel(Base):
    __tablename__ = "novels"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    author = Column(String(100), nullable=True)
    raw_text = Column(Text, nullable=False)
    cleaned_text = Column(Text, nullable=True)
    word_count = Column(Integer, default=0)
    format = Column(String(10), default="txt")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    project = relationship("Project", back_populates="novels")
    chapters = relationship("Chapter", back_populates="novel", cascade="all, delete-orphan")
    script_chapters = relationship("ScriptChapter", back_populates="novel", cascade="all, delete-orphan")
    storyboard_chapters = relationship("StoryboardChapter", back_populates="novel", cascade="all, delete-orphan")
    layout_chapters = relationship("LayoutChapter", back_populates="novel", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Novel(id={self.id}, title='{self.title}', project_id={self.project_id})>"


class Chapter(Base):
    __tablename__ = "chapters"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    novel_id = Column(UUID(as_uuid=True), ForeignKey("novels.id"), nullable=False, index=True)
    chapter_number = Column(Integer, nullable=False)
    title = Column(String(200), nullable=True)
    content = Column(Text, nullable=True)
    status = Column(String(20), default="pending", index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    novel = relationship("Novel", back_populates="chapters")
    paragraphs = relationship("Paragraph", back_populates="chapter", cascade="all, delete-orphan", order_by="Paragraph.paragraph_number")
    versions = relationship("EditorVersion", back_populates="chapter", cascade="all, delete-orphan", order_by="EditorVersion.version_number.desc()")

    def __repr__(self):
        return f"<Chapter(id={self.id}, number={self.chapter_number}, novel_id={self.novel_id})>"


class Paragraph(Base):
    __tablename__ = "paragraphs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chapter_id = Column(UUID(as_uuid=True), ForeignKey("chapters.id"), nullable=False, index=True)
    paragraph_number = Column(String(10), nullable=False)  # 如 0001, 0001a, 0001b
    text = Column(Text, nullable=False, default="")
    annotation_type = Column(String(20), nullable=True)  # dialogue/narration/action/description
    annotation_content = Column(Text, nullable=True)     # 标注内容
    comment = Column(Text, nullable=True)                # 注释
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    chapter = relationship("Chapter", back_populates="paragraphs")

    def __repr__(self):
        return f"<Paragraph(id={self.id}, num={self.paragraph_number}, chapter_id={self.chapter_id})>"


class EditorVersion(Base):
    __tablename__ = "editor_versions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chapter_id = Column(UUID(as_uuid=True), ForeignKey("chapters.id"), nullable=False, index=True)
    version_number = Column(Integer, nullable=False)
    summary = Column(String(500), nullable=True)
    content_snapshot = Column(JSON, nullable=False)  # [{paragraph_number, text, annotation_type, annotation_content, comment}]
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    chapter = relationship("Chapter", back_populates="versions")

    def __repr__(self):
        return f"<EditorVersion(id={self.id}, chapter_id={self.chapter_id}, version={self.version_number})>"


class ScriptChapter(VersionedMixin, Base):
    """脚本章节 - 剧情拆解中的章节"""
    __tablename__ = "script_chapters"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    novel_id = Column(UUID(as_uuid=True), ForeignKey("novels.id"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    novel = relationship("Novel", back_populates="script_chapters")
    shots = relationship("ScriptShot", back_populates="chapter", cascade="all, delete-orphan", order_by="ScriptShot.sort_order")

    def __repr__(self):
        return f"<ScriptChapter(id={self.id}, title='{self.title}', novel_id={self.novel_id})>"


class ScriptShot(VersionedMixin, Base):
    """脚本镜头 - 剧情拆解中的单条镜头"""
    __tablename__ = "script_shots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chapter_id = Column(UUID(as_uuid=True), ForeignKey("script_chapters.id"), nullable=False, index=True)
    shot_id = Column(String(10), nullable=False)  # e.g., "01", "02"
    content = Column(Text, nullable=False, default="")
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    chapter = relationship("ScriptChapter", back_populates="shots")

    def __repr__(self):
        return f"<ScriptShot(id={self.id}, shot_id='{self.shot_id}', chapter_id={self.chapter_id})>"
