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

export const STATUS_FILTERS = [
  { value: '', label: '全部状态' },
  { value: 'queued', label: '排队中' },
  { value: 'running', label: '处理中' },
  { value: 'completed', label: '已完成' },
  { value: 'failed', label: '失败' },
  { value: 'cancelled', label: '已取消' },
]

export const TYPE_LABELS: Record<string, string> = {
  analysis: '分析',
  generation: '生图',
  export: '导出',
  // 小说管线任务
  preprocess_novel: '预处理小说',
  generate_script: '生成脚本',
  generate_storyboard: '生成分镜',
  generate_layout: '生成排版',
  generate_image_prompts: '生成提示词',
  regenerate_page_prompt: '重新生成提示词',
  match_references: '匹配参考图',
  generate_single_image: '单页生图',
  generate_page_images: '批量生图',
  // 人物IP任务
  extract_characters: '提取角色',
  generate_character_image: '生成形象',
  generate_state_image: '生成状态形象',
  // 世界观任务
  ai_create_world: '创建世界观',
  ai_extract_scenes: '提取场景',
  ai_extract_props: '提取道具',
  ai_extract_buildings: '提取建筑',
  ai_extract_outfits: '提取服装',
  generate_scene_image: '生成场景图片',
  generate_prop_image: '生成道具图片',
  generate_building_image: '生成建筑图片',
  generate_outfit_image: '生成服装图片',
}

// 任务类型过滤：从 TYPE_LABELS 生成（与实际任务类型一致，避免过滤下拉不全）
export const TYPE_FILTERS = [
  { value: '', label: '全部类型' },
  ...Object.entries(TYPE_LABELS).map(([value, label]) => ({ value, label })),
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
