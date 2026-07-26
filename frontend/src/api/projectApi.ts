import apiClient from './client'
import type { ApiResponse } from '../types'
import type { Project } from '../types/project'

type ListResponse<T> = { items: T[]; total: number }

export interface CreateProjectParams {
  name: string
  description?: string
  project_type?: string
}

export interface UpdateProjectParams {
  name?: string
  description?: string
  status?: string
  project_type?: string
}

export const projectApi = {
  list: (params?: {
    page?: number
    page_size?: number
    status?: string
    project_type?: string
    sort_by?: string
    sort_order?: 'asc' | 'desc'
  }) =>
    apiClient.get<ApiResponse<ListResponse<Project>>>('/projects', { params }),

  get: (id: string) =>
    apiClient.get<ApiResponse<Project>>(`/projects/${id}`),

  create: (params: CreateProjectParams) =>
    apiClient.post<ApiResponse<Project>>('/projects', params),

  update: (id: string, params: UpdateProjectParams) =>
    apiClient.put<ApiResponse<Project>>(`/projects/${id}`, params),

  delete: (id: string) =>
    apiClient.delete<ApiResponse<null>>(`/projects/${id}`),

  duplicate: (id: string) =>
    apiClient.post<ApiResponse<Project>>(`/projects/${id}/duplicate`),

  checkName: (name: string) =>
    apiClient.get<ApiResponse<{ exists: boolean }>>('/projects/check-name', { params: { name } }),
}
