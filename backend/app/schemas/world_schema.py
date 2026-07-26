from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID
from datetime import datetime


class WorldBuildingCreate(BaseModel):
    name: str
    era: Optional[str] = None
    era_type: Optional[str] = None
    time_span: Optional[str] = None
    background: Optional[str] = None
    core_tags: Optional[list[str]] = None
    region_style: Optional[str] = None
    civilization_level: Optional[str] = None
    description: Optional[str] = None
    settings: Optional[dict] = None
    cover_image: Optional[str] = None


class WorldBuildingUpdate(BaseModel):
    name: Optional[str] = None
    era: Optional[str] = None
    era_type: Optional[str] = None
    time_span: Optional[str] = None
    background: Optional[str] = None
    core_tags: Optional[list[str]] = None
    region_style: Optional[str] = None
    civilization_level: Optional[str] = None
    description: Optional[str] = None
    settings: Optional[dict] = None
    cover_image: Optional[str] = None


class WorldBuildingResponse(BaseModel):
    id: UUID
    project_id: UUID
    name: str
    era: Optional[str] = None
    era_type: Optional[str] = None
    time_span: Optional[str] = None
    background: Optional[str] = None
    core_tags: Optional[list] = None
    region_style: Optional[str] = None
    civilization_level: Optional[str] = None
    description: Optional[str] = None
    settings: Optional[dict] = None
    cover_image: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ------------------------------------------------------------------
# 场景资产
# ------------------------------------------------------------------


class SceneAssetCreate(BaseModel):
    name: str
    description: Optional[str] = None
    season: Optional[str] = None
    weather: Optional[str] = None
    time_of_day: Optional[str] = None
    lighting: Optional[str] = None
    atmosphere: Optional[str] = None
    tags: Optional[List[str]] = None


class SceneAssetUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    season: Optional[str] = None
    weather: Optional[str] = None
    time_of_day: Optional[str] = None
    lighting: Optional[str] = None
    atmosphere: Optional[str] = None
    tags: Optional[List[str]] = None


class SceneAssetResponse(BaseModel):
    id: UUID
    world_id: UUID
    name: str
    description: Optional[str] = None
    season: Optional[str] = None
    weather: Optional[str] = None
    time_of_day: Optional[str] = None
    lighting: Optional[str] = None
    atmosphere: Optional[str] = None
    reference_images: Optional[dict] = None
    tags: Optional[dict] = None
    image_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ------------------------------------------------------------------
# 道具
# ------------------------------------------------------------------


class PropCreate(BaseModel):
    name: str
    category: Optional[str] = None
    description: Optional[str] = None
    visual_description: Optional[str] = None
    tags: Optional[List[str]] = None


class PropUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    visual_description: Optional[str] = None
    tags: Optional[List[str]] = None


class PropResponse(BaseModel):
    id: UUID
    world_id: UUID
    name: str
    category: Optional[str] = None
    description: Optional[str] = None
    visual_description: Optional[str] = None
    tags: Optional[dict] = None
    image_url: Optional[str] = None

    class Config:
        from_attributes = True


# ------------------------------------------------------------------
# 建筑
# ------------------------------------------------------------------


class BuildingCreate(BaseModel):
    name: str
    style: Optional[str] = None
    interior_exterior: Optional[str] = None
    description: Optional[str] = None
    interior_description: Optional[str] = None
    reference_images: Optional[List[str]] = None


class BuildingUpdate(BaseModel):
    name: Optional[str] = None
    style: Optional[str] = None
    interior_exterior: Optional[str] = None
    description: Optional[str] = None
    interior_description: Optional[str] = None
    reference_images: Optional[List[str]] = None


class BuildingResponse(BaseModel):
    id: UUID
    world_id: UUID
    name: str
    style: Optional[str] = None
    interior_exterior: Optional[str] = None
    description: Optional[str] = None
    interior_description: Optional[str] = None
    reference_images: Optional[dict] = None
    image_url: Optional[str] = None

    class Config:
        from_attributes = True


# ------------------------------------------------------------------
# 服装
# ------------------------------------------------------------------


class OutfitCreate(BaseModel):
    name: str
    style: Optional[str] = None
    color_scheme: Optional[List[str]] = None
    description: Optional[str] = None
    belongs_to_character: Optional[str] = None


class OutfitUpdate(BaseModel):
    name: Optional[str] = None
    style: Optional[str] = None
    color_scheme: Optional[List[str]] = None
    description: Optional[str] = None
    belongs_to_character: Optional[str] = None


class OutfitResponse(BaseModel):
    id: UUID
    world_id: UUID
    name: str
    style: Optional[str] = None
    color_scheme: Optional[List[str]] = None
    description: Optional[str] = None
    belongs_to_character: Optional[str] = None
    image_url: Optional[str] = None

    class Config:
        from_attributes = True


# ------------------------------------------------------------------
# 风格模板
# ------------------------------------------------------------------


class StyleTemplateCreate(BaseModel):
    name: str
    aspect_ratio: Optional[str] = "1:1.34"
    width: Optional[int] = 1080
    art_style: Optional[str] = None
    coloring_style: Optional[str] = None
    lineart_style: Optional[str] = None
    lighting_style: Optional[str] = None
    negative_prompt: Optional[str] = None
    is_default: Optional[bool] = False


class StyleTemplateUpdate(BaseModel):
    name: Optional[str] = None
    aspect_ratio: Optional[str] = None
    width: Optional[int] = None
    art_style: Optional[str] = None
    coloring_style: Optional[str] = None
    lineart_style: Optional[str] = None
    lighting_style: Optional[str] = None
    negative_prompt: Optional[str] = None
    is_default: Optional[bool] = None


class StyleTemplateResponse(BaseModel):
    id: UUID
    project_id: UUID
    name: str
    aspect_ratio: Optional[str] = None
    width: Optional[int] = None
    art_style: Optional[str] = None
    coloring_style: Optional[str] = None
    lineart_style: Optional[str] = None
    lighting_style: Optional[str] = None
    negative_prompt: Optional[str] = None
    is_default: Optional[bool] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
