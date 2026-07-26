import { create } from 'zustand'
import { ScriptChapterData, ScriptChapter } from '../types/novel'
import { novelApi } from '../api/novelApi'

interface GenerationTask {
  taskId: string | null
  status: 'idle' | 'running' | 'completed' | 'failed'
}

interface ScriptState {
  // 剧情拆解（脚本）数据
  scriptData: ScriptChapter[]
  scriptLoading: boolean
  scriptGenerating: boolean
  scriptDeleting: boolean
  generationTask: GenerationTask
  error: string | null

  fetchScript: (projectId: string, novelId: string) => Promise<void>
  generateScript: (projectId: string, novelId: string) => Promise<string | undefined>
  saveScript: (projectId: string, novelId: string, chapters: ScriptChapterData[]) => Promise<any>
  splitShot: (
    projectId: string,
    novelId: string,
    chapterId: string,
    shotId: string,
    contentBefore: string,
    contentAfter: string
  ) => Promise<any>
  deleteScript: (projectId: string, novelId: string) => Promise<void>
  updateGenerationTask: (taskId: string, status: 'running' | 'completed' | 'failed') => void
  // D58: 请求 ID 追踪，防止快速切换小说时旧请求覆写新数据
  _fetchScriptRequestId: number
}

export const useScriptStore = create<ScriptState>((set, get) => ({
  scriptData: [],
  scriptLoading: false,
  scriptGenerating: false,
  scriptDeleting: false,
  generationTask: { taskId: null, status: 'idle' },
  error: null,
  _fetchScriptRequestId: 0,

  fetchScript: async (projectId, novelId) => {
    // D58: 请求 ID 追踪——快速切换小说时丢弃旧请求的响应
    const requestId = get()._fetchScriptRequestId + 1
    set({ scriptLoading: true, error: null, _fetchScriptRequestId: requestId })
    try {
      const res = await novelApi.getScript(projectId, novelId)
      if (get()._fetchScriptRequestId !== requestId) return
      set({ scriptData: res.data?.chapters || [] })
    } catch (e) {
      if (get()._fetchScriptRequestId !== requestId) return
      // D77: 设置错误状态供 UI 感知
      set({ scriptData: [], error: '获取脚本数据失败' })
      console.error('获取脚本数据失败:', e)
    } finally {
      if (get()._fetchScriptRequestId === requestId) {
        set({ scriptLoading: false })
      }
    }
  },

  generateScript: async (projectId, novelId) => {
    set({ generationTask: { taskId: null, status: 'running' } })
    try {
      const res = await novelApi.generateScript(projectId, novelId)
      const taskId = res.data?.task_id
      if (taskId) {
        set({ generationTask: { taskId, status: 'running' } })
        return taskId
      }
      throw new Error('未返回 task_id')
    } catch (e) {
      set({ generationTask: { taskId: null, status: 'failed' } })
      console.error('生成脚本失败:', e)
      throw e
    }
  },

  saveScript: async (projectId, novelId, chapters) => {
    set({ scriptLoading: true })
    try {
      const res = await novelApi.saveScript(projectId, novelId, chapters)
      set({ scriptData: res.data?.chapters || [] })
      return res.data
    } catch (e) {
      console.error('保存脚本失败:', e)
      throw e
    } finally {
      set({ scriptLoading: false })
    }
  },

  splitShot: async (projectId, novelId, chapterId, shotId, contentBefore, contentAfter) => {
    try {
      const res = await novelApi.splitShot(
        projectId, novelId, chapterId, shotId, contentBefore, contentAfter
      )
      set({ scriptData: res.data?.chapters || [] })
      return res.data
    } catch (e) {
      console.error('拆分镜头失败:', e)
      throw e
    }
  },

  deleteScript: async (projectId, novelId) => {
    set({ scriptDeleting: true })
    try {
      await novelApi.deleteScript(projectId, novelId)
      set({ scriptData: [], generationTask: { taskId: null, status: 'idle' } })
    } catch (e) {
      console.error('删除脚本失败:', e)
      throw e
    } finally {
      set({ scriptDeleting: false })
    }
  },

  updateGenerationTask: (taskId, status) => {
    set({ generationTask: { taskId, status } })
  },
}))
