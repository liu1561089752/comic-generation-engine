import apiClient from './client'

export const qualityApi = {
  checkConsistency: (projectId: string, imageId: string) =>
    apiClient.post(`/projects/${projectId}/images/${imageId}/check-consistency`),

  getConsistencyReport: (projectId: string, imageId: string) =>
    apiClient.get(`/projects/${projectId}/images/${imageId}/consistency-report`),

  scoreQuality: (projectId: string, imageId: string) =>
    apiClient.post(`/projects/${projectId}/images/${imageId}/quality-score`),

  listPending: (projectId: string) =>
    apiClient.get(`/projects/${projectId}/quality-check/pending`),

  submitReview: (projectId: string, checkId: string, action: string, note?: string) =>
    apiClient.post(`/projects/${projectId}/quality-check/${checkId}/review`, { action, note }),

  // ====== 新增：质量报告 API ======
  listReports: (projectId: string, params?: { skip?: number; limit?: number }) =>
    apiClient.get(`/projects/${projectId}/quality/reports`, { params }),

  getReportDetail: (projectId: string, reportId: string) =>
    apiClient.get(`/projects/${projectId}/quality/reports/${reportId}`),

  createReport: (projectId: string, params: { scope?: string; panel_ids?: string[] }) =>
    apiClient.post(`/projects/${projectId}/quality/reports`, params),

  approveImage: (projectId: string, imageId: string, note?: string) =>
    apiClient.post(`/projects/${projectId}/quality/${imageId}/approve`, { note }),

  rejectImage: (projectId: string, imageId: string, note?: string) =>
    apiClient.post(`/projects/${projectId}/quality/${imageId}/reject`, { note }),
}
