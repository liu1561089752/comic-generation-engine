export interface PendingPanel {
  id: string
  panel_number: number
  thumbnail_url?: string
  status: string
  created_at: string
}

export interface ConsistencyDimension {
  dimension: string
  expected: string
  detected: string
  match: boolean
  confidence: number
}

export interface ConsistencyReport {
  panel_id: string
  checks: {
    character_name: string
    overall_match: boolean
    dimensions: ConsistencyDimension[]
  }[]
  passed: boolean
  overall_score: number
}

export interface QualityScore {
  dimension: string
  score: number
  weight: number
  comment: string
}

export interface QualityReport {
  panel_id: string
  scores: QualityScore[]
  overall_score: number
  defects: string[]
  recommendation: string
}

export interface PanelOption {
  id: string
  panel_number: number
}

export const DIMENSION_LABELS: Record<string, string> = {
  hair_color: '发色',
  hair_style: '发型',
  eye_color: '瞳色',
  skin_tone: '肤色',
  clothing: '服装',
  composition: '构图',
  character_integrity: '角色完整度',
  lighting: '光照',
  detail: '细节',
  style_consistency: '风格一致性',
}

export const RECOMMENDATION_MAP: Record<string, { color: string; text: string }> = {
  best: { color: '#52c41a', text: '最佳' },
  recommended: { color: '#1677ff', text: '推荐' },
  acceptable: { color: '#faad14', text: '可接受' },
  rejected: { color: '#ff4d4f', text: '不通过' },
}
