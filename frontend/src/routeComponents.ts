import { lazy } from 'react'
import type { ComponentType } from 'react'

/**
 * 路由懒加载集中管理
 *
 * 目的：
 * 1. 集中维护所有页面的动态导入
 * 2. 提供 preloadByPath 方法，在菜单 hover 时预加载对应组件
 * 3. 避免 React.lazy + Suspense 在首次点击导航时触发的 fallback 闪烁
 */

// 各路由组件：lazy 包裹的动态 import
export const Dashboard = lazy(() => import('./pages/Dashboard'))
export const Login = lazy(() => import('./pages/Login'))
export const ProjectDetail = lazy(() => import('./pages/projects/[id]'))
export const ProjectList = lazy(() => import('./pages/projects'))
export const NovelList = lazy(() => import('./pages/novels'))
export const NovelDetail = lazy(() => import('./pages/novels/[id]'))
export const NovelEditor = lazy(() => import('./pages/novels/editor'))
export const StoryBreakdownLanding = lazy(() => import('./pages/story-breakdown'))
export const StoryBreakdownDetail = lazy(() => import('./pages/story-breakdown/detail'))
export const ProjectStoryBreakdown = lazy(() => import('./pages/story-breakdown/project-entry'))
export const ProjectStoryboard = lazy(() => import('./pages/storyboard/project-storyboard'))
export const ProjectLayoutPage = lazy(() => import('./pages/layout/project-layout'))
export const CharacterList = lazy(() => import('./pages/characters'))
export const CharacterGlobalList = lazy(() => import('./pages/characters/global'))
export const CharacterDetail = lazy(() => import('./pages/characters/[id]'))
export const CharacterRelations = lazy(() => import('./pages/characters/relations'))
export const WorldList = lazy(() => import('./pages/worlds'))
export const WorldDetail = lazy(() => import('./pages/worlds/[id]'))
export const StyleTemplateList = lazy(() => import('./pages/style-templates'))
export const EditorList = lazy(() => import('./pages/editor'))
export const ComicEditor = lazy(() => import('./pages/editor/[pageId]'))
export const ExportCenter = lazy(() => import('./pages/export'))
export const TaskCenter = lazy(() => import('./pages/tasks'))
export const ModelCenter = lazy(() => import('./pages/models'))
export const GenerationCenter = lazy(() => import('./pages/generation'))
export const QualityCenter = lazy(() => import('./pages/quality'))
export const NotificationsPage = lazy(() => import('./pages/notifications'))
export const SystemSettings = lazy(() => import('./pages/system'))
export const StoryboardCenter = lazy(() => import('./pages/storyboard'))
export const LayoutCenter = lazy(() => import('./pages/layout'))
export const TextCenter = lazy(() => import('./pages/text-center'))
export const PromptCenter = lazy(() => import('./pages/prompt-center'))
export const ResourceCenter = lazy(() => import('./pages/resources'))
export const PluginCenter = lazy(() => import('./pages/plugins'))
export const HelpCenter = lazy(() => import('./pages/help'))

/**
 * 路径 → 动态 import 函数 的映射表
 *
 * 注意：键使用「路径前缀」，与 Sidebar 中菜单项的 path 一致；
 * 同一个组件可能被多个路径使用，此处只列该组件的代表性导入路径。
 */
const pathToImporter: Record<string, () => Promise<unknown>> = {
  '/': () => import('./pages/Dashboard'),
  '/login': () => import('./pages/Login'),
  '/projects': () => import('./pages/projects'),
  '/novels': () => import('./pages/novels'),
  '/characters': () => import('./pages/characters/global'),
  '/story-breakdown': () => import('./pages/story-breakdown'),
  '/storyboard': () => import('./pages/storyboard'),
  '/layout': () => import('./pages/layout'),
  '/text-center': () => import('./pages/text-center'),
  '/prompts': () => import('./pages/prompt-center'),
  '/generation': () => import('./pages/generation'),
  '/quality': () => import('./pages/quality'),
  '/editor': () => import('./pages/editor'),
  '/export': () => import('./pages/export'),
  '/models': () => import('./pages/models'),
  '/resources': () => import('./pages/resources'),
  '/plugins': () => import('./pages/plugins'),
  '/system': () => import('./pages/system'),
  '/help': () => import('./pages/help'),
  '/tasks': () => import('./pages/tasks'),
  '/notifications': () => import('./pages/notifications'),
}

/** 已预加载过的路径集合，避免重复触发 */
const preloadedPaths = new Set<string>()

/**
 * 根据路径预加载对应的页面组件
 *
 * 用法：在菜单项 onMouseEnter 时调用
 *  - 已预加载过的路径会跳过
 *  - 未知路径静默忽略
 */
export function preloadByPath(path: string): void {
  if (preloadedPaths.has(path)) return
  const importer = pathToImporter[path]
  if (!importer) return
  preloadedPaths.add(path)
  // 触发动态 import，webpack/vite 会开始下载对应 chunk
  void importer()
}
