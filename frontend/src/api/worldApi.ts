import apiClient from './client'
import type { ApiResponse } from '../types'
import type {
  WorldBuilding,
  SceneAsset,
  Prop,
  Building,
  Outfit,
  StyleTemplate,
  PaginatedItems,
} from '../types/world'

// ======================================================================
// 世界观 API
// ======================================================================

export interface CreateWorldParams {
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
}

export interface UpdateWorldParams {
  name?: string
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
}

export const worldApi = {
  list: (projectId: string, params?: { skip?: number; limit?: number }) =>
    apiClient.get<ApiResponse<PaginatedItems<WorldBuilding>>>(
      `/projects/${projectId}/worlds`,
      { params },
    ),

  getById: (projectId: string, worldId: string) =>
    apiClient.get<ApiResponse<WorldBuilding>>(
      `/projects/${projectId}/worlds/${worldId}`,
    ),

  create: (projectId: string, data: CreateWorldParams) =>
    apiClient.post<ApiResponse<WorldBuilding>>(
      `/projects/${projectId}/worlds`,
      data,
    ),

  update: (projectId: string, worldId: string, data: UpdateWorldParams) =>
    apiClient.put<ApiResponse<WorldBuilding>>(
      `/projects/${projectId}/worlds/${worldId}`,
      data,
    ),

  delete: (projectId: string, worldId: string) =>
    apiClient.delete<ApiResponse<null>>(
      `/projects/${projectId}/worlds/${worldId}`,
    ),

  aiAssist: (projectId: string, data: { novel_text: string }) =>
    apiClient.post<ApiResponse<CreateWorldParams>>(
      `/projects/${projectId}/worlds/ai-assist`,
      data,
    ),

  aiCreate: (projectId: string, data: { novel_text: string }) =>
    apiClient.post<ApiResponse<WorldBuilding>>(
      `/projects/${projectId}/worlds/ai-create`,
      data,
    ),
}

// ======================================================================
// 场景资产 API
// ======================================================================

export interface CreateSceneAssetParams {
  name: string
  description?: string
  season?: string
  weather?: string
  time_of_day?: string
  lighting?: string
  atmosphere?: string
  tags?: string[]
}

export const sceneAssetApi = {
  list: (projectId: string, worldId: string) =>
    apiClient.get<ApiResponse<PaginatedItems<SceneAsset>>>(
      `/projects/${projectId}/worlds/${worldId}/scene-assets`,
    ),

  create: (projectId: string, worldId: string, data: CreateSceneAssetParams) =>
    apiClient.post<ApiResponse<SceneAsset>>(
      `/projects/${projectId}/worlds/${worldId}/scene-assets`,
      data,
    ),

  update: (
    projectId: string,
    worldId: string,
    assetId: string,
    data: Partial<CreateSceneAssetParams>,
  ) =>
    apiClient.put<ApiResponse<SceneAsset>>(
      `/projects/${projectId}/worlds/${worldId}/scene-assets/${assetId}`,
      data,
    ),

  delete: (projectId: string, worldId: string, assetId: string) =>
    apiClient.delete<ApiResponse<null>>(
      `/projects/${projectId}/worlds/${worldId}/scene-assets/${assetId}`,
    ),

  aiExtract: (projectId: string, worldId: string, data: { novel_text: string }) =>
    apiClient.post<ApiResponse<PaginatedItems<SceneAsset>>>(
      `/projects/${projectId}/worlds/${worldId}/scene-assets/ai-extract`,
      data,
    ),
  aiExtractProps: (projectId: string, worldId: string, data: { novel_text: string }) =>
    apiClient.post<ApiResponse<PaginatedItems<Prop>>>(
      `/projects/${projectId}/worlds/${worldId}/props/ai-extract`,
      data,
    ),
  aiExtractBuildings: (projectId: string, worldId: string, data: { novel_text: string }) =>
    apiClient.post<ApiResponse<PaginatedItems<Building>>>(
      `/projects/${projectId}/worlds/${worldId}/buildings/ai-extract`,
      data,
    ),
  aiExtractOutfits: (projectId: string, worldId: string, data: { novel_text: string }) =>
    apiClient.post<ApiResponse<PaginatedItems<Outfit>>>(
      `/projects/${projectId}/worlds/${worldId}/outfits/ai-extract`,
      data,
    ),
  generateSceneImage: (projectId: string, worldId: string, assetId: string) =>
    apiClient.post<ApiResponse<{ image_url: string }>>(
      `/projects/${projectId}/worlds/${worldId}/scene-assets/${assetId}/generate-image`,
    ),
  generatePropImage: (projectId: string, worldId: string, propId: string) =>
    apiClient.post<ApiResponse<{ image_url: string }>>(
      `/projects/${projectId}/worlds/${worldId}/props/${propId}/generate-image`,
    ),
  generateBuildingImage: (projectId: string, worldId: string, buildingId: string) =>
    apiClient.post<ApiResponse<{ image_url: string }>>(
      `/projects/${projectId}/worlds/${worldId}/buildings/${buildingId}/generate-image`,
    ),
  generateOutfitImage: (projectId: string, worldId: string, outfitId: string) =>
    apiClient.post<ApiResponse<{ image_url: string }>>(
      `/projects/${projectId}/worlds/${worldId}/outfits/${outfitId}/generate-image`,
    ),
}

// ======================================================================
// 道具 API
// ======================================================================

export interface CreatePropParams {
  name: string
  category?: string
  description?: string
  visual_description?: string
  tags?: string[]
}

