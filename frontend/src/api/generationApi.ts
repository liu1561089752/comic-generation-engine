import apiClient from './client'

export const generationApi = {
  generate: (projectId: string, panelId: string, params: any) =>
    apiClient.post(`/projects/${projectId}/panels/${panelId}/generate`, params),

  getTaskStatus: (projectId: string, taskId: string) =>
    apiClient.get(`/projects/${projectId}/tasks/${taskId}/status`),

  listImages: (projectId: string, panelId: string) =>
    apiClient.get(`/projects/${projectId}/panels/${panelId}/images`),

  selectImage: (projectId: string, imageId: string) =>
    apiClient.put(`/projects/${projectId}/images/${imageId}/select`),

  batchGenerate: (projectId: string, panelId: string, panelIds: string[], params: any) =>
    apiClient.post(`/projects/${projectId}/panels/${panelId}/generate-batch`, { panel_ids: panelIds, ...params }),
}
