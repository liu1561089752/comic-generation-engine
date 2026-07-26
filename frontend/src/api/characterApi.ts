import apiClient from './client'
import type { ApiResponse } from '../types'
import type { Character, CharacterRelation, CharacterOutfit, CharacterExpression } from '../types/character'

export interface CreateCharacterParams {
  name: string
}

export interface UpdateCharacterParams {
  name?: string
  aliases?: string
  description?: string
  role_type?: string
}

export interface CreateRelationParams {
  character_b_id: string
  relation_type_a_to_b: string
  relation_type_b_to_a: string
  description?: string
}

export interface CreateOutfitParams {
  name: string
  outfit_type: string
  description: string
  color_scheme?: string[]
  scene_tags?: string[]
}

export interface CreateExpressionParams {
  name: string
  expression_type?: string
  description?: string
  reference_image_url?: string
}

export interface UpdateExpressionParams {
  name?: string
  expression_type?: string
  description?: string
  reference_image_url?: string
}

export const characterApi = {
  list: (projectId: string, params?: { search?: string }) =>
    apiClient.get<ApiResponse<{ items: Character[]; total: number }>>(`/projects/${projectId}/characters`, { params }),

  listAll: (params?: { search?: string }) =>
    apiClient.get<ApiResponse<{ items: Character[]; total: number }>>('/characters', { params }),

  getById: (projectId: string, characterId: string) =>
    apiClient.get<ApiResponse<Character>>(`/projects/${projectId}/characters/${characterId}`),

  create: (projectId: string, data: CreateCharacterParams) =>
    apiClient.post<ApiResponse<Character>>(`/projects/${projectId}/characters`, data),

  update: (projectId: string, characterId: string, data: UpdateCharacterParams) =>
    apiClient.put<ApiResponse<Character>>(`/projects/${projectId}/characters/${characterId}`, data),

  delete: (projectId: string, characterId: string) =>
    apiClient.delete<ApiResponse<null>>(`/projects/${projectId}/characters/${characterId}`),

  extract: (projectId: string, novelText: string) =>
    apiClient.post<ApiResponse<{ items: Character[]; total: number }>>(`/projects/${projectId}/characters/extract`, { novel_text: novelText }),

  generateImage: (projectId: string, characterId: string) =>
    apiClient.post<ApiResponse<{ image_url: string; character_name: string }>>(`/projects/${projectId}/characters/${characterId}/generate-image`),

  listRelations: (projectId: string, characterId: string) =>
    apiClient.get<ApiResponse<CharacterRelation[]>>(`/projects/${projectId}/characters/${characterId}/relations`),

  createRelation: (projectId: string, characterId: string, data: CreateRelationParams) =>
    apiClient.post<ApiResponse<CharacterRelation>>(`/projects/${projectId}/characters/${characterId}/relations`, data),

  listOutfits: (projectId: string, characterId: string) =>
    apiClient.get<ApiResponse<{ items: CharacterOutfit[] }>>(`/projects/${projectId}/characters/${characterId}/outfits`),

  createOutfit: (projectId: string, characterId: string, data: CreateOutfitParams) =>
    apiClient.post<ApiResponse<CharacterOutfit>>(`/projects/${projectId}/characters/${characterId}/outfits`, data),

  listExpressions: (projectId: string, characterId: string) =>
    apiClient.get<ApiResponse<{ items: CharacterExpression[] }>>(`/projects/${projectId}/characters/${characterId}/expressions`),

  createExpression: (projectId: string, characterId: string, data: CreateExpressionParams) =>
    apiClient.post<ApiResponse<CharacterExpression>>(`/projects/${projectId}/characters/${characterId}/expressions`, data),

  updateExpression: (projectId: string, characterId: string, expressionId: string, data: UpdateExpressionParams) =>
    apiClient.put<ApiResponse<CharacterExpression>>(`/projects/${projectId}/characters/${characterId}/expressions/${expressionId}`, data),

  deleteExpression: (projectId: string, characterId: string, expressionId: string) =>
    apiClient.delete<ApiResponse<null>>(`/projects/${projectId}/characters/${characterId}/expressions/${expressionId}`),
}