export const propApi = {
  list: (projectId: string, worldId: string) =>
    apiClient.get<ApiResponse<PaginatedItems<Prop>>>(
      `/projects/${projectId}/worlds/${worldId}/props`,
    ),

  create: (projectId: string, worldId: string, data: CreatePropParams) =>
    apiClient.post<ApiResponse<Prop>>(
      `/projects/${projectId}/worlds/${worldId}/props`,
      data,
    ),

  update: (projectId: string, worldId: string, propId: string, data: Partial<CreatePropParams>) =>
    apiClient.put<ApiResponse<Prop>>(
      `/projects/${projectId}/worlds/${worldId}/props/${propId}`,
      data,
    ),

  delete: (projectId: string, worldId: string, propId: string) =>
    apiClient.delete<ApiResponse<null>>(
      `/projects/${projectId}/worlds/${worldId}/props/${propId}`,
    ),

  generateImage: (projectId: string, worldId: string, propId: string) =>
    apiClient.post<ApiResponse<{ image_url: string }>>(
      `/projects/${projectId}/worlds/${worldId}/props/${propId}/generate-image`,
    ),
}

// ======================================================================
// 建筑 API
// ======================================================================

export interface CreateBuildingParams {
  name: string
  style?: string
  description?: string
  interior_description?: string
  reference_images?: string[]
}

export const buildingApi = {
  list: (projectId: string, worldId: string) =>
    apiClient.get<ApiResponse<PaginatedItems<Building>>>(
      `/projects/${projectId}/worlds/${worldId}/buildings`,
    ),

  create: (projectId: string, worldId: string, data: CreateBuildingParams) =>
    apiClient.post<ApiResponse<Building>>(
      `/projects/${projectId}/worlds/${worldId}/buildings`,
      data,
    ),

  update: (projectId: string, worldId: string, buildingId: string, data: Partial<CreateBuildingParams>) =>
    apiClient.put<ApiResponse<Building>>(
      `/projects/${projectId}/worlds/${worldId}/buildings/${buildingId}`,
      data,
    ),

  delete: (projectId: string, worldId: string, buildingId: string) =>
    apiClient.delete<ApiResponse<null>>(
      `/projects/${projectId}/worlds/${worldId}/buildings/${buildingId}`,
    ),

  generateImage: (projectId: string, worldId: string, buildingId: string) =>
    apiClient.post<ApiResponse<{ image_url: string }>>(
      `/projects/${projectId}/worlds/${worldId}/buildings/${buildingId}/generate-image`,
    ),
}

// ======================================================================
// 服装 API
// ======================================================================

export interface CreateOutfitParams {
  name: string
  style?: string
  color_scheme?: Record<string, unknown>
  description?: string
}

export const outfitApi = {
  list: (projectId: string, worldId: string) =>
    apiClient.get<ApiResponse<PaginatedItems<Outfit>>>(
      `/projects/${projectId}/worlds/${worldId}/outfits`,
    ),

  create: (projectId: string, worldId: string, data: CreateOutfitParams) =>
    apiClient.post<ApiResponse<Outfit>>(
      `/projects/${projectId}/worlds/${worldId}/outfits`,
      data,
    ),

  update: (projectId: string, worldId: string, outfitId: string, data: Partial<CreateOutfitParams>) =>
    apiClient.put<ApiResponse<Outfit>>(
      `/projects/${projectId}/worlds/${worldId}/outfits/${outfitId}`,
      data,
    ),

  delete: (projectId: string, worldId: string, outfitId: string) =>
    apiClient.delete<ApiResponse<null>>(
      `/projects/${projectId}/worlds/${worldId}/outfits/${outfitId}`,
    ),

  generateImage: (projectId: string, worldId: string, outfitId: string) =>
    apiClient.post<ApiResponse<{ image_url: string }>>(
      `/projects/${projectId}/worlds/${worldId}/outfits/${outfitId}/generate-image`,
    ),
}

// ======================================================================
// 风格模板 API
// ======================================================================

export interface CreateTemplateParams {
  name: string
  aspect_ratio?: string
  width?: number
  art_style?: string
  coloring_style?: string
  lineart_style?: string
  lighting_style?: string
  negative_prompt?: string
  is_default?: boolean
}

export interface UpdateTemplateParams {
  name?: string
  aspect_ratio?: string
  width?: number
  art_style?: string
  coloring_style?: string
  lineart_style?: string
  lighting_style?: string
  negative_prompt?: string
  is_default?: boolean
}

export const templateApi = {
  list: (projectId: string) =>
    apiClient.get<ApiResponse<PaginatedItems<StyleTemplate>>>(
      `/projects/${projectId}/style-templates`,
    ),

  getById: (projectId: string, templateId: string) =>
    apiClient.get<ApiResponse<StyleTemplate>>(
      `/projects/${projectId}/style-templates/${templateId}`,
    ),

  create: (projectId: string, data: CreateTemplateParams) =>
    apiClient.post<ApiResponse<StyleTemplate>>(
      `/projects/${projectId}/style-templates`,
      data,
    ),

  update: (projectId: string, templateId: string, data: UpdateTemplateParams) =>
    apiClient.put<ApiResponse<StyleTemplate>>(
      `/projects/${projectId}/style-templates/${templateId}`,
      data,
    ),

  delete: (projectId: string, templateId: string) =>
    apiClient.delete<ApiResponse<null>>(
      `/projects/${projectId}/style-templates/${templateId}`,
    ),

  setDefault: (projectId: string, templateId: string) =>
    apiClient.post<ApiResponse<StyleTemplate>>(
      `/projects/${projectId}/style-templates/${templateId}/set-default`,
    ),
}
