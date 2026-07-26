import { create } from 'zustand'
import type { Character, CharacterRelation, CharacterOutfit, CharacterExpression } from '../types/character'
import { characterApi } from '../api/characterApi'
import type { CreateCharacterParams, UpdateCharacterParams, CreateRelationParams, CreateOutfitParams, CreateExpressionParams, UpdateExpressionParams } from '../api/characterApi'

interface CharacterState {
  characters: Character[]
  currentCharacter: Character | null
  relations: CharacterRelation[]
  outfits: CharacterOutfit[]
  expressions: CharacterExpression[]
  total: number
  loading: boolean
  fetchCharacters: (projectId: string, params?: { search?: string; role_type?: string }) => Promise<void>
  fetchCharacter: (projectId: string, characterId: string) => Promise<void>
  createCharacter: (projectId: string, data: CreateCharacterParams) => Promise<void>
  updateCharacter: (projectId: string, characterId: string, data: UpdateCharacterParams) => Promise<void>
  deleteCharacter: (projectId: string, characterId: string) => Promise<void>
  fetchRelations: (projectId: string, characterId: string) => Promise<void>
  createRelation: (projectId: string, characterId: string, data: CreateRelationParams) => Promise<void>
  fetchOutfits: (projectId: string, characterId: string) => Promise<void>
  createOutfit: (projectId: string, characterId: string, data: CreateOutfitParams) => Promise<void>
  fetchExpressions: (projectId: string, characterId: string) => Promise<void>
  createExpression: (projectId: string, characterId: string, data: CreateExpressionParams) => Promise<void>
  updateExpression: (projectId: string, characterId: string, expressionId: string, data: UpdateExpressionParams) => Promise<void>
  deleteExpression: (projectId: string, characterId: string, expressionId: string) => Promise<void>
  // D58: 请求 ID 追踪，防止快速搜索/切换角色时旧请求覆写新数据
  _fetchCharactersRequestId: number
  _fetchCharacterRequestId: number
  _fetchRelationsRequestId: number
  _fetchOutfitsRequestId: number
  _fetchExpressionsRequestId: number
}

