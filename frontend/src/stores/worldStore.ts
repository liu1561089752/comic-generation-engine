import { create } from 'zustand'
import type {
  WorldBuilding,
  SceneAsset,
  Prop,
  Building,
  Outfit,
} from '../types/world'
import {
  worldApi,
  sceneAssetApi,
  propApi,
  buildingApi,
  outfitApi,
} from '../api/worldApi'
import type {
  UpdateWorldParams,
  CreateSceneAssetParams,
  CreatePropParams,
  CreateBuildingParams,
  CreateOutfitParams,
} from '../api/worldApi'
import { message } from 'antd'

interface WorldState {
  // 世界观
  worlds: WorldBuilding[]
  currentWorld: WorldBuilding | null
  // 子资产
  sceneAssets: SceneAsset[]
  props: Prop[]
  buildings: Building[]
  outfits: Outfit[]
  loading: boolean

  // 世界观
  fetchWorlds: (projectId: string) => Promise<void>
  fetchWorld: (projectId: string, worldId: string) => Promise<void>
  updateWorld: (projectId: string, worldId: string, data: UpdateWorldParams) => Promise<void>
  deleteWorld: (projectId: string, worldId: string) => Promise<void>

  // 场景资产
  fetchSceneAssets: (projectId: string, worldId: string) => Promise<void>
  createSceneAsset: (projectId: string, worldId: string, data: CreateSceneAssetParams) => Promise<void>
  updateSceneAsset: (projectId: string, worldId: string, assetId: string, data: Partial<CreateSceneAssetParams>) => Promise<void>
  deleteSceneAsset: (projectId: string, worldId: string, assetId: string) => Promise<void>
  aiExtractScenes: (projectId: string, worldId: string, novelText: string) => Promise<string>
  aiExtractProps: (projectId: string, worldId: string, novelText: string) => Promise<string>
  aiExtractBuildings: (projectId: string, worldId: string, novelText: string) => Promise<string>
  aiExtractOutfits: (projectId: string, worldId: string, novelText: string) => Promise<string>
  generateSceneImage: (projectId: string, worldId: string, assetId: string) => Promise<string>
  generatePropImage: (projectId: string, worldId: string, propId: string) => Promise<string>
  generateBuildingImage: (projectId: string, worldId: string, buildingId: string) => Promise<string>
  generateOutfitImage: (projectId: string, worldId: string, outfitId: string) => Promise<string>

  // 道具
  fetchProps: (projectId: string, worldId: string) => Promise<void>
  createProp: (projectId: string, worldId: string, data: CreatePropParams) => Promise<void>
  updateProp: (projectId: string, worldId: string, propId: string, data: Partial<CreatePropParams>) => Promise<void>
  deleteProp: (projectId: string, worldId: string, propId: string) => Promise<void>

  // 建筑
  fetchBuildings: (projectId: string, worldId: string) => Promise<void>
  createBuilding: (projectId: string, worldId: string, data: CreateBuildingParams) => Promise<void>
  updateBuilding: (projectId: string, worldId: string, buildingId: string, data: Partial<CreateBuildingParams>) => Promise<void>
  deleteBuilding: (projectId: string, worldId: string, buildingId: string) => Promise<void>

  // 服装
  fetchOutfits: (projectId: string, worldId: string) => Promise<void>
  createOutfit: (projectId: string, worldId: string, data: CreateOutfitParams) => Promise<void>
  updateOutfit: (projectId: string, worldId: string, outfitId: string, data: Partial<CreateOutfitParams>) => Promise<void>
  deleteOutfit: (projectId: string, worldId: string, outfitId: string) => Promise<void>

  // AI辅助
  aiAssistWorld: (projectId: string, novelText: string) => Promise<any>
  aiCreateWorld: (projectId: string, novelText: string) => Promise<string>

  // D58: 请求 ID 追踪，防止快速切换项目/世界观时旧请求覆写新数据
  _fetchWorldsRequestId: number
  _fetchWorldRequestId: number
  _fetchSceneAssetsRequestId: number
  _fetchPropsRequestId: number
  _fetchBuildingsRequestId: number
  _fetchOutfitsRequestId: number
}

