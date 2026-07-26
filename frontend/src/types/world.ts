// 世界观
export interface WorldBuilding {
  id: string
  project_id: string
  name: string
  era?: string
  era_type?: string
  time_span?: string
  background?: string
  core_tags?: string[]
  region_style?: string
  civilization_level?: string
  description?: string
  settings?: Record<string, unknown>
  cover_image?: string
  created_at: string
  updated_at: string
}

// 场景资产
export interface SceneAsset {
  id: string
  world_id: string
  name: string
  description?: string
  season?: string
  weather?: string
  time_of_day?: string
  lighting?: string
  atmosphere?: string
  tags?: string[]
  image_url?: string
  created_at: string
  updated_at: string
}

// 道具
export interface Prop {
  id: string
  world_id: string
  name: string
  category?: string
  description?: string
  visual_description?: string
  tags?: string[]
  image_url?: string
}

// 建筑
export interface Building {
  id: string
  world_id: string
  name: string
  style?: string
  interior_exterior?: string
  description?: string
  interior_description?: string
  reference_images?: string[]
  image_url?: string
}

// 服装
export interface Outfit {
  id: string
  world_id: string
  name: string
  style?: string
  color_scheme?: Record<string, unknown>
  description?: string
  belongs_to_character?: string
  image_url?: string
}

// 风格模板
export interface StyleTemplate {
  id: string
  project_id: string
  name: string
  aspect_ratio?: string
  width?: number
  art_style?: string
  coloring_style?: string
  lineart_style?: string
  lighting_style?: string
  negative_prompt?: string
  is_default?: boolean
  created_at: string
  updated_at: string
}

export interface PaginatedItems<T> {
  items: T[]
  total: number
  skip?: number
  limit?: number
}
