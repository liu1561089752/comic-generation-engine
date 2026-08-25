from pydantic import BaseModel, Field
from typing import Optional


class CreateProjectRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    project_type: Optional[str] = Field("comic", max_length=20)
    status: Optional[str] = Field("draft")


class UpdateProjectRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    project_type: Optional[str] = None
    status: Optional[str] = None


class DuplicateProjectRequest(BaseModel):
    new_name: str = Field(..., min_length=1, max_length=200)
    copy_world_settings: bool = True
    copy_characters: bool = True
    copy_storyboard_templates: bool = True
    copy_prompt_templates: bool = True
    copy_novel: bool = False
    copy_images: bool = False
