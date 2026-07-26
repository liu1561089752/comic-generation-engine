import apiClient from './client'

export const modelApi = {
  getLLMConfig: () => apiClient.get('/models/llm'),
  updateLLMConfig: (data: any) => apiClient.put('/models/llm', data),
  testLLM: () => apiClient.post('/models/llm/test'),

  getImageModelConfig: () => apiClient.get('/models/image-gen'),
  updateImageModelConfig: (data: any) => apiClient.put('/models/image-gen', data),
  testImageModel: () => apiClient.post('/models/image-gen/test'),

  getModelLogs: (params?: any) => apiClient.get('/models/logs', { params }),
}
