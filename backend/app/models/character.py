"""角色数据模型 - 角色提取模块"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.core.base_model import StableKeyMixin


class Character(StableKeyMixin, Base):
    """角色 - 对应角色提取提示词输出的 roles[]"""
    __tablename__ = "characters"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False, index=True)
    aliases = Column(Text, nullable=True)          # 别名（逗号分隔）
    description = Column(Text, nullable=True)      # 角色完整视觉设定描述（150-250字）
    role_type = Column(String(50), nullable=True, index=True)  # 主角/配角/反派/关键人物
    status = Column(String(20), default="active")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    project = relationship("Project", back_populates="characters")
    states = relationship("CharacterState", back_populates="character", cascade="all, delete-orphan")
    outfits = relationship("CharacterOutfit", back_populates="character", cascade="all, delete-orphan")
    reference_images = relationship("CharacterReferenceImage", back_populates="character", cascade="all, delete-orphan")
    relations_a = relationship("CharacterRelation", foreign_keys="CharacterRelation.character_a_id", back_populates="character_a", cascade="all, delete-orphan")
    relations_b = relationship("CharacterRelation", foreign_keys="CharacterRelation.character_b_id", back_populates="character_b", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Character(id={self.id}, name='{self.name}', role_type='{self.role_type or 'unknown'}')>"


class CharacterState(Base):
    """角色状态 - 对应角色提取提示词输出的 state[]（年龄阶段/身份变化）"""
    __tablename__ = "character_states"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    character_id = Column(UUID(as_uuid=True), ForeignKey("characters.id"), nullable=False, index=True)
    name = Column(String(200), nullable=False)       # 角色名(年龄或状态)
    aliases = Column(Text, nullable=True)            # 别名
    description = Column(Text, nullable=True)        # 该阶段视觉设定描述
    sort_order = Column(String(50), nullable=True)   # 排序标识
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    character = relationship("Character", back_populates="states")

    def __repr__(self):
        return f"<CharacterState(id={self.id}, name='{self.name}', character_id={self.character_id})>"


class CharacterRelation(Base):
    """角色关系"""
    __tablename__ = "character_relations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True)
    character_a_id = Column(UUID(as_uuid=True), ForeignKey("characters.id"), nullable=False, index=True)
    character_b_id = Column(UUID(as_uuid=True), ForeignKey("characters.id"), nullable=False, index=True)
    relation_type_a_to_b = Column(String(50), nullable=False)
    relation_type_b_to_a = Column(String(50), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    project = relationship("Project", back_populates="character_relations")
    character_a = relationship("Character", foreign_keys=[character_a_id], back_populates="relations_a")
    character_b = relationship("Character", foreign_keys=[character_b_id], back_populates="relations_b")

    def __repr__(self):
        return f"<CharacterRelation(id={self.id}, a={self.character_a_id}, b={self.character_b_id})>"


class CharacterOutfit(Base):
    """角色穿搭 - 角色特定服装关联"""
    __tablename__ = "character_outfits"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    character_id = Column(UUID(as_uuid=True), ForeignKey("characters.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    outfit_type = Column(String(50), nullable=True)
    description = Column(Text, nullable=True)
    color_scheme = Column(JSON, nullable=True)
    scene_tags = Column(JSON, nullable=True)
    reference_image_url = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    character = relationship("Character", back_populates="outfits")

    def __repr__(self):
        return f"<CharacterOutfit(id={self.id}, name='{self.name}', character_id={self.character_id})>"


class CharacterReferenceImage(Base):
    """角色参考图 - 生成的角色立绘/设定图，供参考图匹配模块使用"""
    __tablename__ = "character_reference_images"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    character_id = Column(UUID(as_uuid=True), ForeignKey("characters.id"), nullable=False, index=True)
    state_id = Column(UUID(as_uuid=True), ForeignKey("character_states.id"), nullable=True, index=True)
    angle = Column(String(20), nullable=True)       # 正面/侧面/背面
    image_url = Column(String(500), nullable=False)
    tags = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    character = relationship("Character", back_populates="reference_images")

    def __repr__(self):
        return f"<CharacterReferenceImage(id={self.id}, angle='{self.angle}', character_id={self.character_id})>"
