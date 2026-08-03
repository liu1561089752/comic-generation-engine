import { create } from 'zustand'
import apiClient from '../api/client'

export interface PageInfo {
  id: string
  page_number: number
  thumbnail_url?: string
  panel_count: number
  status: string
}

export interface PanelInfo {
  id: string
  panel_number: number
  image_url: string
  x: number
  y: number
  width: number
  height: number
  rotation: number
}

export interface BubbleData {
  id: string
  type: 'narration' | 'dialogue' | 'thinking'
  text: string
  x: number
  y: number
  width: number
  height: number
  fontSize?: number
  fontFamily?: string
  color?: string
}

export interface ExportHistoryItem {
  id: string
  project_id: string
  format: string
  status: string
  progress: number
  file_url?: string
  created_at: string
}

export interface CandidateImage {
  id: string
  url: string
  thumbnail_url: string
}

export interface EditorSnapshot {
  panels: PanelInfo[]
  bubbles: BubbleData[]
}

interface EditorState {
  pages: PageInfo[]
  currentPage: PageInfo | null
  panels: PanelInfo[]
  bubbles: BubbleData[]
  candidateImages: Record<string, CandidateImage[]>
  selectedPanelId: string | null
  selectedBubbleId: string | null
  stageScale: number
  tool: 'select' | 'drag'
  loading: boolean
  error: string | null
  exportHistory: ExportHistoryItem[]
  isDirty: boolean
  history: EditorSnapshot[]
  historyIndex: number
  lockedLayerIds: string[]
  hiddenLayerIds: string[]

  setPages: (pages: PageInfo[]) => void
  setCurrentPage: (page: PageInfo | null) => void
  setPanels: (panels: PanelInfo[]) => void
  setSelectedPanelId: (id: string | null) => void
  setSelectedBubbleId: (id: string | null) => void
  setStageScale: (scale: number | ((prev: number) => number)) => void
  setTool: (tool: 'select' | 'drag') => void
  setLoading: (loading: boolean) => void
  setExportHistory: (history: ExportHistoryItem[]) => void
  addExportHistory: (item: ExportHistoryItem) => void
  updatePanelPosition: (id: string, x: number, y: number) => void
  updatePanelSize: (id: string, width: number, height: number) => void

  // Bubble operations
  addBubble: (panelId: string, type: BubbleData['type']) => void
  updateBubble: (id: string, data: Partial<BubbleData>) => void
  removeBubble: (id: string) => void

  // Image replacement
  setCandidateImages: (panelId: string, images: CandidateImage[]) => void
  replacePanelImage: (panelId: string, imageUrl: string) => void

  // Layer management
  toggleLayerVisibility: (id: string) => void
  toggleLayerLock: (id: string) => void
  reorderLayer: (fromIndex: number, toIndex: number) => void

  // History
  saveSnapshot: () => void
  undo: () => void
  redo: () => void

  // Persistence
  save: (projectId: string) => Promise<void>
  loadPageData: (projectId: string, pageId: string) => Promise<void>

  // D58: 请求 ID 追踪，防止快速切换页面时旧请求覆写新数据
  _loadPageRequestId: number
  // 标记 history[historyIndex] 是否就是当前画布状态。
  // saveSnapshot 存的是"修改前"的状态，所以修改完成后当前状态并不在栈内；
  // 只有 undo/redo 之后二者才一致。undo 依赖它决定是否要先把当前状态补入栈。
  _currentInHistory: boolean
}

const cloneSnapshot = (panels: PanelInfo[], bubbles: BubbleData[]): EditorSnapshot => ({
  panels: JSON.parse(JSON.stringify(panels)),
  bubbles: JSON.parse(JSON.stringify(bubbles)),
})

// 快照栈最多保留的步数
const MAX_HISTORY = 50

