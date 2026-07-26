export interface LLMConfig {
  id?: string
  api_base: string
  api_key: string
  model_name: string
  is_active?: boolean
}

export interface ImageModelConfig {
  id?: string
  api_base: string
  api_key: string
  model_name: string
  is_active?: boolean
}

export interface ModelPreset {
  id: string
  name: string
  steps: number
  cfg_scale: number
  width: number
  height: number
  is_default?: boolean
}

export interface ModelLog {
  id: string
  model_type: string
  model_name: string
  call_type: string
  duration_ms: number
  prompt_tokens?: number
  completion_tokens?: number
  total_tokens?: number
  status: string
  error_message?: string
  created_at: string
}

export const LOG_TYPE_MAP: Record<string, string> = {
  llm_chat: 'LLM 对话',
  llm_embedding: 'LLM Embedding',
  image_generation: '生图',
  image_variation: '图生图',
}

export const LOG_STATUS_COLOR: Record<string, string> = {
  success: 'success',
  failed: 'error',
  running: 'processing',
}

export const LOG_STATUS_LABEL: Record<string, string> = {
  success: '成功',
  failed: '失败',
  running: '运行中',
}
