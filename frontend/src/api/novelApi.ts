import apiClient from './client'
import type { AxiosProgressEvent } from 'axios'
import type { ApiResponse } from '../types'
import type {
  Novel,
  Chapter,
  EditorParagraph,
  EditorVersionDetail,
  VersionHistoryItem,
  ScriptResponse,
  ScriptChapterData,
  StoryboardResponse,
  StoryboardChapterData,
  LayoutResponse,
  LayoutChapterData,
} from '../types/novel'

// Helper type for paginated list responses
type ListResponse<T> = { items: T[]; total: number; skip?: number; limit?: number }

export const novelApi = {
  // 上传小说（T8 D62: 支持 onUploadProgress 上传进度回调）
  upload: (
    projectId: string,
    file: File,
    title?: string,
    onUploadProgress?: (percent: number) => void
  ) => {
    const formData = new FormData()
    formData.append('file', file)
    if (title) formData.append('title', title)
    return apiClient.post<ApiResponse<Novel>>(`/projects/${projectId}/novels/upload`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: onUploadProgress
        ? (e: AxiosProgressEvent) => {
            if (e.total) {
              onUploadProgress(Math.round((e.loaded / e.total) * 100))
            }
          }
        : undefined,
    })
  },

  // 小说列表
  list: (projectId: string) =>
    apiClient.get<ApiResponse<ListResponse<Novel>>>(`/projects/${projectId}/novels`),

  // 小说详情
  getById: (projectId: string, novelId: string) =>
    apiClient.get<ApiResponse<Novel>>(`/projects/${projectId}/novels/${novelId}`),

  // 预处理
  preprocess: (projectId: string, novelId: string) =>
    apiClient.post<ApiResponse<any>>(`/projects/${projectId}/novels/${novelId}/preprocess`),

  // 更新小说文本
  updateText: (projectId: string, novelId: string, raw_text: string) =>
    apiClient.put<ApiResponse<any>>(`/projects/${projectId}/novels/${novelId}/text`, { raw_text }),

  // 章节列表
  listChapters: (projectId: string, novelId: string) =>
    apiClient.get<ApiResponse<Chapter[]>>(`/projects/${projectId}/novels/${novelId}/chapters`),

  // ===== 编辑器 API =====

  // 获取章节详情（含段落）
  getChapterDetail: (projectId: string, novelId: string, chapterId: string) =>
    apiClient.get<ApiResponse<any>>(
      `/projects/${projectId}/novels/${novelId}/editor/chapters/${chapterId}`
    ),

  // 保存编辑器内容
  saveEditor: (
    projectId: string,
    novelId: string,
    chapterId: string,
    paragraphs: EditorParagraph[],
    summary?: string
  ) =>
    apiClient.post<ApiResponse<any>>(
      `/projects/${projectId}/novels/${novelId}/editor/save`,
      { chapter_id: chapterId, paragraphs, summary }
    ),

  // 获取版本历史
  getVersionHistory: (projectId: string, novelId: string, chapterId: string) =>
    apiClient.get<ApiResponse<VersionHistoryItem[]>>(
      `/projects/${projectId}/novels/${novelId}/editor/history`,
      { params: { chapter_id: chapterId } }
    ),

  // 获取版本详情
  getVersionDetail: (projectId: string, novelId: string, versionId: string) =>
    apiClient.get<ApiResponse<EditorVersionDetail>>(
      `/projects/${projectId}/novels/${novelId}/editor/versions/${versionId}`
    ),

  // 恢复版本
  restoreVersion: (projectId: string, novelId: string, versionId: string, chapterId: string) =>
    apiClient.post<ApiResponse<any>>(
      `/projects/${projectId}/novels/${novelId}/editor/restore/${versionId}`,
      null,
      { params: { chapter_id: chapterId } }
    ),

  // ===== 章节管理 API =====

  // 更新章节
  updateChapter: (
    projectId: string,
    novelId: string,
    chapterId: string,
    data: { title?: string; content?: string; status?: string }
  ) =>
    apiClient.put<ApiResponse<Chapter>>(
      `/projects/${projectId}/novels/${novelId}/chapters/${chapterId}`,
      data
    ),

  // 合并章节
  mergeChapters: (
    projectId: string,
    novelId: string,
    chapterId: string,
    targetChapterId: string
  ) =>
    apiClient.post<ApiResponse<any>>(
      `/projects/${projectId}/novels/${novelId}/chapters/${chapterId}/merge`,
      { target_chapter_id: targetChapterId }
    ),

  // 分割章节
  splitChapter: (
    projectId: string,
    novelId: string,
    chapterId: string,
    splitAtParagraphNumber: string
  ) =>
    apiClient.post<ApiResponse<any>>(
      `/projects/${projectId}/novels/${novelId}/chapters/${chapterId}/split`,
      { split_at_paragraph_number: splitAtParagraphNumber }
    ),

  // ===== 剧情拆解（Script）API =====

  // 生成脚本
  generateScript: (projectId: string, novelId: string) =>
    apiClient.post<ApiResponse<{ task_id: string }>>(
      `/projects/${projectId}/novels/${novelId}/generate-script`
    ),

  // 获取脚本
  getScript: (projectId: string, novelId: string) =>
    apiClient.get<ApiResponse<ScriptResponse>>(
      `/projects/${projectId}/novels/${novelId}/script`
    ),

  // 保存脚本
  saveScript: (projectId: string, novelId: string, chapters: ScriptChapterData[]) =>
    apiClient.put<ApiResponse<ScriptResponse>>(
      `/projects/${projectId}/novels/${novelId}/script`,
      { chapters }
    ),

  // 拆分镜头
  splitShot: (
    projectId: string,
    novelId: string,
    chapterId: string,
    shotId: string,
    contentBefore: string,
    contentAfter: string
  ) =>
    apiClient.post<ApiResponse<ScriptResponse>>(
      `/projects/${projectId}/novels/${novelId}/script/split-shot`,
      {
        chapter_id: chapterId,
        shot_id: shotId,
        content_before: contentBefore,
        content_after: contentAfter,
      }
    ),

  /** 删除脚本及下游数据（分镜、排版、生图提示词、参考图、漫画页图片） */
  deleteScript: (projectId: string, novelId: string) =>
    apiClient.delete<ApiResponse<any>>(
      `/projects/${projectId}/novels/${novelId}/script`
    ),

  // ===== 分镜（Storyboard）API =====

  // 生成分镜
  generateStoryboard: (projectId: string, novelId: string) =>
    apiClient.post<ApiResponse<{ task_id: string }>>(
      `/projects/${projectId}/novels/${novelId}/generate-storyboard`
    ),

  // 获取分镜
  getStoryboard: (projectId: string, novelId: string) =>
    apiClient.get<ApiResponse<StoryboardResponse>>(
      `/projects/${projectId}/novels/${novelId}/storyboard`
    ),

  // 保存分镜
  saveStoryboard: (projectId: string, novelId: string, chapters: StoryboardChapterData[]) =>
    apiClient.put<ApiResponse<StoryboardResponse>>(
      `/projects/${projectId}/novels/${novelId}/storyboard`,
      { chapters }
    ),

  // ===== AI排版（Layout）API =====

  generateLayout: (projectId: string, novelId: string) =>
    apiClient.post<ApiResponse<{ task_id: string }>>(
      `/projects/${projectId}/novels/${novelId}/generate-layout`
    ),

  getLayout: (projectId: string, novelId: string) =>
    apiClient.get<ApiResponse<LayoutResponse>>(
      `/projects/${projectId}/novels/${novelId}/layout`
    ),

  saveLayout: (projectId: string, novelId: string, chapters: LayoutChapterData[]) =>
    apiClient.put<ApiResponse<LayoutResponse>>(
      `/projects/${projectId}/novels/${novelId}/layout`,
      { chapters }
    ),

  /** 删除小说所有漫画页图片 */
  deleteAllLayoutPages: (projectId: string, novelId: string) =>
    apiClient.delete<ApiResponse<any>>(
      `/projects/${projectId}/novels/${novelId}/layout-pages`
    ),

  /** 删除小说所有分镜及下游数据（排版、生图提示词、参考图、漫画页） */
  deleteAllStoryboard: (projectId: string, novelId: string) =>
    apiClient.delete<ApiResponse<any>>(
      `/projects/${projectId}/novels/${novelId}/storyboard`
    ),

  /** 删除小说所有排版及下游数据（生图提示词、参考图、漫画页），保留分镜 */
  deleteAllLayout: (projectId: string, novelId: string) =>
    apiClient.delete<ApiResponse<any>>(
      `/projects/${projectId}/novels/${novelId}/layout`
    ),

  /** 删除指定章节的排版及下游数据，保留分镜 */
  deleteLayoutChapter: (projectId: string, novelId: string, chapterId: string) =>
    apiClient.delete<ApiResponse<any>>(
      `/projects/${projectId}/novels/${novelId}/layout/${chapterId}`
    ),

  /** 批量删除指定页面的内容（按范围 + 类型） */
  batchDeletePages: (
    projectId: string,
    novelId: string,
    startPage: number,
    endPage: number,
    deleteType: 'prompt' | 'reference' | 'page',
  ) =>
    apiClient.post<ApiResponse<any>>(
      `/projects/${projectId}/novels/${novelId}/batch-delete-pages`,
      { start_page: startPage, end_page: endPage, delete_type: deleteType }
    ),

  // ===== 生图中心 API =====

  /** 一键生成生图提示词（调用LLM） */
  generateImagePrompts: (projectId: string, novelId: string) =>
    apiClient.post<ApiResponse<{ task_id: string }>>(
      `/projects/${projectId}/novels/${novelId}/generate-image-prompts`
    ),

  /** 重新生成单页提示词 */
  regeneratePagePrompt: (projectId: string, novelId: string, pageId: string) =>
    apiClient.post<ApiResponse<LayoutResponse>>(
      `/projects/${projectId}/novels/${novelId}/regenerate-page-prompt`,
      { page_id: pageId }
    ),

  /** AI 匹配参考图 */
  matchReferences: (projectId: string, novelId: string) =>
    apiClient.post<ApiResponse<Record<string, string[]>>>(
      `/projects/${projectId}/novels/${novelId}/match-references`
    ),

  /** 生成单页图片（支持携带参考图 ID） */
  generateSingleImage: (projectId: string, novelId: string, pageId: string, referenceIds?: string[]) =>
    apiClient.post<ApiResponse<LayoutResponse>>(
      `/projects/${projectId}/novels/${novelId}/generate-single-image`,
      { page_id: pageId, reference_ids: referenceIds || [] }
    ),

  /** 一键生成图片（调用GRS AI） */
  generatePageImages: (projectId: string, novelId: string) =>
    apiClient.post<ApiResponse<{ task_id: string }>>(
      `/projects/${projectId}/novels/${novelId}/generate-page-images`
    ),

  /** 一键生成图片（携带各页参考图 ID） */
  generatePageImagesWithRefs: (projectId: string, novelId: string, referenceIds: Record<string, string[]>) =>
    apiClient.post<ApiResponse<LayoutResponse>>(
      `/projects/${projectId}/novels/${novelId}/generate-page-images`,
      { reference_ids: referenceIds }
    ),

  /** 一键补图：从 GRS AI 积分记录中恢复未生成的图片 */
  recoverImages: (projectId: string, novelId: string, authorization: string, xtx: string, limit: number) =>
    apiClient.post<ApiResponse<{ task_id: string }>>(
      `/projects/${projectId}/novels/${novelId}/recover-images`,
      { authorization, xtx, limit }
    ),

  /** 获取小说的所有小说列表（用于切换小说） */
  listByProject: (projectId: string) =>
    apiClient.get<ApiResponse<ListResponse<Novel>>>(`/projects/${projectId}/novels`),
}
