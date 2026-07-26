import apiClient from './client'
import type { ApiResponse, PaginatedResponse } from '../types'

export interface ExportParams {
  format: 'long_image' | 'png_sequence' | 'jpg'
  quality: number
  add_alias?: boolean
  alias_name?: string
}

export interface ExportTask {
  id: string
  project_id: string
  format: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  progress: number
  file_url?: string
  file_size?: number
  export_dir?: string
  folder_name?: string
  file_count?: number
  created_at: string
  updated_at: string
}

export interface ExportProgress {
  task_id: string
  status: string
  progress: number
  message: string
}

export const exportApi = {
  /** 创建导出任务 */
  create: (projectId: string, params: ExportParams) =>
    apiClient.post<ApiResponse<ExportTask>>(`/projects/${projectId}/export`, params),

  /** 获取导出任务列表 */
  list: (projectId: string, params?: { page?: number; page_size?: number }) =>
    apiClient.get<PaginatedResponse<ExportTask>>(`/projects/${projectId}/export/history`, { params }),

  /** 获取导出任务详情 */
  get: (projectId: string, taskId: string) =>
    apiClient.get<ApiResponse<ExportTask>>(`/projects/${projectId}/export/${taskId}`),

  /** 取消导出任务 */
  cancel: (projectId: string, taskId: string) =>
    apiClient.post<ApiResponse<null>>(`/projects/${projectId}/export/${taskId}/cancel`),

  /** 获取导出进度 */
  getProgress: (projectId: string, taskId: string) =>
    apiClient.get<ApiResponse<ExportProgress>>(`/projects/${projectId}/export/${taskId}/progress`),

  /** 下载导出文件 */
  download: (projectId: string, taskId: string) =>
    apiClient.get<Blob>(`/projects/${projectId}/export/${taskId}/download`, {
      responseType: 'blob',
    }),
}
