// 通用 API 响应类型
export interface ApiResponse<T> {
  code: number
  message: string
  data: T
}

export interface PaginatedResponse<T> {
  code: number
  message: string
  data: T[]
  meta: { page: number; page_size: number; total: number }
}

// 项目状态
export type ProjectStatus = 'draft' | 'planning' | 'generating' | 'editing' | 'completed' | 'archived'

// 项目类型
export type ProjectType = 'webtoon' | 'comic' | 'manga' | 'illustration'

// 通用常量
export const PROJECT_STATUS_MAP: Record<ProjectStatus, string> = {
  draft: '草稿',
  planning: '规划中',
  generating: '生成中',
  editing: '编辑中',
  completed: '已完成',
  archived: '已归档',
}

export const PROJECT_TYPE_MAP: Record<ProjectType, string> = {
  webtoon: '条漫',
  comic: '漫画',
  manga: '日漫',
  illustration: '插画',
}