export const useCharacterStore = create<CharacterState>((set, get) => ({
  characters: [],
  currentCharacter: null,
  relations: [],
  outfits: [],
  expressions: [],
  total: 0,
  loading: false,
  _fetchCharactersRequestId: 0,
  _fetchCharacterRequestId: 0,
  _fetchRelationsRequestId: 0,
  _fetchOutfitsRequestId: 0,
  _fetchExpressionsRequestId: 0,

  fetchCharacters: async (projectId, params) => {
    const requestId = get()._fetchCharactersRequestId + 1
    set({ loading: true, _fetchCharactersRequestId: requestId })
    try {
      const res = await characterApi.list(projectId, params)
      if (get()._fetchCharactersRequestId !== requestId) return
      set({ characters: res.data?.items ?? [], total: res.data?.total ?? 0 })
    } catch (e) {
      console.error('获取角色列表失败:', e)
      if (get()._fetchCharactersRequestId === requestId) {
        set({ characters: [], total: 0 })
      }
      throw e
    } finally {
      if (get()._fetchCharactersRequestId === requestId) {
        set({ loading: false })
      }
    }
  },

  fetchCharacter: async (projectId, characterId) => {
    const requestId = get()._fetchCharacterRequestId + 1
    set({ loading: true, _fetchCharacterRequestId: requestId })
    try {
      const res = await characterApi.getById(projectId, characterId)
      if (get()._fetchCharacterRequestId !== requestId) return
      set({ currentCharacter: res.data ?? null })
    } catch (e) {
      console.error('获取角色详情失败:', e)
      if (get()._fetchCharacterRequestId === requestId) {
        set({ currentCharacter: null })
      }
      throw e
    } finally {
      if (get()._fetchCharacterRequestId === requestId) {
        set({ loading: false })
      }
    }
  },

  createCharacter: async (projectId, data) => {
    set({ loading: true })
    try {
      await characterApi.create(projectId, data)
    } catch (e) {
      console.error('创建角色失败:', e)
      throw e
    } finally {
      set({ loading: false })
    }
  },

  updateCharacter: async (projectId, characterId, data) => {
    set({ loading: true })
    try {
      const res = await characterApi.update(projectId, characterId, data)
      set({ currentCharacter: res.data ?? null })
    } catch (e) {
      console.error('更新角色失败:', e)
      throw e
    } finally {
      set({ loading: false })
    }
  },

  deleteCharacter: async (projectId, characterId) => {
    set({ loading: true })
    try {
      await characterApi.delete(projectId, characterId)
    } catch (e) {
      console.error('删除角色失败:', e)
      throw e
    } finally {
      set({ loading: false })
    }
  },

  fetchRelations: async (projectId, characterId) => {
    const requestId = get()._fetchRelationsRequestId + 1
    set({ loading: true, _fetchRelationsRequestId: requestId })
    try {
      const res = await characterApi.listRelations(projectId, characterId)
      if (get()._fetchRelationsRequestId !== requestId) return
      set({ relations: res.data ?? [] })
    } catch (e) {
      console.error('获取角色关系失败:', e)
      if (get()._fetchRelationsRequestId === requestId) {
        set({ relations: [] })
      }
      throw e
    } finally {
      if (get()._fetchRelationsRequestId === requestId) {
        set({ loading: false })
      }
    }
  },

  createRelation: async (projectId, characterId, data) => {
    set({ loading: true })
    try {
      await characterApi.createRelation(projectId, characterId, data)
    } catch (e) {
      console.error('创建角色关系失败:', e)
      throw e
    } finally {
      set({ loading: false })
    }
  },

  fetchOutfits: async (projectId, characterId) => {
    const requestId = get()._fetchOutfitsRequestId + 1
    set({ loading: true, _fetchOutfitsRequestId: requestId })
    try {
      const res = await characterApi.listOutfits(projectId, characterId)
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

  createOutfit: async (projectId, characterId, data) => {
    set({ loading: true })
    try {
      await characterApi.createOutfit(projectId, characterId, data)
    } catch (e) {
      console.error('创建服装失败:', e)
      throw e
    } finally {
      set({ loading: false })
    }
  },

  fetchExpressions: async (projectId, characterId) => {
    const requestId = get()._fetchExpressionsRequestId + 1
    set({ loading: true, _fetchExpressionsRequestId: requestId })
    try {
      const res = await characterApi.listExpressions(projectId, characterId)
      if (get()._fetchExpressionsRequestId !== requestId) return
      set({ expressions: res.data?.items ?? [] })
    } catch (e) {
      console.error('获取表情列表失败:', e)
      if (get()._fetchExpressionsRequestId === requestId) {
        set({ expressions: [] })
      }
      throw e
    } finally {
      if (get()._fetchExpressionsRequestId === requestId) {
        set({ loading: false })
      }
    }
  },

  createExpression: async (projectId, characterId, data) => {
    set({ loading: true })
    try {
      await characterApi.createExpression(projectId, characterId, data)
    } catch (e) {
      console.error('创建表情失败:', e)
      throw e
    } finally {
      set({ loading: false })
    }
  },

  updateExpression: async (projectId, characterId, expressionId, data) => {
    set({ loading: true })
    try {
      await characterApi.updateExpression(projectId, characterId, expressionId, data)
    } catch (e) {
      console.error('更新表情失败:', e)
      throw e
    } finally {
      set({ loading: false })
    }
  },

  deleteExpression: async (projectId, characterId, expressionId) => {
    set({ loading: true })
    try {
      await characterApi.deleteExpression(projectId, characterId, expressionId)
    } catch (e) {
      console.error('删除表情失败:', e)
      throw e
    } finally {
      set({ loading: false })
    }
  },
}))
