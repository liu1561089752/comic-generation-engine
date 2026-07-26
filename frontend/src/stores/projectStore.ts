import { create } from 'zustand'
import type { Project } from '../types/project'
import { projectApi } from '../api/projectApi'

interface FetchProjectsParams {
  page?: number
  page_size?: number
  status?: string
  project_type?: string
  sort_by?: string
  sort_order?: 'asc' | 'desc'
}

interface ProjectState {
  projects: Project[]
  currentProject: Project | null
  loading: boolean
  total: number
  error: string | null
  fetchProjects: (params?: FetchProjectsParams) => Promise<void>
  fetchProject: (id: string) => Promise<void>
  setCurrentProject: (project: Project | null) => void
  // D58: 请求 ID 追踪，防止快速切换项目时旧请求覆写新数据
  _fetchProjectRequestId: number
}

export const useProjectStore = create<ProjectState>((set, get) => ({
  projects: [],
  currentProject: null,
  loading: false,
  total: 0,
  error: null,
  _fetchProjectRequestId: 0,
  fetchProjects: async (params) => {
    set({ loading: true, error: null })
    try {
      const res = await projectApi.list(params)
      set({ projects: res.data?.items ?? [], total: res.data?.total ?? 0 })
    } catch (e) {
      // D77: 设置错误状态供 UI 感知
      set({ error: '获取项目列表失败' })
      console.error('获取项目列表失败:', e)
    } finally {
      set({ loading: false })
    }
  },
  fetchProject: async (id) => {
    // D58: 请求 ID 追踪——快速切换项目时丢弃旧请求的响应
    const requestId = get()._fetchProjectRequestId + 1
    set({ loading: true, error: null, _fetchProjectRequestId: requestId })
    try {
      const res = await projectApi.get(id)
      if (get()._fetchProjectRequestId !== requestId) return
      set({ currentProject: res.data ?? null })
    } catch (e) {
      if (get()._fetchProjectRequestId !== requestId) return
      set({ error: '获取项目详情失败' })
      console.error('获取项目详情失败:', e)
    } finally {
      if (get()._fetchProjectRequestId === requestId) {
        set({ loading: false })
      }
    }
  },
  setCurrentProject: (project) => set({ currentProject: project }),
}))
