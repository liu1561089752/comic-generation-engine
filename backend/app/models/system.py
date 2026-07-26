import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Boolean, Text, DateTime, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class LLMConfig(Base):
    """LLM 模型配置（持久化存储）"""
    __tablename__ = "llm_config"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    api_base = Column(String(500), default="")
    api_key = Column(String(500), default="")
    model_name = Column(String(100), default="")
    is_active = Column(Boolean, default=True)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class ImageGenConfig(Base):
    """生图模型配置（持久化存储）"""
    __tablename__ = "image_gen_config"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    api_base = Column(String(500), default="")
    api_key = Column(String(500), default="")
    model_name = Column(String(100), default="")
    is_active = Column(Boolean, default=True)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class SystemLog(Base):
    __tablename__ = "system_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    level = Column(String(20), nullable=False)
    module = Column(String(50), nullable=False)
    action = Column(String(100), nullable=False)
    user_id = Column(String(100), nullable=True)
    target_type = Column(String(50), nullable=True)
    target_id = Column(UUID(as_uuid=True), nullable=True)
    details = Column(JSON, nullable=True)
    ip_address = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<SystemLog(id={self.id}, level='{self.level}', module='{self.module}')>"


class Plugin(Base):
    __tablename__ = "plugins"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    version = Column(String(20), nullable=False)
    description = Column(Text, nullable=True)
    plugin_type = Column(String(50), nullable=False)
    config_schema = Column(JSON, nullable=True)
    enabled = Column(Boolean, default=False)

    def __repr__(self):
        return f"<Plugin(id={self.id}, name='{self.name}', version='{self.version}')>"


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(36), nullable=False)
    type = Column(String(20), nullable=False)  # task_complete/task_failed/system/info/warning
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    related_url = Column(String(500), nullable=True)
    is_read = Column(Boolean, default=False)
    priority = Column(String(10), default="normal")  # high/normal/low
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<Notification(id={self.id}, type='{self.type}', is_read={self.is_read})>"