export const useWorldStore = create<WorldState>((set, get) => ({
  worlds: [],
  currentWorld: null,
  sceneAssets: [],
  props: [],
  buildings: [],
  outfits: [],
  loading: false,
  _fetchWorldsRequestId: 0,
  _fetchWorldRequestId: 0,
  _fetchSceneAssetsRequestId: 0,
  _fetchPropsRequestId: 0,
  _fetchBuildingsRequestId: 0,
  _fetchOutfitsRequestId: 0,

  // ======================================================================
  // 世界观
  // ======================================================================

  fetchWorlds: async (projectId) => {
    const requestId = get()._fetchWorldsRequestId + 1
    set({ loading: true, _fetchWorldsRequestId: requestId })
    try {
      const res = await worldApi.list(projectId)
      if (get()._fetchWorldsRequestId !== requestId) return
      set({ worlds: res.data?.items ?? [] })
    } catch (e) {
      console.error('获取世界观列表失败:', e)
      if (get()._fetchWorldsRequestId === requestId) {
        set({ worlds: [] })
      }
      throw e
    } finally {
      if (get()._fetchWorldsRequestId === requestId) {
        set({ loading: false })
      }
    }
  },

  fetchWorld: async (projectId, worldId) => {
    const requestId = get()._fetchWorldRequestId + 1
    set({ loading: true, _fetchWorldRequestId: requestId })
    try {
      const res = await worldApi.getById(projectId, worldId)
      if (get()._fetchWorldRequestId !== requestId) return
      set({ currentWorld: res.data })
    } catch (e) {
      console.error('获取世界观详情失败:', e)
      if (get()._fetchWorldRequestId === requestId) {
        set({ currentWorld: null })
      }
      throw e
    } finally {
      if (get()._fetchWorldRequestId === requestId) {
        set({ loading: false })
      }
    }
  },

  updateWorld: async (projectId, worldId, data) => {
    set({ loading: true })
    try {
      const res = await worldApi.update(projectId, worldId, data)
      set({ currentWorld: res.data })
    } catch (e) {
      console.error('更新世界观失败:', e)
      throw e
    } finally {
      set({ loading: false })
    }
  },

  deleteWorld: async (projectId, worldId) => {
    set({ loading: true })
    try {
      await worldApi.delete(projectId, worldId)
    } catch (e) {
      console.error('删除世界观失败:', e)
      throw e
    } finally {
      set({ loading: false })
    }
  },

  // ======================================================================
  // 场景资产
  // ======================================================================

  fetchSceneAssets: async (projectId, worldId) => {
    const requestId = get()._fetchSceneAssetsRequestId + 1
    set({ loading: true, _fetchSceneAssetsRequestId: requestId })
    try {
      const res = await sceneAssetApi.list(projectId, worldId)
      if (get()._fetchSceneAssetsRequestId !== requestId) return
      set({ sceneAssets: res.data?.items ?? [] })
    } catch (e) {
      console.error('获取场景资产列表失败:', e)
      if (get()._fetchSceneAssetsRequestId === requestId) {
        set({ sceneAssets: [] })
      }
      throw e
    } finally {
      if (get()._fetchSceneAssetsRequestId === requestId) {
        set({ loading: false })
      }
    }
  },

  createSceneAsset: async (projectId, worldId, data) => {
    set({ loading: true })
    try {
      await sceneAssetApi.create(projectId, worldId, data)
    } catch (e) {
      console.error('创建场景资产失败:', e)
      throw e
    } finally {
      set({ loading: false })
    }
  },

  updateSceneAsset: async (projectId, worldId, assetId, data) => {
    set({ loading: true })
    try {
      await sceneAssetApi.update(projectId, worldId, assetId, data)
    } catch (e) {
      console.error('更新场景资产失败:', e)
      throw e
    } finally {
      set({ loading: false })
    }
  },

  deleteSceneAsset: async (projectId, worldId, assetId) => {
    set({ loading: true })
    try {
      await sceneAssetApi.delete(projectId, worldId, assetId)
    } catch (e) {
      console.error('删除场景资产失败:', e)
      throw e
    } finally {
      set({ loading: false })
    }
  },

  aiExtractScenes: async (projectId, worldId, novelText) => {
    set({ loading: true })
    try {
      const res: any = await sceneAssetApi.aiExtract(projectId, worldId, { novel_text: novelText })
      return res.data?.task_id || ''
    } catch (e: any) {
      console.error('AI提取场景失败:', e)
      message.error(e.response?.data?.detail || '提取失败')
      throw e
    } finally {
      set({ loading: false })
    }
  },

  aiExtractProps: async (projectId, worldId, novelText) => {
    set({ loading: true })
    try {
      const res: any = await sceneAssetApi.aiExtractProps(projectId, worldId, { novel_text: novelText })
      return res.data?.task_id || ''
    } catch (e: any) {
      console.error('AI提取道具失败:', e)
      message.error(e.response?.data?.detail || '提取失败')
      throw e
    } finally {
      set({ loading: false })
    }
  },

  aiExtractBuildings: async (projectId, worldId, novelText) => {
    set({ loading: true })
    try {
      const res: any = await sceneAssetApi.aiExtractBuildings(projectId, worldId, { novel_text: novelText })
      return res.data?.task_id || ''
    } catch (e: any) {
      console.error('AI提取建筑失败:', e)
      message.error(e.response?.data?.detail || '提取失败')
      throw e
    } finally {
      set({ loading: false })
    }
  },

  aiExtractOutfits: async (projectId, worldId, novelText) => {
    set({ loading: true })
    try {
      const res: any = await sceneAssetApi.aiExtractOutfits(projectId, worldId, { novel_text: novelText })
      return res.data?.task_id || ''
    } catch (e: any) {
      console.error('AI提取服装失败:', e)
      message.error(e.response?.data?.detail || '提取失败')
      throw e
    } finally {
      set({ loading: false })
    }
  },

  generateSceneImage: async (projectId, worldId, assetId) => {
    const res: any = await sceneAssetApi.generateSceneImage(projectId, worldId, assetId)
    return res.data?.task_id || ''
  },

  generatePropImage: async (projectId, worldId, propId) => {
    const res: any = await propApi.generateImage(projectId, worldId, propId)
    return res.data?.task_id || ''
  },

  generateBuildingImage: async (projectId, worldId, buildingId) => {
    const res: any = await buildingApi.generateImage(projectId, worldId, buildingId)
    return res.data?.task_id || ''
  },

  generateOutfitImage: async (projectId, worldId, outfitId) => {
    const res: any = await outfitApi.generateImage(projectId, worldId, outfitId)
    return res.data?.task_id || ''
  },

  // ======================================================================
  // 道具
  // ======================================================================

  fetchProps: async (projectId, worldId) => {
    const requestId = get()._fetchPropsRequestId + 1
    set({ loading: true, _fetchPropsRequestId: requestId })
    try {
      const res = await propApi.list(projectId, worldId)
      if (get()._fetchPropsRequestId !== requestId) return
      set({ props: res.data?.items ?? [] })
    } catch (e) {
      console.error('获取道具列表失败:', e)
      if (get()._fetchPropsRequestId === requestId) {
        set({ props: [] })
      }
      throw e
    } finally {
      if (get()._fetchPropsRequestId === requestId) {
        set({ loading: false })
      }
    }
  },

  createProp: async (projectId, worldId, data) => {
    set({ loading: true })
    try {
      await propApi.create(projectId, worldId, data)
    } catch (e) {
      console.error('创建道具失败:', e)
      throw e
    } finally {
      set({ loading: false })
    }
  },

  updateProp: async (projectId, worldId, propId, data) => {
    set({ loading: true })
    try {
      await propApi.update(projectId, worldId, propId, data)
    } catch (e) {
      console.error('更新道具失败:', e)
      throw e
    } finally {
      set({ loading: false })
    }
  },

  deleteProp: async (projectId, worldId, propId) => {
    set({ loading: true })
    try {
      await propApi.delete(projectId, worldId, propId)
    } catch (e) {
      console.error('删除道具失败:', e)
      throw e
    } finally {
      set({ loading: false })
    }
  },

  // ======================================================================
  // 建筑
  // ======================================================================

  fetchBuildings: async (projectId, worldId) => {
    const requestId = get()._fetchBuildingsRequestId + 1
    set({ loading: true, _fetchBuildingsRequestId: requestId })
    try {
      const res = await buildingApi.list(projectId, worldId)
      if (get()._fetchBuildingsRequestId !== requestId) return
      set({ buildings: res.data?.items ?? [] })
    } catch (e) {
      console.error('获取建筑列表失败:', e)
      if (get()._fetchBuildingsRequestId === requestId) {
        set({ buildings: [] })
      }
      throw e
    } finally {
      if (get()._fetchBuildingsRequestId === requestId) {
        set({ loading: false })
      }
    }
  },

  createBuilding: async (projectId, worldId, data) => {
    set({ loading: true })
    try {
      await buildingApi.create(projectId, worldId, data)
    } catch (e) {
      console.error('创建建筑失败:', e)
      throw e
    } finally {
      set({ loading: false })
    }
  },

  updateBuilding: async (projectId, worldId, buildingId, data) => {
    set({ loading: true })
    try {
      await buildingApi.update(projectId, worldId, buildingId, data)
    } catch (e) {
      console.error('更新建筑失败:', e)
      throw e
    } finally {
      set({ loading: false })
    }
  },

  deleteBuilding: async (projectId, worldId, buildingId) => {
    set({ loading: true })
    try {
      await buildingApi.delete(projectId, worldId, buildingId)
    } catch (e) {
      console.error('删除建筑失败:', e)
      throw e
    } finally {
      set({ loading: false })
    }
  },

  // ======================================================================
  // 服装
  // ======================================================================

  fetchOutfits: async (projectId, worldId) => {
    const requestId = get()._fetchOutfitsRequestId + 1
    set({ loading: true, _fetchOutfitsRequestId: requestId })
    try {
      const res = await outfitApi.list(projectId, worldId)
      if (get()._fetchOutfitsRequestId !== requestId) return
      set({ outfits: res.data?.items ?? [] })
    } catch (e) {
      console.error('获取服装列表失败:', e)
      if (get()._fetchOutfitsRequestId === requestId) {
        set({ outfits: [] })
      }
      throw e
    } finally {
      if (get()._fetchOutfitsRequestId === requestId) {
        set({ loading: false })
      }
    }
  },

  createOutfit: async (projectId, worldId, data) => {
    set({ loading: true })
    try {
      await outfitApi.create(projectId, worldId, data)
    } catch (e) {
      console.error('创建服装失败:', e)
      throw e
    } finally {
      set({ loading: false })
    }
  },

  updateOutfit: async (projectId, worldId, outfitId, data) => {
    set({ loading: true })
    try {
      await outfitApi.update(projectId, worldId, outfitId, data)
    } catch (e) {
      console.error('更新服装失败:', e)
      throw e
    } finally {
      set({ loading: false })
    }
  },

  deleteOutfit: async (projectId, worldId, outfitId) => {
    set({ loading: true })
    try {
      await outfitApi.delete(projectId, worldId, outfitId)
    } catch (e) {
      console.error('删除服装失败:', e)
      throw e
    } finally {
      set({ loading: false })
    }
  },

  aiAssistWorld: async (projectId, novelText) => {
    set({ loading: true })
    try {
      const res = await worldApi.aiAssist(projectId, { novel_text: novelText })
      return res.data
    } catch (e) {
      console.error('AI辅助创建失败:', e)
      message.error('AI分析失败')
      throw e
    } finally {
      set({ loading: false })
    }
  },

  aiCreateWorld: async (projectId, novelText) => {
    set({ loading: true })
    try {
      const res: any = await worldApi.aiCreate(projectId, { novel_text: novelText })
      return res.data?.task_id || ''
    } catch (e: any) {
      console.error('AI自动创建世界观失败:', e)
      message.error(e.response?.data?.detail || 'AI创建失败')
      throw e
    } finally {
      set({ loading: false })
    }
  },
}))
