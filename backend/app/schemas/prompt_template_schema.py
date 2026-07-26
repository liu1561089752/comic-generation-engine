"""Prompt 模板的 Pydantic schemas。"""
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel


class PromptModuleResponse(BaseModel):
    """单个 Prompt 模块响应。"""
    id: UUID
    template_id: UUID
    module_key: str
    module_label: str
    category: Optional[str] = None
    content: str
    sort_order: int
    updated_at: datetime

    class Config:
        from_attributes = True


class PromptTemplateCreate(BaseModel):
    """创建 Prompt 模板请求。"""
    name: str
    description: Optional[str] = None
    cover_image_url: Optional[str] = None


class PromptTemplateUpdate(BaseModel):
    """更新 Prompt 模板基本信息请求。"""
    name: Optional[str] = None
    description: Optional[str] = None
    cover_image_url: Optional[str] = None


class PromptTemplateResponse(BaseModel):
    """Prompt 模板响应（含 modules）。"""
    id: UUID
    name: str
    description: Optional[str] = None
    cover_image_url: Optional[str] = None
    is_active: bool
    is_default: bool
    created_at: datetime
    updated_at: datetime
    modules: List[PromptModuleResponse] = []

    class Config:
        from_attributes = True


class PromptModuleUpdate(BaseModel):
    """更新单个模块提示词内容请求。"""
    content: str


class SetActiveRequest(BaseModel):
    """设置生效模板请求（无字段，仅触发设置生效）。"""
    pass
