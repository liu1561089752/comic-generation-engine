export interface ProductionStage {
  key: string
  label: string
  status: 'pending' | 'in_progress' | 'completed'
  path?: string
}

export interface ProductionProgress {
  stages: ProductionStage[]
  overall_progress?: number
}

export interface Project {
  id: string
  name: string
  description?: string
  status: string
  project_type?: string
  cover_image_url?: string
  completion_percentage?: number
  production_progress?: ProductionProgress
  created_at: string
  updated_at: string
}
