from typing import Optional, List
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel


class PromptGenerateRequest(BaseModel):
    """生成 Prompt 请求"""
    character_data: Optional[dict] = None
    scene_data: Optional[dict] = None
    style_data: Optional[dict] = None
    bubble_data: Optional[List[dict]] = None


class PromptGenerateResponse(BaseModel):
    """生成 Prompt 响应"""
    layers: dict
    full_prompt: str
    negative_prompt: str
    params: dict

    class Config:
        from_attributes = True


class PromptUpdate(BaseModel):
    """手动编辑 Prompt 请求"""
    layers: Optional[dict] = None
    full_prompt: Optional[str] = None
    model_params: Optional[dict] = None
    tags: Optional[List[str]] = None


class PromptResponse(BaseModel):
    """Prompt 列表响应"""
    id: UUID
    panel_id: UUID
    version: int
    layers: Optional[dict] = None
    full_prompt: Optional[str] = None
    model_params: Optional[dict] = None
    score: Optional[float] = None
    tags: Optional[list] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PromptDetailResponse(PromptResponse):
    """Prompt 详情响应"""
    pass


class PromptTestRequest(BaseModel):
    """测试 Prompt 请求"""
    prompt: str
    negative_prompt: str = ""
    width: int = 1080
    height: int = 1440
    steps: int = 30
    cfg_scale: float = 7.5
    seed: int = -1
    model_name: Optional[str] = None


class PromptTestResponse(BaseModel):
    """测试 Prompt 响应"""
    image_url: str
    prompt: str
    params: dict
