import { create } from 'zustand'
import { StoryboardChapter, StoryboardChapterData, LayoutChapter, LayoutChapterData } from '../types/novel'
import { novelApi } from '../api/novelApi'

interface GenerationTask {
  taskId: string | null
  status: 'idle' | 'running' | 'completed' | 'failed'
}

interface PipelineState {
  // 分镜
  storyboardData: StoryboardChapter[]
  storyboardLoading: boolean
  storyboardGenerating: boolean
  // 排版
  layoutData: LayoutChapter[]
  layoutLoading: boolean
  layoutGenerating: boolean
  // 生图
  promptGenerating: boolean
  imageGenerating: boolean
  // 异步任务
  generationTask: GenerationTask
  error: string | null

  // 分镜操作
  fetchStoryboard: (projectId: string, novelId: string) => Promise<void>
  generateStoryboard: (projectId: string, novelId: string) => Promise<string | undefined>
  saveStoryboard: (projectId: string, novelId: string, chapters: StoryboardChapterData[]) => Promise<any>
  deleteAllStoryboard: (projectId: string, novelId: string) => Promise<void>
  deleteAllLayout: (projectId: string, novelId: string) => Promise<void>
  deleteLayoutChapter: (projectId: string, novelId: string, chapterId: string) => Promise<void>
  // 排版操作
  fetchLayout: (projectId: string, novelId: string) => Promise<void>
  generateLayout: (projectId: string, novelId: string) => Promise<string | undefined>
  saveLayout: (projectId: string, novelId: string, chapters: LayoutChapterData[]) => Promise<any>
  deleteAllLayoutPages: (projectId: string, novelId: string) => Promise<void>
  batchDeletePagesContent: (
    projectId: string, novelId: string,
    startPage: number, endPage: number, deleteType: 'prompt' | 'reference' | 'page',
  ) => Promise<void>
  // 生图
  generateImagePrompts: (projectId: string, novelId: string) => Promise<string | undefined>
  generatePageImages: (projectId: string, novelId: string) => Promise<string | undefined>
  // 任务状态
  updateGenerationTask: (taskId: string, status: 'running' | 'completed' | 'failed') => void
  // D58: 请求 ID 追踪，防止快速切换小说时旧请求覆写新数据
  _fetchStoryboardRequestId: number
  _fetchLayoutRequestId: number
}

