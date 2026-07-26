export interface TaskItem {
  id: string
  project_id: string | null
  task_type: string
  status: string
  priority: string
  progress: number
  input_data: any
  output_data: any
  logs: string[]
  error_message: string | null
  started_at: string | null
  completed_at: string | null
  created_at: string | null
  updated_at: string | null
}

export interface QueueData {
  [status: string]: {
    items: TaskItem[]
    total: number
  }
}

export const STATUS_FILTERS = [
  { value: '', label: '全部状态' },
  { value: 'queued', label: '排队中' },
  { value: 'running', label: '处理中' },
  { value: 'completed', label: '已完成' },
  { value: 'failed', label: '失败' },
  { value: 'cancelled', label: '已取消' },
]

export const TYPE_FILTERS = [
  { value: '', label: '全部类型' },
  { value: 'analysis', label: '分析' },
  { value: 'generation', label: '生图' },
  { value: 'export', label: '导出' },
]

export const PRIORITY_FILTERS = [
  { value: '', label: '全部优先级' },
  { value: 'low', label: '低' },
  { value: 'normal', label: '普通' },
  { value: 'high', label: '高' },
  { value: 'urgent', label: '紧急' },
]

export const SORT_OPTIONS = [
  { value: 'created_at', label: '创建时间' },
  { value: 'priority', label: '优先级' },
  { value: 'status', label: '状态' },
]

export const PRIORITY_COLORS: Record<string, string> = {
  low: 'default',
  normal: 'blue',
  high: 'orange',
  urgent: 'red',
}

export const PRIORITY_LABELS: Record<string, string> = {
  low: '低',
  normal: '普通',
  high: '高',
  urgent: '紧急',
}

export const TYPE_LABELS: Record<string, string> = {
  analysis: '分析',
  generation: '生图',
  export: '导出',
}
