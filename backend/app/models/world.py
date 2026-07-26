"""世界观资产数据模型 - 场景/道具/建筑/服饰提取模块"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Boolean, Text, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class WorldBuilding(Base):
    """世界观设定"""
    __tablename__ = "world_buildings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    era = Column(String(100), nullable=True)
    era_type = Column(String(50), nullable=True)          # 古代/中世纪/近代/现代/未来/奇幻
    time_span = Column(String(100), nullable=True)
    background = Column(Text, nullable=True)
    core_tags = Column(JSON, nullable=True)
    region_style = Column(String(100), nullable=True)
    civilization_level = Column(String(50), nullable=True)
    description = Column(Text, nullable=True)
    settings = Column(JSON, nullable=True)
    cover_image = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    project = relationship("Project", back_populates="world_buildings")
    scene_assets = relationship("SceneAsset", back_populates="world", cascade="all, delete-orphan")
    props = relationship("Prop", back_populates="world", cascade="all, delete-orphan")
    buildings = relationship("Building", back_populates="world", cascade="all, delete-orphan")
    outfits = relationship("Outfit", back_populates="world", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<WorldBuilding(id={self.id}, name='{self.name}', project_id={self.project_id})>"


class SceneAsset(Base):
    """场景资产 - 对应场景提取提示词输出的 scenes[]"""
    __tablename__ = "scene_assets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    world_id = Column(UUID(as_uuid=True), ForeignKey("world_buildings.id"), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    aliases = Column(Text, nullable=True)            # 别名（逗号分隔）
    description = Column(Text, nullable=True)        # 场景完整视觉描述
    season = Column(String(50), nullable=True)       # 春/夏/秋/冬
    weather = Column(String(50), nullable=True)      # 晴/阴/雨/雪
    time_of_day = Column(String(50), nullable=True)  # 黎明/清晨/上午/正午/下午/黄昏/夜晚
    lighting = Column(String(100), nullable=True)    # 柔光/自然光/逆光/昏暗/灯光/月光/其他
    atmosphere = Column(String(100), nullable=True)  # 宁静/温馨/压抑/紧张/浪漫/肃穆/繁华/荒凉/其他
    tags = Column(JSON, nullable=True)
    image_url = Column(String(500), nullable=True)   # 生成的场景背景图
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    world = relationship("WorldBuilding", back_populates="scene_assets")

    def __repr__(self):
        return f"<SceneAsset(id={self.id}, name='{self.name}', world_id={self.world_id})>"


class Prop(Base):
    """道具 - 对应道具提取提示词输出的 props[]"""
    __tablename__ = "props"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    world_id = Column(UUID(as_uuid=True), ForeignKey("world_buildings.id"), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    category = Column(String(100), nullable=True)       # 武器/兵器/珠宝饰品/服饰配件/身份信物/...
    description = Column(Text, nullable=True)           # 道具完整视觉描述
    visual_description = Column(Text, nullable=True)    # 道具纯视觉细节描述
    tags = Column(JSON, nullable=True)
    image_url = Column(String(500), nullable=True)      # 生成的道具设定图
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    world = relationship("WorldBuilding", back_populates="props")

    def __repr__(self):
        return f"<Prop(id={self.id}, name='{self.name}', category='{self.category}')>"


class Building(Base):
    """建筑 - 对应建筑提取提示词输出的 buildings[]"""
    __tablename__ = "buildings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    world_id = Column(UUID(as_uuid=True), ForeignKey("world_buildings.id"), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    style = Column(String(100), nullable=True)              # 宫廷/府邸/园林/寺庙/道观/...
    interior_exterior = Column(String(20), nullable=True)   # 内景/外景/两者
    description = Column(Text, nullable=True)               # 建筑完整视觉描述
    interior_description = Column(Text, nullable=True)      # 建筑内部空间描述
    tags = Column(JSON, nullable=True)
    image_url = Column(String(500), nullable=True)          # 生成的建筑设定图
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    world = relationship("WorldBuilding", back_populates="buildings")

    def __repr__(self):
        return f"<Building(id={self.id}, name='{self.name}', style='{self.style}')>"


class Outfit(Base):
    """服装 - 对应服饰提取提示词输出的 outfits[]"""
    __tablename__ = "outfits"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    world_id = Column(UUID(as_uuid=True), ForeignKey("world_buildings.id"), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    style = Column(String(100), nullable=True)             # 日常/校园/职场/正式/礼服/...
    belongs_to_character = Column(String(100), nullable=True)  # 归属角色名称（LLM输出）
    description = Column(Text, nullable=True)              # 服装完整视觉描述
    color_scheme = Column(JSON, nullable=True)             # ["颜色1", "颜色2"]
    tags = Column(JSON, nullable=True)
    image_url = Column(String(500), nullable=True)         # 生成的服装设定图
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    world = relationship("WorldBuilding", back_populates="outfits")

    def __repr__(self):
        return f"<Outfit(id={self.id}, name='{self.name}', style='{self.style}')>"


class StyleTemplate(Base):
    """风格模板 - 漫画视觉风格配置"""
    __tablename__ = "style_templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    aspect_ratio = Column(String(20), default="3:4")
    width = Column(String(20), default="1080")
    art_style = Column(Text, nullable=True)
    coloring_style = Column(Text, nullable=True)
    lineart_style = Column(Text, nullable=True)
    lighting_style = Column(Text, nullable=True)
    negative_prompt = Column(Text, nullable=True)
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    project = relationship("Project", back_populates="style_templates")

    def __repr__(self):
        return f"<StyleTemplate(id={self.id}, name='{self.name}', project_id={self.project_id})>"