export const useEditorStore = create<EditorState>((set, get) => ({
  pages: [],
  currentPage: null,
  panels: [],
  bubbles: [],
  candidateImages: {},
  selectedPanelId: null,
  selectedBubbleId: null,
  stageScale: 0.5,
  tool: 'select',
  loading: false,
  error: null,
  exportHistory: [],
  isDirty: false,
  history: [],
  historyIndex: -1,
  lockedLayerIds: [],
  hiddenLayerIds: [],
  _loadPageRequestId: 0,
  _currentInHistory: false,

  setPages: (pages) => set({ pages }),
  setCurrentPage: (page) => set({ currentPage: page }),
  setPanels: (panels) => {
    set({ panels })
  },
  setSelectedPanelId: (id) => set((state) => ({
    selectedPanelId: id,
    selectedBubbleId: id !== state.selectedPanelId ? null : state.selectedBubbleId,
  })),
  setSelectedBubbleId: (id) => set({ selectedBubbleId: id, selectedPanelId: id ? null : null }),
  setStageScale: (scale) => set((state) => ({
    stageScale: typeof scale === 'function' ? scale(state.stageScale) : scale,
  })),
  setTool: (tool) => set({ tool }),
  setLoading: (loading) => set({ loading }),
  setExportHistory: (history) => set({ exportHistory: history }),
  addExportHistory: (item) =>
    set((state) => ({ exportHistory: [item, ...state.exportHistory] })),

  updatePanelPosition: (id, x, y) =>
    set((state) => ({
      panels: state.panels.map((p) => (p.id === id ? { ...p, x, y } : p)),
      isDirty: true,
    })),

  updatePanelSize: (id, width, height) =>
    set((state) => ({
      panels: state.panels.map((p) => (p.id === id ? { ...p, width, height } : p)),
      isDirty: true,
    })),

  // Bubble operations
  addBubble: (panelId, type) => {
    const state = get()
    const panel = state.panels.find((p) => p.id === panelId)
    if (!panel) return

    const bubbleId = `bubble-${Date.now()}`
    const bubbleTextMap: Record<BubbleData['type'], string> = {
      narration: '旁白文字',
      dialogue: '对话文字',
      thinking: '内心独白',
    }

    const newBubble: BubbleData = {
      id: bubbleId,
      type,
      text: bubbleTextMap[type],
      x: panel.x + 40,
      y: panel.y + 40,
      width: 200,
      height: type === 'narration' ? 80 : 100,
    }

    state.saveSnapshot()
    set((s) => ({
      bubbles: [...s.bubbles, newBubble],
      selectedBubbleId: bubbleId,
      selectedPanelId: null,
      isDirty: true,
    }))
  },

  updateBubble: (id, data) => {
    const state = get()
    // 只对非撤销/重做操作保存快照
    const currentBubble = state.bubbles.find((b) => b.id === id)
    if (currentBubble && data.text && currentBubble.text !== data.text) {
      state.saveSnapshot()
    }
    set((s) => ({
      bubbles: s.bubbles.map((b) => (b.id === id ? { ...b, ...data } : b)),
      isDirty: true,
    }))
  },

  removeBubble: (id) => {
    const state = get()
    state.saveSnapshot()
    set((s) => ({
      bubbles: s.bubbles.filter((b) => b.id !== id),
      selectedBubbleId: s.selectedBubbleId === id ? null : s.selectedBubbleId,
      isDirty: true,
    }))
  },

  // Image replacement
  setCandidateImages: (panelId, images) =>
    set((state) => ({
      candidateImages: { ...state.candidateImages, [panelId]: images },
    })),

  replacePanelImage: (panelId, imageUrl) =>
    set((state) => ({
      panels: state.panels.map((p) =>
        p.id === panelId ? { ...p, image_url: imageUrl } : p
      ),
      isDirty: true,
    })),

  // Layer management
  toggleLayerVisibility: (id) =>
    set((state) => {
      const hidden = state.hiddenLayerIds.includes(id)
        ? state.hiddenLayerIds.filter((lid) => lid !== id)
        : [...state.hiddenLayerIds, id]
      return { hiddenLayerIds: hidden }
    }),

  toggleLayerLock: (id) =>
    set((state) => {
      const locked = state.lockedLayerIds.includes(id)
        ? state.lockedLayerIds.filter((lid) => lid !== id)
        : [...state.lockedLayerIds, id]
      return { lockedLayerIds: locked }
    }),

  reorderLayer: (fromIndex, toIndex) =>
    set((state) => {
      // 层顺序：先 panels 再 bubbles
      const allLayers = [
        ...state.panels.map((p) => ({ type: 'panel' as const, id: p.id })),
        ...state.bubbles.map((b) => ({ type: 'bubble' as const, id: b.id })),
      ]
      const [moved] = allLayers.splice(fromIndex, 1)
      allLayers.splice(toIndex, 0, moved)

      // 重新排序 panels 和 bubbles
      const panelIds = allLayers
        .filter((l) => l.type === 'panel')
        .map((l) => l.id)
      const bubbleIds = allLayers
        .filter((l) => l.type === 'bubble')
        .map((l) => l.id)

      const reorderedPanels = panelIds
        .map((id) => state.panels.find((p) => p.id === id))
        .filter(Boolean) as PanelInfo[]
      const reorderedBubbles = bubbleIds
        .map((id) => state.bubbles.find((b) => b.id === id))
        .filter(Boolean) as BubbleData[]

      return { panels: reorderedPanels, bubbles: reorderedBubbles, isDirty: true }
    }),

  // History
  // 调用约定：所有修改型 action 在改动之前调用 saveSnapshot()
  saveSnapshot: () =>
    set((state) => {
      // 产生新分支，丢弃当前位置之后的重做记录
      const newHistory = state.history.slice(0, state.historyIndex + 1)
      let newIndex = state.historyIndex
      if (!state._currentInHistory) {
        // 当前状态还没进过栈，压入它作为"这次修改之前"的状态
        newHistory.push(cloneSnapshot(state.panels, state.bubbles))
        if (newHistory.length > MAX_HISTORY) newHistory.shift()
        newIndex = newHistory.length - 1
      }
      return {
        history: newHistory,
        historyIndex: newIndex,
        _currentInHistory: false,
      }
    }),

  undo: () =>
    set((state) => {
      if (state._currentInHistory) {
        // 当前状态就是 history[historyIndex]，直接往前一格
        const newIndex = state.historyIndex - 1
        if (newIndex < 0) return state
        const restored = cloneSnapshot(
          state.history[newIndex].panels,
          state.history[newIndex].bubbles
        )
        return {
          panels: restored.panels,
          bubbles: restored.bubbles,
          historyIndex: newIndex,
          _currentInHistory: true,
          isDirty: true,
        }
      }
      // 当前状态尚未入栈，先补进去，redo 才能回到这里
      if (state.historyIndex < 0) return state
      const newHistory = state.history.slice(0, state.historyIndex + 1)
      newHistory.push(cloneSnapshot(state.panels, state.bubbles))
      let targetIndex = state.historyIndex
      if (newHistory.length > MAX_HISTORY) {
        newHistory.shift()
        targetIndex -= 1
      }
      if (targetIndex < 0) return state
      const restored = cloneSnapshot(
        newHistory[targetIndex].panels,
        newHistory[targetIndex].bubbles
      )
      return {
        panels: restored.panels,
        bubbles: restored.bubbles,
        history: newHistory,
        historyIndex: targetIndex,
        _currentInHistory: true,
        isDirty: true,
      }
    }),

  redo: () =>
    set((state) => {
      // 当前状态不在栈内说明已经是最新状态，没有可重做的记录
      if (!state._currentInHistory) return state
      const newIndex = state.historyIndex + 1
      if (newIndex > state.history.length - 1) return state
      const restored = cloneSnapshot(
        state.history[newIndex].panels,
        state.history[newIndex].bubbles
      )
      return {
        panels: restored.panels,
        bubbles: restored.bubbles,
        historyIndex: newIndex,
        _currentInHistory: true,
        isDirty: true,
      }
    }),

  // Persistence
  save: async (projectId: string) => {
    const state = get()
    if (!state.currentPage?.id) return
    try {
      await apiClient.put(`/projects/${projectId}/editor/pages/${state.currentPage.id}/layers`, {
        panels: state.panels,
        bubbles: state.bubbles,
        layers: { hidden: state.hiddenLayerIds, locked: state.lockedLayerIds },
      })
      // 保存成功，清除脏标记
      set({ isDirty: false })
    } catch (e) {
      // D61: 不吞错误，让调用方感知失败
      console.error('保存失败:', e)
      throw e
    }
  },

  loadPageData: async (projectId, pageId) => {
    // D58: 请求 ID 追踪——快速切换页面时丢弃旧请求的响应
    const requestId = get()._loadPageRequestId + 1
    set({ loading: true, error: null as string | null, _loadPageRequestId: requestId })
    try {
      const res = await apiClient.get(`/projects/${projectId}/pages/${pageId}`)
      if (get()._loadPageRequestId !== requestId) return
      const data = (res as { data?: { panels?: PanelInfo[]; bubbles?: BubbleData[] } }).data
      set({
        panels: data?.panels || [],
        bubbles: data?.bubbles || [],
        history: [],
        historyIndex: -1,
        _currentInHistory: false,
        isDirty: false,
        loading: false,
        error: null,
      })
    } catch (e) {
      if (get()._loadPageRequestId !== requestId) return
      // D76: 不静默回退 mock 数据，设置错误状态
      console.error('加载页面数据失败:', e)
      set({
        panels: [],
        bubbles: [],
        loading: false,
        history: [],
        historyIndex: -1,
        _currentInHistory: false,
        isDirty: false,
        error: '加载页面数据失败，请检查网络后重试',
      })
    }
  },
}))


