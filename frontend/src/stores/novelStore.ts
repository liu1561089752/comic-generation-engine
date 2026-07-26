import { create } from 'zustand'
import {
  Novel,
  Chapter,
  EditorParagraph,
  VersionHistoryItem,
} from '../types/novel'
import { novelApi } from '../api/novelApi'

interface ChapterDetail {
  id: string
  novel_id: string
  chapter_number: number
  title?: string
  status: string
  content?: string
  paragraphs: EditorParagraph[]
  paragraph_stats: Record<string, number>
  created_at: string
  updated_at: string
}

interface NovelState {
  // 小说列表/详情
  novels: Novel[]
  currentNovel: Novel | null
  chapters: Chapter[]
  loading: boolean
  uploading: boolean
  uploadProgress: number
  preprocessing: boolean
  error: string | null

  // 编辑器状态
  chapterDetail: ChapterDetail | null
  editorLoading: boolean
  saving: boolean
  versionHistory: VersionHistoryItem[]
  historyLoading: boolean
  _chapterDetailRequestId: number

  // 小说操作
  fetchNovels: (projectId: string) => Promise<void>
  fetchNovel: (projectId: string, novelId: string) => Promise<void>
  uploadNovel: (projectId: string, file: File, title?: string) => Promise<void>
  preprocessNovel: (projectId: string, novelId: string) => Promise<void>
  updateNovelText: (projectId: string, novelId: string, raw_text: string) => Promise<any>
  fetchChapters: (projectId: string, novelId: string) => Promise<void>

  // 编辑器操作
  fetchChapterDetail: (projectId: string, novelId: string, chapterId: string) => Promise<void>
  saveEditor: (
    projectId: string,
    novelId: string,
    chapterId: string,
    paragraphs: EditorParagraph[],
    summary?: string
  ) => Promise<any>
  fetchVersionHistory: (projectId: string, novelId: string, chapterId: string) => Promise<void>
  restoreVersion: (
    projectId: string,
    novelId: string,
    versionId: string,
    chapterId: string
  ) => Promise<void>

  // 章节管理操作
  updateChapter: (
    projectId: string,
    novelId: string,
    chapterId: string,
    data: { title?: string; content?: string; status?: string }
  ) => Promise<void>
  mergeChapters: (
    projectId: string,
    novelId: string,
    chapterId: string,
    targetChapterId: string
  ) => Promise<void>
  splitChapter: (
    projectId: string,
    novelId: string,
    chapterId: string,
    splitAtParagraphNumber: string
  ) => Promise<void>
}

