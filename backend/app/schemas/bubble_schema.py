from typing import Optional, List
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel


class BubbleCreate(BaseModel):
    """创建气泡请求"""
    panel_id: UUID
    bubble_type: str = "dialogue"   # dialogue/narration/thinking/sfx
    text: str = ""
    speaker: Optional[str] = None
    speaker_id: Optional[UUID] = None
    order: int = 0
    style: Optional[str] = None
    font: Optional[str] = None
    font_size: int = 16
    position_x: Optional[float] = None
    position_y: Optional[float] = None
    width: Optional[float] = None
    height: Optional[float] = None


class BubbleUpdate(BaseModel):
    """更新气泡请求"""
    id: Optional[UUID] = None           # 用于批量操作时指定
    bubble_type: Optional[str] = None
    text: Optional[str] = None
    speaker: Optional[str] = None
    speaker_id: Optional[UUID] = None
    order: Optional[int] = None
    style: Optional[str] = None
    font: Optional[str] = None
    font_size: Optional[int] = None
    position_x: Optional[float] = None
    position_y: Optional[float] = None
    width: Optional[float] = None
    height: Optional[float] = None


class BubbleResponse(BaseModel):
    """气泡响应"""
    id: UUID
    panel_id: UUID
    bubble_type: str
    text: str
    speaker: Optional[str] = None
    speaker_id: Optional[UUID] = None
    order: int
    style: Optional[str] = None
    font: Optional[str] = None
    font_size: int
    position_x: Optional[float] = None
    position_y: Optional[float] = None
    width: Optional[float] = None
    height: Optional[float] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class BubbleBatchUpdate(BaseModel):
    """批量排序/更新气泡"""
    bubbles: List[BubbleUpdate]
