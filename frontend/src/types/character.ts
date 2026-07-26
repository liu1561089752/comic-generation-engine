export interface Character {
  id: string
  project_id: string
  name: string
  aliases?: string
  description?: string
  role_type?: string
  image_url?: string
  status: string
  created_at: string
  updated_at: string
}

export interface CharacterRelation {
  id: string
  character_a_id: string
  character_b_id: string
  relation_type_a_to_b: string
  relation_type_b_to_a: string
  description?: string
}

export interface CharacterOutfit {
  id: string
  character_id: string
  name: string
  outfit_type: string
  description: string
  color_scheme?: string[]
  scene_tags?: string[]
}

export interface CharacterExpression {
  id: string
  character_id: string
  name: string
  expression_type?: string
  description?: string
  reference_image_url?: string
  created_at: string
  updated_at: string
}

export const EXPRESSION_TYPE_MAP: Record<string, string> = {
  happy: '高兴',
  sad: '悲伤',
  angry: '愤怒',
  surprised: '惊讶',
  fearful: '恐惧',
  disgusted: '厌恶',
  calm: '平静',
  neutral: '中性',
}
