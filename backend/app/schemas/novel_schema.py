from typing import Optional, List, Any
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel


class NovelCreate(BaseModel):
    project_id: UUID
    title: str
    author: Optional[str] = None


class NovelUpdate(BaseModel):
    title: Optional[str] = None
    author: Optional[str] = None
    cleaned_text: Optional[str] = None


class NovelResponse(BaseModel):
    id: UUID
    project_id: UUID
    title: str
    author: Optional[str] = None
    raw_text: Optional[str] = None
    cleaned_text: Optional[str] = None
    word_count: int
    format: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ChapterCreate(BaseModel):
    novel_id: UUID
    chapter_number: int
    title: Optional[str] = None
    content: Optional[str] = None


class ChapterUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    status: Optional[str] = None


class ChapterResponse(BaseModel):
    id: UUID
    novel_id: UUID
    chapter_number: int
    title: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PreprocessResult(BaseModel):
    cleaned_text: str
    paragraphs: List[str]
    word_count: int


# ===== 编辑器相关 Schema =====

class ParagraphItem(BaseModel):
    """段落项"""
    id: Optional[str] = None
    paragraph_number: str
    text: str
    annotation_type: Optional[str] = None      # dialogue/narration/action/description
    annotation_content: Optional[str] = None
    comment: Optional[str] = None
    sort_order: int = 0


class EditorSaveRequest(BaseModel):
    """编辑器保存请求"""
    chapter_id: UUID
    paragraphs: List[ParagraphItem]
    summary: Optional[str] = None


class EditorVersionResponse(BaseModel):
    """版本历史响应"""
    id: str
    chapter_id: str
    version_number: int
    summary: Optional[str] = None
    created_at: str

    class Config:
        from_attributes = True


class EditorVersionDetailResponse(BaseModel):
    """版本详情（含内容快照）"""
    id: str
    chapter_id: str
    version_number: int
    summary: Optional[str] = None
    content_snapshot: Any
    created_at: str

    class Config:
        from_attributes = True


class ChapterDetailResponse(BaseModel):
    """章节详情（含段落）"""
    id: str
    novel_id: UUID
    chapter_number: int
    title: Optional[str] = None
    status: str
    content: Optional[str] = None
    paragraphs: List[dict] = []
    paragraph_stats: dict = {}
    created_at: str
    updated_at: str


class MergeChapterRequest(BaseModel):
    """合并章节请求"""
    target_chapter_id: UUID   # 合并到目标章节


class SplitChapterRequest(BaseModel):
    """分割章节请求"""
    split_at_paragraph_number: str   # 在此段落编号后分割


# ===== 剧情拆解（Script）相关 Schema =====

class ScriptShotData(BaseModel):
    """镜头数据"""
    shotId: str
    content: str


class ScriptChapterData(BaseModel):
    """脚本章节数据"""
    chapterTitle: str
    shots: List[ScriptShotData]


class ScriptData(BaseModel):
    """完整脚本数据"""
    chapters: List[ScriptChapterData]


class ScriptShotItem(BaseModel):
    """单条镜头（含ID）"""
    id: str
    shot_id: str
    content: str
    sort_order: int


class ScriptChapterItem(BaseModel):
    """脚本章节（含镜头列表）"""
    id: str
    title: str
    sort_order: int
    shots: List[ScriptShotItem]


class ScriptResponse(BaseModel):
    """脚本响应"""
    chapters: List[ScriptChapterItem]


class SplitShotRequest(BaseModel):
    """拆分镜头请求"""
    chapter_id: str
    shot_id: str       # 要拆分的镜头shot_id
    content_before: str  # 拆分后前半部分内容（保留原shot_id）
    content_after: str   # 拆分后后半部分内容（新shot_id = 原shot_id+1）


class SaveScriptRequest(BaseModel):
    """保存脚本请求"""
    chapters: List[ScriptChapterData]


# ===== 分镜（Storyboard）相关 Schema =====

class StoryboardShotData(BaseModel):
    """分镜头数据"""
    shotId: str
    storyboardDetails: str


class StoryboardChapterData(BaseModel):
    """分镜章节数据（用于保存/生成时传入）"""
    chapterTitle: str
    shots: List[StoryboardShotData]


class StoryboardShotItem(BaseModel):
    """单条分镜头（含ID）"""
    id: str
    shot_id: str
    storyboard_details: str
    sort_order: int


class StoryboardChapterItem(BaseModel):
    """分镜章节（含镜头列表）"""
    id: str
    title: str
    sort_order: int
    shots: List[StoryboardShotItem]


class StoryboardResponse(BaseModel):
    """分镜响应"""
    chapters: List[StoryboardChapterItem]


class SaveStoryboardRequest(BaseModel):
    """保存分镜请求"""
    chapters: List[StoryboardChapterData]


# ===== AI排版（Layout）相关 Schema =====

class LayoutPageData(BaseModel):
    """排版页面数据"""
    pageId: str
    layoutType: str
    pagePurpose: str
    visualFocus: str
    shots: List[dict]
    imagePrompt: Optional[str] = ""
    imageUrl: Optional[str] = ""


class LayoutChapterData(BaseModel):
    """排版章节数据"""
    chapterTitle: str
    pages: List[LayoutPageData]


class LayoutPageItem(BaseModel):
    """单条排版页面（含ID）"""
    id: str
    page_id: str
    layout_type: str
    page_purpose: str
    visual_focus: str
    shots: list
    sort_order: int
    image_prompt: Optional[str] = ""
    image_url: Optional[str] = ""


class LayoutChapterItem(BaseModel):
    """排版章节（含页面列表）"""
    id: str
    title: str
    sort_order: int
    pages: List[LayoutPageItem]


class LayoutResponse(BaseModel):
    """排版响应"""
    chapters: List[LayoutChapterItem]


class SaveLayoutRequest(BaseModel):
    """保存排版请求"""
    chapters: List[LayoutChapterData]