export const usePipelineStore = create<PipelineState>((set, get) => ({
  storyboardData: [],
  storyboardLoading: false,
  storyboardGenerating: false,
  layoutData: [],
  layoutLoading: false,
  layoutGenerating: false,
  promptGenerating: false,
  imageGenerating: false,
  generationTask: { taskId: null, status: 'idle' },
  error: null,
  _fetchStoryboardRequestId: 0,
  _fetchLayoutRequestId: 0,

  // 分镜操作
  fetchStoryboard: async (projectId, novelId) => {
    // D58: 请求 ID 追踪——快速切换小说时丢弃旧请求的响应
    const requestId = get()._fetchStoryboardRequestId + 1
    set({ storyboardLoading: true, error: null, _fetchStoryboardRequestId: requestId })
    try {
      const res = await novelApi.getStoryboard(projectId, novelId)
      if (get()._fetchStoryboardRequestId !== requestId) return
      set({ storyboardData: res.data?.chapters || [] })
    } catch (e) {
      if (get()._fetchStoryboardRequestId !== requestId) return
      // D77: 设置错误状态供 UI 感知
      set({ storyboardData: [], error: '获取分镜数据失败' })
      console.error('获取分镜数据失败:', e)
    } finally {
      if (get()._fetchStoryboardRequestId === requestId) {
        set({ storyboardLoading: false })
      }
    }
  },

  generateStoryboard: async (projectId, novelId) => {
    set({ generationTask: { taskId: null, status: 'running' } })
    try {
      const res = await novelApi.generateStoryboard(projectId, novelId)
      const taskId = res.data?.task_id
      if (taskId) {
        set({ generationTask: { taskId, status: 'running' } })
        return taskId
      }
      throw new Error('未返回 task_id')
    } catch (e) {
      set({ generationTask: { taskId: null, status: 'failed' } })
      console.error('生成分镜失败:', e)
      throw e
    }
  },

  saveStoryboard: async (projectId, novelId, chapters) => {
    set({ storyboardLoading: true })
    try {
      const res = await novelApi.saveStoryboard(projectId, novelId, chapters)
      set({ storyboardData: res.data?.chapters || [] })
      return res.data
    } catch (e) {
      console.error('保存分镜失败:', e)
      throw e
    } finally {
      set({ storyboardLoading: false })
    }
  },

  deleteAllStoryboard: async (projectId: string, novelId: string) => {
    set({ storyboardLoading: true })
    try {
      await novelApi.deleteAllStoryboard(projectId, novelId)
      set({ storyboardData: [] })
    } catch (e) {
      console.error('删除分镜失败:', e)
      throw e
    } finally {
      set({ storyboardLoading: false })
    }
  },

  deleteAllLayout: async (projectId: string, novelId: string) => {
    set({ layoutLoading: true })
    try {
      await novelApi.deleteAllLayout(projectId, novelId)
      set({ layoutData: [] })
    } catch (e) {
      console.error('删除排版失败:', e)
      throw e
    } finally {
      set({ layoutLoading: false })
    }
  },

  deleteLayoutChapter: async (projectId: string, novelId: string, chapterId: string) => {
    set({ layoutLoading: true })
    try {
      await novelApi.deleteLayoutChapter(projectId, novelId, chapterId)
      // 删除成功后刷新排版数据
      await get().fetchLayout(projectId, novelId)
    } catch (e) {
      console.error('删除章节排版失败:', e)
      throw e
    } finally {
      set({ layoutLoading: false })
    }
  },

  // 排版操作
  fetchLayout: async (projectId, novelId) => {
    // D58: 请求 ID 追踪——快速切换小说时丢弃旧请求的响应
    const requestId = get()._fetchLayoutRequestId + 1
    set({ layoutLoading: true, error: null, _fetchLayoutRequestId: requestId })
    try {
      const res = await novelApi.getLayout(projectId, novelId)
      if (get()._fetchLayoutRequestId !== requestId) return
      set({ layoutData: res.data?.chapters || [] })
    } catch (e) {
      if (get()._fetchLayoutRequestId !== requestId) return
      // D77: 设置错误状态供 UI 感知
      set({ layoutData: [], error: '获取排版数据失败' })
      console.error('获取排版数据失败:', e)
    } finally {
      if (get()._fetchLayoutRequestId === requestId) {
        set({ layoutLoading: false })
      }
    }
  },

  generateLayout: async (projectId, novelId) => {
    set({ generationTask: { taskId: null, status: 'running' } })
    try {
      const res = await novelApi.generateLayout(projectId, novelId)
      const taskId = res.data?.task_id
      if (taskId) {
        set({ generationTask: { taskId, status: 'running' } })
        return taskId
      }
      throw new Error('未返回 task_id')
    } catch (e) {
      set({ generationTask: { taskId: null, status: 'failed' } })
      console.error('生成排版失败:', e)
      throw e
    }
  },

  saveLayout: async (projectId, novelId, chapters) => {
    set({ layoutLoading: true })
    try {
      const res = await novelApi.saveLayout(projectId, novelId, chapters)
      set({ layoutData: res.data?.chapters || [] })
      return res.data
    } catch (e) {
      console.error('保存排版失败:', e)
      throw e
    } finally {
      set({ layoutLoading: false })
    }
  },

  deleteAllLayoutPages: async (projectId: string, novelId: string) => {
    set({ layoutLoading: true })
    try {
      await novelApi.deleteAllLayoutPages(projectId, novelId)
      // 重新拉取后端数据（image_url 已被清空，排版/提示词等保留）
      await get().fetchLayout(projectId, novelId)
    } catch (e) {
      console.error('删除漫画页失败:', e)
      throw e
    } finally {
      set({ layoutLoading: false })
    }
  },

  batchDeletePagesContent: async (projectId, novelId, startPage, endPage, deleteType) => {
    set({ layoutLoading: true })
    try {
      await novelApi.batchDeletePages(projectId, novelId, startPage, endPage, deleteType)
      await get().fetchLayout(projectId, novelId)
    } catch (e) {
      console.error('批量删除失败:', e)
      throw e
    } finally {
      set({ layoutLoading: false })
    }
  },

  // 生图
  generateImagePrompts: async (projectId, novelId) => {
    set({ generationTask: { taskId: null, status: 'running' } })
    try {
      const res = await novelApi.generateImagePrompts(projectId, novelId)
      const taskId = res.data?.task_id
      if (taskId) {
        set({ generationTask: { taskId, status: 'running' } })
        return taskId
      }
      throw new Error('未返回 task_id')
    } catch (e) {
      set({ generationTask: { taskId: null, status: 'failed' } })
      console.error('生成提示词失败:', e)
      throw e
    }
  },

  generatePageImages: async (projectId, novelId) => {
    set({ generationTask: { taskId: null, status: 'running' } })
    try {
      const res = await novelApi.generatePageImages(projectId, novelId)
      const taskId = res.data?.task_id
      if (taskId) {
        set({ generationTask: { taskId, status: 'running' } })
        return taskId
      }
      throw new Error('未返回 task_id')
    } catch (e) {
      set({ generationTask: { taskId: null, status: 'failed' } })
      console.error('生成图片失败:', e)
      throw e
    }
  },

  updateGenerationTask: (taskId, status) => {
    set({ generationTask: { taskId, status } })
  },
}))
