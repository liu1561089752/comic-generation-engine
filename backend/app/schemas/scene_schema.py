from typing import Optional, List
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel


# ======================================================================
# Scene 相关 Schema
# ======================================================================


class SceneCreate(BaseModel):
    chapter_id: UUID
    scene_number: int
    description: Optional[str] = None
    start_paragraph_id: Optional[int] = None
    end_paragraph_id: Optional[int] = None
    location: Optional[str] = None
    characters: Optional[List[str]] = None
    mood: Optional[str] = None
    weather: Optional[str] = None
    time: Optional[str] = None
    summary: Optional[str] = None


class SceneUpdate(BaseModel):
    scene_number: Optional[int] = None
    description: Optional[str] = None
    start_paragraph_id: Optional[int] = None
    end_paragraph_id: Optional[int] = None
    location: Optional[str] = None
    characters: Optional[List[str]] = None
    mood: Optional[str] = None
    weather: Optional[str] = None
    time: Optional[str] = None
    summary: Optional[str] = None
    status: Optional[str] = None


class SceneResponse(BaseModel):
    id: UUID
    chapter_id: UUID
    scene_number: int
    description: Optional[str] = None
    start_paragraph_id: Optional[int] = None
    end_paragraph_id: Optional[int] = None
    location: Optional[str] = None
    characters: Optional[list] = None
    mood: Optional[str] = None
    weather: Optional[str] = None
    time: Optional[str] = None
    summary: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ======================================================================
# Panel 相关 Schema
# ======================================================================


class PanelCreate(BaseModel):
    scene_id: UUID
    panel_number: int
    source_text: Optional[str] = None
    start_paragraph_id: Optional[int] = None
    end_paragraph_id: Optional[int] = None
    characters: Optional[List[str]] = None
    action: Optional[str] = None
    emotion: Optional[str] = None
    camera_type: Optional[str] = None
    camera_movement: Optional[str] = None
    composition: Optional[str] = None
    layout_type: Optional[str] = None
    beat: Optional[str] = None


class PanelUpdate(BaseModel):
    panel_number: Optional[int] = None
    source_text: Optional[str] = None
    characters: Optional[List[str]] = None
    action: Optional[str] = None
    emotion: Optional[str] = None
    camera_type: Optional[str] = None
    camera_movement: Optional[str] = None
    composition: Optional[str] = None
    layout_type: Optional[str] = None
    beat: Optional[str] = None
    status: Optional[str] = None


class CameraUpdate(BaseModel):
    """镜头设置"""
    camera_type: Optional[str] = None       # 远景/中景/近景/特写/俯拍/仰拍/POV
    camera_movement: Optional[str] = None   # 固定/推/拉/摇/移/跟/升降


class CompositionUpdate(BaseModel):
    """构图设置"""
    composition: Optional[str] = None          # 三分法/对称/引导线/框架/对角线/黄金比例
    composition_description: Optional[str] = None
    layout_type: Optional[str] = None          # 单格/双格/三格/四格/整页/跨格


class PanelResponse(BaseModel):
    id: UUID
    scene_id: UUID
    panel_number: int
    source_text: Optional[str] = None
    start_paragraph_id: Optional[int] = None
    end_paragraph_id: Optional[int] = None
    characters: Optional[list] = None
    action: Optional[str] = None
    emotion: Optional[str] = None
    camera_type: Optional[str] = None
    camera_movement: Optional[str] = None
    composition: Optional[str] = None
    layout_type: Optional[str] = None
    beat: Optional[str] = None
    page_id: Optional[UUID] = None
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ======================================================================
# Shot / Bubble Schema
# ======================================================================


class ShotResponse(BaseModel):
    id: UUID
    panel_id: UUID
    shot_number: int
    shot_type: Optional[str] = None
    movement: Optional[str] = None
    description: Optional[str] = None

    class Config:
        from_attributes = True


class BubbleResponse(BaseModel):
    id: UUID
    panel_id: UUID
    bubble_type: str
    text: str
    speaker: Optional[str] = None
    speaker_id: Optional[UUID] = None
    order: int
    style: Optional[str] = None
    font: Optional[str] = None
    font_size: int = 16
    position_x: Optional[float] = None
    position_y: Optional[float] = None
    width: Optional[float] = None
    height: Optional[float] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ======================================================================
# 嵌套详情 Schema
# ======================================================================


class PanelDetailResponse(PanelResponse):
    # TODO: 待后续实现使用
    shots: List[ShotResponse] = []
    bubbles: List[BubbleResponse] = []


class SceneDetailResponse(SceneResponse):
    # TODO: 待后续实现使用
    panels: List[PanelResponse] = []


# ======================================================================
# 分析结果 Schema
# ======================================================================


class SceneAnalysisResult(BaseModel):
    # TODO: 待后续实现使用
    scenes: List[SceneCreate]
    plot_structure: Optional[dict] = None


# ======================================================================
# Page 布局相关 Schema
# ======================================================================


class PageCreate(BaseModel):
    chapter_id: UUID
    page_number: int
    layout_template: Optional[str] = None        # single/double/triple/quad/fullpage/cross
    panel_layout: Optional[dict] = None


class PageUpdate(BaseModel):
    page_number: Optional[int] = None
    layout_template: Optional[str] = None
    panel_layout: Optional[dict] = None
    status: Optional[str] = None


class AutoLayoutRequest(BaseModel):
    chapter_id: Optional[UUID] = None
    page_ids: Optional[List[UUID]] = None
    template: Optional[str] = None


class PageResponse(BaseModel):
    id: UUID
    chapter_id: UUID
    page_number: int
    layout_template: Optional[str] = None
    panel_layout: Optional[dict] = None
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
