// API 基础路径
export const API_BASE_URL = '/api/v1'

// WebSocket 基础路径
export const WS_BASE_URL = `ws://${window.location.host}/ws`

// 页面路由
export const ROUTES = {
  LOGIN: '/login',
  DASHBOARD: '/',
  PROJECTS: '/projects',
  NOVELS: '/projects/:id/novels',
  CHARACTERS: '/characters',
  STORYBOARD: '/storyboard',
  LAYOUT: '/layout',
  PROMPTS: '/prompts',
  GENERATION: '/generation',
  EDITOR: '/projects',
  EXPORT: '/projects',
} as const

// 项目状态颜色映射
export const PROJECT_STATUS_COLOR: Record<string, string> = {
  draft: 'default',
  planning: 'processing',
  generating: 'processing',
  editing: 'warning',
  completed: 'success',
  archived: 'default',
}

// 分页默认值
export const DEFAULT_PAGE_SIZE = 20
