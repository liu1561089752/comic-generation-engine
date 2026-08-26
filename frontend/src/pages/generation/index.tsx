import { useEffect, useState, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Button,
  Space,
  Typography,
  Spin,
  message,
  Image,
  Checkbox,
  Empty,
  Input,
  InputNumber,
  Select,
  Modal,
  Alert,
  Card,
} from 'antd'
import {
  SaveOutlined,
  PictureOutlined,
  FileTextOutlined,
  LeftOutlined,
  RightOutlined,
  ReloadOutlined,
  ThunderboltOutlined,
  ExperimentOutlined,
  DeleteOutlined,
} from '@ant-design/icons'
import { usePipelineStore } from '../../stores/pipelineStore'
import { novelApi } from '../../api/novelApi'
import { useAutoSave, useBeforeUnload } from '../../hooks/useAutoSave'
import { useTaskProgress } from '../../hooks/useTaskProgress'
import { characterApi } from '../../api/characterApi'
import { worldApi, sceneAssetApi, propApi, buildingApi, outfitApi } from '../../api/worldApi'
import ProjectFilter from '../../components/common/ProjectFilter'
import EmptyState from '../../components/common/EmptyState'
import LazyImage from '../../components/common/LazyImage'
import StreamOutputPanel from '../../components/common/StreamOutputPanel'
import type { LayoutPage, Novel } from '../../types/novel'
import type { Character, CharacterState } from '../../types/character'
import type { SceneAsset, Prop, Building, Outfit } from '../../types/world'

const { Text } = Typography
const { TextArea } = Input

type ReferenceItem = SceneAsset | Prop | Building | Outfit | Character | CharacterState

function getRefImageUrl(item: ReferenceItem): string {
  if ('image_url' in item && item.image_url) return item.image_url
  return ''
}

function getReferenceImageUrl(item: ReferenceItem): string {
  const url = getRefImageUrl(item)
  if (url.startsWith('/storage/')) {
    return `${window.location.origin}${url}`
  }
  return url
}

function getReferenceLabel(item: ReferenceItem): string {
  return item.name || '未知'
}

function getRefId(item: ReferenceItem): string {
  return (item as any).id || ''
}

