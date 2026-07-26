export interface Novel {
  id: string
  project_id: string
  title: string
  author?: string
  word_count: number
  format: string
  raw_text?: string
  cleaned_text?: string
  created_at: string
  updated_at: string
}

export interface Chapter {
  id: string
  novel_id: string
  chapter_number: number
  title?: string
  status: string
  paragraph_count?: number
  paragraph_stats?: ParagraphStats
  created_at: string
  updated_at?: string
}

export interface Paragraph {
  id: number | string
  text: string
  annotation?: string
  is_chapter_title?: boolean
}

export interface ParagraphStats {
  dialogue: number
  narration: number
  action: number
  description: number
  unmarked: number
}

// 编辑器段落
export interface EditorParagraph {
  id?: string
  paragraph_number: string
  text: string
  annotation_type?: AnnotationType
  annotation_content?: string
  comment?: string
  sort_order?: number
}

export type AnnotationType = 'dialogue' | 'narration' | 'action' | 'description'

export const ANNOTATION_CONFIG: Record<AnnotationType, { color: string; label: string; hex: string }> = {
  dialogue: { color: '#1677ff', label: '对话', hex: 'blue' },
  narration: { color: '#722ed1', label: '旁白', hex: 'purple' },
  action: { color: '#fa8c16', label: '动作', hex: 'orange' },
  description: { color: '#52c41a', label: '描述', hex: 'green' },
}

// 编辑器版本
export interface EditorVersion {
  id: string
  chapter_id: string
  version_number: number
  summary?: string
  created_at: string
}

export interface EditorVersionDetail extends EditorVersion {
  content_snapshot: EditorParagraph[]
}

// 版本历史
export interface VersionHistoryItem {
  id: string
  chapter_id: string
  version_number: number
  summary?: string
  created_at: string
}

// ===== 剧情拆解（Script）类型 =====

export interface ScriptShot {
  id: string
  shot_id: string
  content: string
  sort_order: number
}

export interface ScriptChapter {
  id: string
  title: string
  sort_order: number
  shots: ScriptShot[]
}

export interface ScriptResponse {
  chapters: ScriptChapter[]
}

export interface ScriptShotData {
  shotId: string
  content: string
}

export interface ScriptChapterData {
  chapterTitle: string
  shots: ScriptShotData[]
}

// ===== 分镜（Storyboard）类型 =====

export interface StoryboardShot {
  id: string
  shot_id: string
  storyboard_details: string
  sort_order: number
}

export interface StoryboardChapter {
  id: string
  title: string
  sort_order: number
  shots: StoryboardShot[]
}

export interface StoryboardResponse {
  chapters: StoryboardChapter[]
}

export interface StoryboardShotData {
  shotId: string
  storyboardDetails: string
}

export interface StoryboardChapterData {
  chapterTitle: string
  shots: StoryboardShotData[]
}

// ===== AI排版（Layout）类型 =====

export interface LayoutPage {
  id: string
  page_id: string
  layout_type: string
  page_purpose: string
  visual_focus: string
  shots: { shotId: string; content: string; storyboardDetails: string }[]
  sort_order: number
  image_prompt?: string
  image_url?: string
}

export interface LayoutChapter {
  id: string
  title: string
  sort_order: number
  pages: LayoutPage[]
}

export interface LayoutResponse {
  chapters: LayoutChapter[]
}

export interface LayoutPageData {
  pageId: string
  layoutType: string
  pagePurpose: string
  visualFocus: string
  shots: { shotId: string; content: string; storyboardDetails: string }[]
}

export interface LayoutChapterData {
  chapterTitle: string
  pages: LayoutPageData[]
}