export const useNovelStore = create<NovelState>((set, get) => ({
  novels: [],
  currentNovel: null,
  chapters: [],
  loading: false,
  uploading: false,
  uploadProgress: 0,
  preprocessing: false,
  error: null,
  chapterDetail: null,
  editorLoading: false,
  saving: false,
  versionHistory: [],
  historyLoading: false,

  fetchNovels: async (projectId) => {
    set({ loading: true, error: null })
    try {
      const res = await novelApi.list(projectId)
      set({ novels: res.data?.items ?? [] })
    } catch (e) {
      // D77: 设置错误状态供 UI 感知
      set({ error: '获取小说列表失败' })
      console.error('获取小说列表失败:', e)
    } finally {
      set({ loading: false })
    }
  },

  fetchNovel: async (projectId, novelId) => {
    set({ loading: true, error: null })
    try {
      const res = await novelApi.getById(projectId, novelId)
      set({ currentNovel: res.data })
    } catch (e) {
      set({ error: '获取小说详情失败' })
      console.error('获取小说详情失败:', e)
    } finally {
      set({ loading: false })
    }
  },

  uploadNovel: async (projectId, file, title) => {
    set({ uploading: true, uploadProgress: 0 })
    try {
      const res = await novelApi.upload(projectId, file, title, (percent) => {
        set({ uploadProgress: percent })
      })
      return res.data
    } catch (e) {
      console.error('操作失败:', e)
      throw e
    } finally {
      set({ uploading: false, uploadProgress: 0 })
    }
  },

  preprocessNovel: async (projectId, novelId) => {
    set({ preprocessing: true })
    try {
      const res = await novelApi.preprocess(projectId, novelId)
      return res.data
    } catch (e) {
      console.error('操作失败:', e)
      throw e
    } finally {
      set({ preprocessing: false })
    }
  },

  updateNovelText: async (projectId: string, novelId: string, raw_text: string) => {
    set({ preprocessing: true })
    try {
      const res = await novelApi.updateText(projectId, novelId, raw_text)
      return res.data
    } catch (e) {
      console.error('更新文本失败:', e)
      throw e
    } finally {
      set({ preprocessing: false })
    }
  },

  fetchChapters: async (projectId, novelId) => {
    set({ loading: true, error: null })
    try {
      const res = await novelApi.listChapters(projectId, novelId)
      set({ chapters: res.data ?? [] })
    } catch (e) {
      set({ error: '获取章节列表失败' })
      console.error('获取章节列表失败:', e)
    } finally {
      set({ loading: false })
    }
  },

  // 编辑器操作
  // D55/D63: 用请求 ID 追踪防止竞态——快速切换章节时旧请求返回被丢弃
  _chapterDetailRequestId: 0 as number,
  fetchChapterDetail: async (projectId, novelId, chapterId) => {
    const requestId = get()._chapterDetailRequestId + 1
    set({ editorLoading: true, error: null, _chapterDetailRequestId: requestId })
    try {
      const res = await novelApi.getChapterDetail(projectId, novelId, chapterId)
      // D63: 过期请求丢弃，不覆写新数据
      if (get()._chapterDetailRequestId !== requestId) return
      set({ chapterDetail: res.data })
    } catch (e) {
      if (get()._chapterDetailRequestId !== requestId) return
      set({ error: '获取章节详情失败' })
      console.error('获取章节详情失败:', e)
    } finally {
      if (get()._chapterDetailRequestId === requestId) {
        set({ editorLoading: false })
      }
    }
  },

  saveEditor: async (projectId, novelId, chapterId, paragraphs, summary) => {
    set({ saving: true })
    try {
      const res = await novelApi.saveEditor(projectId, novelId, chapterId, paragraphs, summary)
      return res.data
    } catch (e) {
      console.error('保存失败:', e)
      throw e
    } finally {
      set({ saving: false })
    }
  },

  fetchVersionHistory: async (projectId, novelId, chapterId) => {
    set({ historyLoading: true, error: null })
    try {
      const res = await novelApi.getVersionHistory(projectId, novelId, chapterId)
      set({ versionHistory: res.data ?? [] })
    } catch (e) {
      set({ error: '获取版本历史失败' })
      console.error('获取版本历史失败:', e)
    } finally {
      set({ historyLoading: false })
    }
  },

  restoreVersion: async (projectId, novelId, versionId, chapterId) => {
    try {
      await novelApi.restoreVersion(projectId, novelId, versionId, chapterId)
    } catch (e) {
      console.error('恢复版本失败:', e)
      throw e
    }
  },

  // 章节管理操作
  updateChapter: async (projectId, novelId, chapterId, data) => {
    try {
      await novelApi.updateChapter(projectId, novelId, chapterId, data)
      const res = await novelApi.listChapters(projectId, novelId)
      set({ chapters: res.data ?? [] })
    } catch (e) {
      console.error('更新章节失败:', e)
      throw e
    }
  },

  mergeChapters: async (projectId, novelId, chapterId, targetChapterId) => {
    try {
      await novelApi.mergeChapters(projectId, novelId, chapterId, targetChapterId)
      const res = await novelApi.listChapters(projectId, novelId)
      set({ chapters: res.data ?? [] })
    } catch (e) {
      console.error('合并章节失败:', e)
      throw e
    }
  },

  splitChapter: async (projectId, novelId, chapterId, splitAtParagraphNumber) => {
    try {
      await novelApi.splitChapter(projectId, novelId, chapterId, splitAtParagraphNumber)
      const res = await novelApi.listChapters(projectId, novelId)
      set({ chapters: res.data ?? [] })
    } catch (e) {
      console.error('分割章节失败:', e)
      throw e
    }
  },
}))