export default function GenerationCenter() {
  const { id: projectId } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const {
    layoutData,
    layoutLoading,
    fetchLayout,
    generateImagePrompts,
    saveLayout,
    updateGenerationTask,
    batchDeletePagesContent,
  } = usePipelineStore()

  const [novels, setNovels] = useState<Novel[]>([])
  const [selectedNovelId, setSelectedNovelId] = useState<string>('')

  const [selectedChapterIdx, setSelectedChapterIdx] = useState<number | null>(null)
  const [selectedPageIdx, setSelectedPageIdx] = useState<number | null>(null)
  const [expandedChapters, setExpandedChapters] = useState<Set<number>>(new Set())

  // Reference images
  const [worlds, setWorlds] = useState<any[]>([])
  const [characters, setCharacters] = useState<Character[]>([])
  const [characterStates, setCharacterStates] = useState<CharacterState[]>([])
  const [sceneAssets, setSceneAssets] = useState<SceneAsset[]>([])
  const [props, setProps] = useState<Prop[]>([])
  const [buildings, setBuildings] = useState<Building[]>([])
  const [outfits, setOutfits] = useState<Outfit[]>([])
  const [selectedRefIds, setSelectedRefIds] = useState<Set<string>>(new Set())

  const [editablePrompts, setEditablePrompts] = useState<Record<string, string>>({})
  const [matchLoading, setMatchLoading] = useState(false)
  const [pageRefMap, setPageRefMap] = useState<Record<string, string[]>>({})
  const refContainerRef = useRef<HTMLDivElement>(null)

  // 批量删除状态
  const totalPages = layoutData.reduce((sum, ch) => sum + ch.pages.length, 0)
  const [deleteStartPage, setDeleteStartPage] = useState(1)
  const [deleteEndPage, setDeleteEndPage] = useState(totalPages || 1)
  const [deleteType, setDeleteType] = useState<'prompt' | 'reference' | 'page'>('prompt')

  // 当 totalPages 变化时自动调整删除范围
  useEffect(() => {
    setDeleteStartPage(1)
    setDeleteEndPage(totalPages || 1)
  }, [totalPages])

  // 进度统计 - 前100页（独立于 deleteType）
  const [progressViewType, setProgressViewType] = useState<'prompt' | 'reference' | 'page'>('prompt')
  const PROGRESS_LIMIT = 100
  const first100Pages = layoutData.flatMap(ch => ch.pages).slice(0, PROGRESS_LIMIT)
  const progressCount = first100Pages.filter(p => {
    if (progressViewType === 'prompt') return (p.image_prompt || '').trim().length > 0
    if (progressViewType === 'reference') {
      const refs = (p as LayoutPage & { reference_ids?: string[] }).reference_ids
      return Array.isArray(refs) && refs.length > 0
    }
    if (progressViewType === 'page') return (p.image_url || '').trim().length > 0
    return false
  }).length

  const { saveStatus, triggerSave, markDirty } = useAutoSave({
    onSave: async () => {
      if (!projectId || !selectedNovelId) return
      const chaptersData = layoutData.map(ch => ({
        chapterTitle: ch.title,
        pages: ch.pages.map(p => ({
          pageId: p.page_id,
          layoutType: p.layout_type,
          pagePurpose: p.page_purpose || '',
          visualFocus: p.visual_focus || '',
          shots: p.shots || [],
          imagePrompt: Object.prototype.hasOwnProperty.call(editablePrompts, p.id)
            ? editablePrompts[p.id]
            : p.image_prompt || '',
          imageUrl: p.image_url || '',
          referenceIds: (p as any).reference_ids || pageRefMap[p.page_id] || [],
        })),
      }))
      await saveLayout(projectId, selectedNovelId, chaptersData)
      message.success('保存成功')
    },
  })

  useBeforeUnload(saveStatus === 'unsaved')

  // ===== Data fetching =====
  useEffect(() => {
    if (!projectId) return
    let cancelled = false
    novelApi.listByProject(projectId)
      .then((res: any) => {
        if (cancelled) return
        const data = res?.data?.items || res?.data || []
        setNovels(data)
        if (data.length > 0) setSelectedNovelId(data[0].id)
      })
      .catch((err: any) => console.error('获取小说列表失败:', err))
    return () => { cancelled = true }
  }, [projectId])

  useEffect(() => {
    if (!projectId || !selectedNovelId) return
    fetchLayout(projectId, selectedNovelId)
  }, [projectId, selectedNovelId, fetchLayout])

  // 从 layoutData 同步 reference_ids 到 pageRefMap
  useEffect(() => {
    if (!layoutData || layoutData.length === 0) return
    const map: Record<string, string[]> = {}
    for (const ch of layoutData) {
      for (const p of ch.pages) {
        const refs = (p as (LayoutPage & { reference_ids?: string[] })).reference_ids
        if (refs && Array.isArray(refs) && refs.length > 0) {
          map[p.page_id] = refs
        }
      }
    }
    if (Object.keys(map).length > 0) {
      setPageRefMap(prev => ({ ...prev, ...map }))
    }
  }, [layoutData])

  useEffect(() => {
    if (!projectId) return
    let cancelled = false
    worldApi.list(projectId).then((res: any) => {
      if (!cancelled) setWorlds(res?.data?.items || [])
    }).catch((err) => console.error('获取世界观列表失败:', err))
    return () => { cancelled = true }
  }, [projectId])

  useEffect(() => {
    if (!projectId || worlds.length === 0) { setSceneAssets([]); setProps([]); setBuildings([]); setOutfits([]); return }
    let cancelled = false
    const worldId = worlds[0]?.id
    if (!worldId) return
    Promise.all([
      sceneAssetApi.list(projectId, worldId).catch(() => ({ data: { items: [] } })),
      propApi.list(projectId, worldId).catch(() => ({ data: { items: [] } })),
      buildingApi.list(projectId, worldId).catch(() => ({ data: { items: [] } })),
      outfitApi.list(projectId, worldId).catch(() => ({ data: { items: [] } })),
    ]).then(([saRes, pRes, bRes, oRes]) => {
      if (cancelled) return
      const extract = (r: any) => r?.data?.data?.items || r?.data?.items || []
      setSceneAssets(extract(saRes))
      setProps(extract(pRes))
      setBuildings(extract(bRes))
      setOutfits(extract(oRes))
    })
    return () => { cancelled = true }
  }, [projectId, worlds])

  // 独立获取角色参考图
  useEffect(() => {
    if (!projectId) { setCharacters([]); setCharacterStates([]); return }
    let cancelled = false
    characterApi.list(projectId).then((res: any) => {
      if (cancelled) return
      const list: Character[] = res?.data?.items || []
      setCharacters(list.filter(c => c.image_url))
      const allStates: CharacterState[] = []
      for (const c of list) {
        if (c.states) {
          for (const s of c.states) {
            if (s.image_url) allStates.push(s)
          }
        }
      }
      setCharacterStates(allStates)
    }).catch(() => { setCharacters([]); setCharacterStates([]) })
    return () => { cancelled = true }
  }, [projectId])

  const allReferences: ReferenceItem[] = [...characters, ...characterStates, ...sceneAssets, ...props, ...buildings, ...outfits]

  const selectedChapter = selectedChapterIdx !== null ? layoutData[selectedChapterIdx] ?? null : null
  const selectedPage = selectedChapter && selectedPageIdx !== null
    ? selectedChapter.pages[selectedPageIdx] ?? null
    : null

  const pageContentText = selectedPage
    ? (selectedPage.shots || []).map((s: any) => `[${s.shotId}] ${s.content}`).join('\n')
    : ''

  // ===== Handlers =====
  const toggleChapter = (idx: number) => {
    setExpandedChapters(prev => {
      const next = new Set(prev)
      next.has(idx) ? next.delete(idx) : next.add(idx)
      return next
    })
  }

  const selectPage = (chIdx: number, pgIdx: number) => {
    setSelectedChapterIdx(chIdx)
    setSelectedPageIdx(pgIdx)
    // 自动勾选该页匹配的参考图
    const chapter = layoutData[chIdx]
    const page = chapter?.pages[pgIdx]
    // pageRefMap 优先（最新匹配结果），包含该页key才使用，否则用数据库保存的
    const refs = page ? (
      page.page_id in pageRefMap ? pageRefMap[page.page_id] : ((page as (LayoutPage & { reference_ids?: string[] })).reference_ids || [])
    ) : []
    setSelectedRefIds(new Set(refs))
  }

  const handleSave = async () => {
    if (!projectId || !selectedNovelId) { message.warning('请先选择小说'); return }
    await triggerSave()
  }

  const handleBatchDelete = () => {
    if (!projectId || !selectedNovelId) { message.warning('请先选择小说'); return }
    if (deleteStartPage < 1 || deleteEndPage < 1 || deleteStartPage > deleteEndPage) {
      message.warning('页码范围无效')
      return
    }
    if (deleteEndPage > totalPages) {
      message.warning(`页码范围超出总页数 (共 ${totalPages} 页)`)
      return
    }
    const typeLabels: Record<string, string> = {
      prompt: '生图提示词',
      reference: '参考图',
      page: '漫画页',
    }
    const typeDescriptions: Record<string, string> = {
      prompt: '将清空对应页面的生图提示词（image_prompt），此操作不可撤销。',
      reference: '将清空对应页面的参考图关联（reference_ids），此操作不可撤销。',
      page: '将删除对应漫画页的图片文件及数据库中的 image_url，此操作不可撤销。',
    }
    Modal.confirm({
      title: `确认删除第 ${deleteStartPage}-${deleteEndPage} 页${typeLabels[deleteType]}？`,
      content: typeDescriptions[deleteType],
      okText: '确认删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        try {
          await batchDeletePagesContent(projectId, selectedNovelId, deleteStartPage, deleteEndPage, deleteType)
          setSelectedChapterIdx(null)
          setSelectedPageIdx(null)
          // D79: 清除编辑缓存，防止旧编辑值在新页面复用相同 page_id 时"复活"
          setEditablePrompts({})
          setPageRefMap({})
          message.success(`已删除第 ${deleteStartPage}-${deleteEndPage} 页${typeLabels[deleteType]}`)
        } catch {
          message.error('删除失败')
        }
      },
    })
  }

  const handleGeneratePrompts = async () => {
    if (!projectId || !selectedNovelId) { message.warning('请先选择小说'); return }
    setPromptGenLoading(true)
    try {
      const taskId = await generateImagePrompts(projectId, selectedNovelId)
      if (taskId) taskProgress.startPolling(taskId)
    } catch (e) {
      console.error('生成提示词失败:', e)
      setPromptGenLoading(false)  // D52: 仅失败时重置，成功时由 onCompleted 重置
    }
    // D52: 移除 30 秒兜底 setTimeout，依赖 taskProgress.onCompleted/onFailed
  }

  const handleGenerateImages = async () => {
    if (!projectId || !selectedNovelId) { message.warning('请先选择小说'); return }
    setBatchImageLoading(true)
    try {
      const res: any = await novelApi.generatePageImagesWithRefs(projectId, selectedNovelId, pageRefMap)
      const taskId = res?.data?.task_id
      if (taskId) taskProgress.startPolling(taskId)
    } catch {
      message.error('图片生成失败')
      setBatchImageLoading(false)  // D52: 仅失败时重置
    }
    // D52: 移除 30 秒兜底 setTimeout
  }

  // 当前页：重新生成提示词
  const handleRegeneratePrompt = async () => {
    if (!selectedPage) { message.warning('请先选择页面'); return }
    setPromptGenLoading(true)
    try {
      const res: any = await novelApi.regeneratePagePrompt(projectId!, selectedNovelId, selectedPage.page_id)
      const taskId = res?.data?.task_id
      if (taskId) taskProgress.startPolling(taskId)
    } catch {
      message.error('提示词生成失败')
      setPromptGenLoading(false)  // D52: 仅失败时重置
    }
    // D52: 移除 30 秒兜底 setTimeout
  }

  // AI 匹配参考图
  const handleMatchReferences = async () => {
    if (!projectId || !selectedNovelId) return
    setMatchLoading(true)
    try {
      const res: any = await novelApi.matchReferences(projectId, selectedNovelId)
      // API 返回 task_id，匹配结果由后端异步保存到 DB
      const taskId = res?.data?.task_id
      if (taskId) {
        taskProgress.startPolling(taskId)
      } else {
        setMatchLoading(false)
      }
    } catch {
      message.error('参考图匹配失败')
      setMatchLoading(false)
    }
  }

  // 当前页：生图
  const handleGenerateSingleImage = async () => {
    if (!selectedPage) { message.warning('请先选择页面'); return }
    setSingleGenLoading(true)
    try {
      const res: any = await novelApi.generateSingleImage(
        projectId!, selectedNovelId, selectedPage.page_id,
        Array.from(selectedRefIds)
      )
      const taskId = res?.data?.task_id
      if (taskId) taskProgress.startPolling(taskId)
    } catch {
      message.error('图片生成失败')
      setSingleGenLoading(false)  // D52: 仅失败时重置
    }
    // D52: 移除 30 秒兜底 setTimeout
  }

  const toggleRefSelection = (id: string) => {
    setSelectedRefIds(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  const scrollRefs = (dir: 'left' | 'right') => {
    refContainerRef.current?.scrollBy({ left: dir === 'left' ? -300 : 300, behavior: 'smooth' })
  }

  const [imageGenVersion, setImageGenVersion] = useState(0)

  const [singleGenLoading, setSingleGenLoading] = useState(false)
  const [promptGenLoading, setPromptGenLoading] = useState(false)
  const [batchImageLoading, setBatchImageLoading] = useState(false)

  const taskProgress = useTaskProgress({
    projectId,
    // 流式任务轮询间隔 1s
    pollInterval: 1000,
    onCompleted: () => {
      setSingleGenLoading(false)
      setPromptGenLoading(false)
      setBatchImageLoading(false)
      setMatchLoading(false)
      // D53: 递增版本号强制浏览器刷新图片缓存
      setImageGenVersion(v => v + 1)
      if (projectId && selectedNovelId) {
        fetchLayout(projectId, selectedNovelId)
        updateGenerationTask('', 'completed')
      }
    },
    onFailed: (error) => {
      setSingleGenLoading(false)
      setPromptGenLoading(false)
      setBatchImageLoading(false)
      setMatchLoading(false)
      console.error('任务失败:', error)
      updateGenerationTask('', 'failed')
    },
  })

  const getImageSrc = (url: string | undefined | null): string => {
    if (!url) return ''
    const base = url.startsWith('/storage/') ? `${window.location.origin}${url}` : url
    // 加 ?v= 强制浏览器刷新缓存
    return `${base}?v=${imageGenVersion}`
  }

  const handlePromptChange = (pageId: string, value: string) => {
    setEditablePrompts(prev => ({ ...prev, [pageId]: value }))
    markDirty()
  }

  // ===== 全局模式（无项目ID）：选择项目后跳转到对应项目的生图中心 =====
  if (!projectId) {
    return (
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
          <h2 style={{ margin: 0, fontSize: 20, fontWeight: 600 }}>生图中心</h2>
        </div>
        <Card style={{ marginBottom: 16 }}>
          <ProjectFilter
            projectId={undefined}
            onProjectChange={(newProjectId) => {
              if (newProjectId) {
                navigate(`/projects/${newProjectId}/generation`, { replace: true })
              }
            }}
            showSearch={false}
          />
        </Card>
        <EmptyState description="请先选择一个项目，进入该项目的生图中心" />
      </div>
    )
  }

  // ===== Render =====
  if (layoutLoading && layoutData.length === 0) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '60vh' }}>
        <Spin size="large" tip="加载排版数据..." />
      </div>
    )
  }

  return (
    <div style={{ height: 'calc(100vh - 104px)', display: 'flex', flexDirection: 'column' }}>
      {/* === Header === */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '4px 0 8px 0', flexShrink: 0 }}>
        <Space>
          {novels.length > 0 && (
            <select
              value={selectedNovelId}
              onChange={e => { setSelectedNovelId(e.target.value); setSelectedChapterIdx(null); setSelectedPageIdx(null) }}
              style={{ padding: '4px 8px', border: '1px solid #d9d9d9', borderRadius: 4, fontSize: 13, minWidth: 140 }}
            >
              {novels.map(n => <option key={n.id} value={n.id}>{n.title}</option>)}
            </select>
          )}
          {/* 多功能删除 */}
          <span style={{ fontSize: 12, color: '#666' }}>第</span>
          <InputNumber
            size="small"
            min={1}
            max={totalPages || 1}
            value={deleteStartPage}
            onChange={v => setDeleteStartPage(v || 1)}
            style={{ width: 52 }}
          />
          <span style={{ fontSize: 12, color: '#666' }}>-</span>
          <InputNumber
            size="small"
            min={1}
            max={totalPages || 1}
            value={deleteEndPage}
            onChange={v => setDeleteEndPage(v || 1)}
            style={{ width: 52 }}
          />
          <span style={{ fontSize: 12, color: '#666' }}>页</span>
          <Select
            size="small"
            value={deleteType}
            onChange={v => setDeleteType(v)}
            style={{ width: 90 }}
            options={[
              { value: 'prompt', label: '生图提示词' },
              { value: 'reference', label: '参考图' },
              { value: 'page', label: '漫画页' },
            ]}
          />
          <Button size="small" icon={<DeleteOutlined />} onClick={handleBatchDelete} danger disabled={!selectedNovelId || totalPages === 0}>
            删除
          </Button>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: 4, marginLeft: 8, padding: '0 8px', background: '#f5f5f5', borderRadius: 4, height: 22 }}>
            <span style={{ fontSize: 11, color: '#888' }}>进度:</span>
            <span style={{ fontSize: 11, fontWeight: 600, color: '#1677ff' }}>{progressCount}</span>
            <span style={{ fontSize: 11, color: '#aaa' }}>/</span>
            <span style={{ fontSize: 11, color: '#666' }}>{Math.min(PROGRESS_LIMIT, totalPages)}</span>
            <Select
              size="small"
              value={progressViewType}
              onChange={v => setProgressViewType(v)}
              style={{ width: 80, fontSize: 11 }}
              bordered={false}
              options={[
                { value: 'prompt', label: '提示词' },
                { value: 'reference', label: '参考图' },
                { value: 'page', label: '漫画页' },
              ]}
            />
          </div>
        </Space>
        <Space>
          <Button icon={<SaveOutlined />} onClick={handleSave} loading={saveStatus === 'saving'} disabled={!selectedNovelId}>保存</Button>
          {saveStatus === 'saving' && <Text type="secondary" style={{ fontSize: 12 }}>保存中...</Text>}
          {saveStatus === 'saved' && layoutData.length > 0 && <Text type="success" style={{ fontSize: 12 }}>已保存</Text>}
          {saveStatus === 'error' && <Text type="danger" style={{ fontSize: 12 }}>保存失败</Text>}
          <Button icon={<ExperimentOutlined />} onClick={handleMatchReferences} loading={matchLoading} disabled={!selectedNovelId || layoutData.length === 0}>一键匹配参考图</Button>
          <Button type="primary" icon={<FileTextOutlined />} onClick={handleGeneratePrompts} loading={promptGenLoading} disabled={!selectedNovelId || layoutData.length === 0}>一键生成提示词</Button>
          <Button type="primary" icon={<PictureOutlined />} onClick={handleGenerateImages} loading={batchImageLoading} disabled={!selectedNovelId || layoutData.length === 0} style={{ background: '#52c41a', borderColor: '#52c41a' }}>一键生成图片</Button>
        </Space>
      </div>

      {taskProgress.isFailed && taskProgress.errorMessage && (
        <Alert message={taskProgress.errorMessage} type="error" showIcon closable style={{ marginBottom: 8 }} />
      )}

      {/* 流式输出：一键生成提示词 / 一键匹配参考图时实时展示生成内容 */}
      <StreamOutputPanel
        visible={taskProgress.isRunning}
        streamText={taskProgress.streamText}
        title="AI 正在生成提示词/匹配参考图（流式输出）..."
      />

      {/* === Body === */}
      <div style={{ flex: 1, display: 'flex', gap: 10, overflow: 'hidden' }}>
        {/* === Left: Chapter List === */}
        <div style={{ width: 180, flexShrink: 0, overflowY: 'auto', background: '#fafafa', borderRadius: 8, padding: 6, border: '1px solid #f0f0f0' }}>
          {layoutData.length === 0 ? (
            <Empty description="暂无排版数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />
          ) : (
            layoutData.map((ch, chIdx) => (
              <div key={ch.id || chIdx} style={{ marginBottom: 2 }}>
                <div onClick={() => toggleChapter(chIdx)} style={{ padding: '6px 8px', cursor: 'pointer', borderRadius: 4, background: expandedChapters.has(chIdx) ? '#e6f4ff' : 'transparent', fontWeight: expandedChapters.has(chIdx) ? 600 : 400, fontSize: 12, userSelect: 'none', display: 'flex', alignItems: 'center', gap: 4 }}>
                  <span style={{ fontSize: 9, color: '#999' }}>{expandedChapters.has(chIdx) ? '▼' : '▶'}</span>
                  <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>第{chIdx + 1}章 {ch.title}</span>
                </div>
                {expandedChapters.has(chIdx) && (
                  <div style={{ paddingLeft: 12 }}>
                    {ch.pages.map((pg, pgIdx) => (
                      <div key={pg.id || pgIdx} onClick={() => selectPage(chIdx, pgIdx)}
                        style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '4px 6px', cursor: 'pointer', borderRadius: 4, background: selectedChapterIdx === chIdx && selectedPageIdx === pgIdx ? '#1677ff' : 'transparent', color: selectedChapterIdx === chIdx && selectedPageIdx === pgIdx ? '#fff' : 'inherit', marginBottom: 1 }}>
                        <LazyImage src={getImageSrc(pg.image_url)} alt={pg.page_id} style={{ width: 36, height: 24, objectFit: 'cover', borderRadius: 2, background: '#f0f0f0' }} />
                        <span style={{ fontSize: 11 }}>{pg.page_id}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))
          )}
        </div>

        {/* === Center: Main Area === */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 6, overflow: 'hidden' }}>
          {!selectedPage ? (
            <div style={{ flex: 1, display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
              <Empty description="请从左侧选择页面" />
            </div>
          ) : (
            <>
              {/* Large comic image - fill available space */}
              <div style={{ flex: 1, overflow: 'hidden', background: '#f5f5f5', borderRadius: 8, position: 'relative', display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
                <div style={{ width: '100%', height: '100%', display: 'flex', justifyContent: 'center', alignItems: 'center', padding: 4 }}>
                  {selectedPage.image_url ? (
                    <Image
                      rootClassName="gen-page-image"
                      src={getImageSrc(selectedPage.image_url)}
                      alt={selectedPage.page_id}
                      style={{ width: '100%', height: '100%', objectFit: 'contain', borderRadius: 4, display: 'block' }}
                      preview={{ src: getImageSrc(selectedPage.image_url) }}
                    />
                  ) : (
                    <Text type="secondary" style={{ fontSize: 14 }}>暂无图片</Text>
                  )}
                </div>
                <div style={{ position: 'absolute', bottom: 8, right: 8, fontSize: 12, fontWeight: 600, color: '#666', background: 'rgba(255,255,255,0.8)', padding: '2px 8px', borderRadius: 4 }}>
                  {selectedPage.page_id}
                </div>
              </div>

              {/* Compact buttons row - gives more space to reference strip below */}
              <div style={{ flexShrink: 0, display: 'flex', alignItems: 'center', gap: 4, minHeight: 22 }}>
                <Button size="small" icon={<ReloadOutlined />} onClick={handleRegeneratePrompt} loading={promptGenLoading} disabled={!selectedPage} style={{ fontSize: 10, height: 22, padding: '0 6px' }}>
                  重生提示词
                </Button>
                <Button size="small" type="primary" icon={<ThunderboltOutlined />} onClick={handleGenerateSingleImage} loading={singleGenLoading} disabled={!selectedPage} style={{ fontSize: 10, height: 22, padding: '0 6px', background: '#52c41a', borderColor: '#52c41a' }}>
                  单页生图
                </Button>
              </div>

              {/* Reference images strip */}
              <div style={{ flexShrink: 0, height: 250, display: 'flex', flexDirection: 'column', gap: 2 }}>
                <Text type="secondary" style={{ fontSize: 11 }}>参考图（角色/角色状态/场景/道具/建筑/服装）</Text>
                {allReferences.length === 0 ? (
                  <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#fafafa', borderRadius: 4, fontSize: 11, color: '#999' }}>
                    暂无参考图，请先在世界观中添加
                  </div>
                ) : (
                  <div style={{ position: 'relative', flex: 1 }}>
                    <div ref={refContainerRef} style={{ display: 'flex', gap: 8, overflowX: 'auto', padding: '2px 0', height: '100%', scrollBehavior: 'smooth', alignItems: 'stretch' }}>
                      {allReferences.map(item => {
                        const itemId = getRefId(item)
                        return (
                          <div key={itemId} style={{ flexShrink: 0, width: 160, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2 }}>
                            <LazyImage src={getReferenceImageUrl(item)} alt={getReferenceLabel(item)} style={{ width: '100%', height: 190, objectFit: 'cover', borderRadius: 4, border: selectedRefIds.has(itemId) ? '2px solid #1677ff' : '2px solid transparent', background: '#f0f0f0', cursor: 'pointer' }} />
                            <Checkbox checked={selectedRefIds.has(itemId)} onChange={() => toggleRefSelection(itemId)} style={{ fontSize: 10 }}>
                              <span style={{ fontSize: 10, maxWidth: 150, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', display: 'inline-block' }}>{getReferenceLabel(item)}</span>
                            </Checkbox>
                          </div>
                        )
                      })}
                    </div>
                    {allReferences.length > 5 && (
                      <>
                        <Button size="small" icon={<LeftOutlined />} onClick={() => scrollRefs('left')} style={{ position: 'absolute', left: 0, top: '50%', transform: 'translateY(-50%)', opacity: 0.7, height: 24, width: 20, minWidth: 20, padding: 0 }} />
                        <Button size="small" icon={<RightOutlined />} onClick={() => scrollRefs('right')} style={{ position: 'absolute', right: 0, top: '50%', transform: 'translateY(-50%)', opacity: 0.7, height: 24, width: 20, minWidth: 20, padding: 0 }} />
                      </>
                    )}
                  </div>
                )}
              </div>
            </>
          )}
        </div>

        {/* === Right: Image Prompt + Page Content === */}
        <div style={{ width: 280, flexShrink: 0, display: 'flex', flexDirection: 'column', gap: 6 }}>
          <div style={{ flex: 2, display: 'flex', flexDirection: 'column', gap: 4, minHeight: 0 }}>
            <Text strong style={{ fontSize: 12, flexShrink: 0 }}>生图提示词</Text>
            {selectedPage ? (
              <TextArea
                value={editablePrompts[selectedPage.id] !== undefined ? editablePrompts[selectedPage.id] : selectedPage.image_prompt || ''}
                onChange={e => handlePromptChange(selectedPage.id, e.target.value)}
                style={{ flex: 1, fontSize: 11, fontFamily: 'monospace' }}
                placeholder="点击「一键生成提示词」或手动输入..."
              />
            ) : (
              <div style={{ flex: 1, display: 'flex', justifyContent: 'center', alignItems: 'center', background: '#fafafa', borderRadius: 4 }}>
                <Text type="secondary" style={{ fontSize: 12 }}>请选择页面</Text>
              </div>
            )}
          </div>
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 2, minHeight: 0 }}>
            <Text strong style={{ fontSize: 12, flexShrink: 0 }}>页面文案</Text>
            <div style={{ flex: 1, overflow: 'auto', background: '#fafafa', borderRadius: 4, padding: '4px 8px', border: '1px solid #f0f0f0', fontSize: 11, lineHeight: '1.5', whiteSpace: 'pre-wrap' }}>
              {pageContentText || <Text type="secondary" style={{ fontSize: 11 }}>暂无内容</Text>}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
