/**
 * Shared helper: extract the first novel's text from a project.
 *
 * Used by SceneAssetTab / PropTab / BuildingTab / OutfitTab to fetch novel
 * text before invoking AI extraction. Returns null if no novel or empty text,
 * in which case the caller should warn the user.
 */
import { novelApi } from '../../../api/novelApi'
import { message } from 'antd'

export async function extractNovelText(projectId: string): Promise<string | null> {
  const novelRes: any = await novelApi.list(projectId)
  const novels = novelRes.data?.items || novelRes.data || []
  if (novels.length === 0) {
    message.warning('当前项目没有小说，请先上传小说')
    return null
  }

  const firstNovel = novels[0]
  let novelText: string = firstNovel.cleaned_text || firstNovel.raw_text || ''

  if (!novelText.trim()) {
    const novelDetailRes: any = await novelApi.getById(projectId, firstNovel.id)
    const novel = novelDetailRes.data
    novelText = novel.cleaned_text || novel.raw_text || ''
  }

  if (!novelText.trim()) {
    message.warning('小说内容为空')
    return null
  }

  return novelText
}
