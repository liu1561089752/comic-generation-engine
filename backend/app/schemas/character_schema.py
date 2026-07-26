from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID
from datetime import datetime


class CharacterCreate(BaseModel):
    name: str
    aliases: Optional[str] = None
    description: Optional[str] = None
    role_type: Optional[str] = None


class CharacterUpdate(BaseModel):
    name: Optional[str] = None
    aliases: Optional[str] = None
    description: Optional[str] = None
    role_type: Optional[str] = None


class CharacterResponse(BaseModel):
    id: UUID
    project_id: UUID
    name: str
    aliases: Optional[str] = None
    description: Optional[str] = None
    role_type: Optional[str] = None
    image_url: Optional[str] = None  # 最近生成的默认形象 URL
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CharacterDetailResponse(CharacterResponse):
    states: list = []
    outfits: List["CharacterOutfitResponse"] = []
    reference_images: List["CharacterReferenceImageResponse"] = []
    relations_a: List["CharacterRelationResponse"] = []
    relations_b: List["CharacterRelationResponse"] = []


class CharacterRelationCreate(BaseModel):
    character_b_id: UUID
    relation_type_a_to_b: str
    relation_type_b_to_a: str
    description: Optional[str] = None


class CharacterRelationResponse(BaseModel):
    id: UUID
    character_a_id: UUID
    character_b_id: UUID
    relation_type_a_to_b: str
    relation_type_b_to_a: str
    description: Optional[str] = None

    class Config:
        from_attributes = True


class CharacterOutfitCreate(BaseModel):
    name: str
    outfit_type: Optional[str] = None
    description: Optional[str] = None
    color_scheme: Optional[dict] = None
    scene_tags: Optional[List[str]] = None
    reference_image_url: Optional[str] = None


class CharacterOutfitResponse(BaseModel):
    id: UUID
    character_id: UUID
    name: str
    outfit_type: Optional[str] = None
    description: Optional[str] = None
    color_scheme: Optional[dict] = None
    scene_tags: Optional[List[str]] = None
    reference_image_url: Optional[str] = None

    class Config:
        from_attributes = True


class CharacterReferenceImageCreate(BaseModel):
    angle: Optional[str] = None
    image_url: str
    tags: Optional[List[str]] = None


class CharacterReferenceImageResponse(BaseModel):
    id: UUID
    character_id: UUID
    angle: Optional[str] = None
    image_url: str
    tags: Optional[List[str]] = None

    class Config:
        from_attributes = True
