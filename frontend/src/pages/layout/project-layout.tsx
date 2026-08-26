import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Button,
  Space,
  Typography,
  message,
  Spin,
  Empty,
  Tag,
  Modal,
} from 'antd'
import {
  ArrowLeftOutlined,
  ThunderboltOutlined,
  SaveOutlined,
  DeleteOutlined,
} from '@ant-design/icons'
import { usePipelineStore } from '../../stores/pipelineStore'
import { novelApi } from '../../api/novelApi'
import { useAutoSave, useBeforeUnload } from '../../hooks/useAutoSave'
import { useTaskProgress } from '../../hooks/useTaskProgress'
import { TaskProgressBar } from '../../components/common/TaskProgressBar'
import StreamOutputPanel from '../../components/common/StreamOutputPanel'

const { Title, Text } = Typography

/** 排版详情子组件 */
function LayoutDetail({ projectId, novelId }: { projectId: string; novelId: string }) {
  const navigate = useNavigate()
  const {
    layoutData,
    layoutLoading,
    layoutGenerating,
    fetchLayout,
    generateLayout,
    saveLayout,
    deleteAllLayout,
    deleteLayoutChapter,
    updateGenerationTask,
  } = usePipelineStore()

  const [selectedChapterId, setSelectedChapterId] = useState<string | null>(null)

  const { saveStatus, triggerSave } = useAutoSave({
    onSave: async () => {
      if (!projectId || !novelId) return
      const chapters = layoutData.map((ch) => ({
        chapterTitle: ch.title,
        pages: ch.pages.map((p) => ({
          pageId: p.page_id,
          layoutType: p.layout_type,
          pagePurpose: p.page_purpose,
          visualFocus: p.visual_focus,
          shots: p.shots,
        })),
      }))
      await saveLayout(projectId, novelId, chapters)
      message.success('排版保存成功')
    },
  })

  useBeforeUnload(saveStatus === 'unsaved')

  useEffect(() => {
    fetchLayout(projectId, novelId)
  }, [projectId, novelId])

  useEffect(() => {
    if (layoutData.length > 0) {
      if (!selectedChapterId || !layoutData.find((ch) => ch.id === selectedChapterId)) {
        setSelectedChapterId(layoutData[0].id)
      }
    } else {
      setSelectedChapterId(null)
    }
  }, [layoutData])

  const selectedChapter = layoutData.find((ch) => ch.id === selectedChapterId) || null

  // 计算 shot 的全局连续序号（仅用于展示）。
  // 后端 shot_id 按章独立编号（"01"、"02"...），跨章会重复，
  // 但分镜/排版的关联键是 (章节序号, shot_id)，因此只在 UI 层做全局映射。
  // 排版数据里 shot 没有 DB id，用 (chapterId, pageId, shotId) 作为组合键。
  const shotGlobalIndexMap = new Map<string, number>()
  let _globalCounter = 1
  layoutData.forEach((ch) => {
    ch.pages.forEach((p) => {
      p.shots.forEach((s) => {
        shotGlobalIndexMap.set(`${ch.id}|${p.id}|${s.shotId}`, _globalCounter++)
      })
    })
  })
  const formatGlobalShotId = (chapterId: string, pageId: string, shotId: string): string => {
    const n = shotGlobalIndexMap.get(`${chapterId}|${pageId}|${shotId}`)
    return n == null ? '--' : String(n).padStart(2, '0')
  }

  const handleGenerate = async () => {
    try {
      const taskId = await generateLayout(projectId, novelId)
      if (taskId) {
        taskProgress.startPolling(taskId)
      }
    } catch (e: any) {
      console.error('生成排版失败:', e)
    }
  }

  const handleSave = async () => {
    await triggerSave()
  }

  const handleDeleteAllLayout = () => {
    if (!projectId || !novelId) return
    Modal.confirm({
      title: '确认删除所有排版？',
      content: '将删除所有排版数据，以及基于排版生成的生图提示词、参考图、漫画页图片，此操作不可撤销。分镜数据不受影响。',
      okText: '确认删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        try {
          await deleteAllLayout(projectId, novelId)
          message.success('已删除所有排版及下游数据')
        } catch {
          message.error('删除失败')
        }
      },
    })
  }

  const handleDeleteChapter = (chapterId: string, chapterTitle: string) => {
    if (!projectId || !novelId) return
    Modal.confirm({
      title: `确认删除「${chapterTitle}」的排版？`,
      content: '将删除该章节的排版数据及下游数据（生图提示词、参考图、漫画页图片），此操作不可撤销。',
      okText: '确认删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        try {
          await deleteLayoutChapter(projectId, novelId, chapterId)
          message.success(`已删除「${chapterTitle}」排版数据`)
        } catch {
          message.error('删除失败')
        }
      },
    })
  }

  const [novelTitle, setNovelTitle] = useState('')
  useEffect(() => {
    if (!projectId || !novelId) return
    let cancelled = false
    novelApi.getById(projectId, novelId)
      .then((res: any) => { if (!cancelled) setNovelTitle(res?.data?.title || '') })
      .catch((err) => console.error('获取小说标题失败:', err))
    return () => { cancelled = true }
  }, [projectId, novelId])

  const taskProgress = useTaskProgress({
    projectId,
    // 流式任务轮询间隔 1s
    pollInterval: 1000,
    onCompleted: () => {
      if (projectId && novelId) {
        fetchLayout(projectId, novelId)
        updateGenerationTask('', 'completed')
      }
    },
    onFailed: (error) => {
      console.error('排版生成失败:', error)
      updateGenerationTask('', 'failed')
    },
  })

  const hasData = layoutData.length > 0

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        marginBottom: 16, flexShrink: 0,
      }}>
        <Space>
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(-1)}>返回</Button>
          <Title level={4} style={{ margin: 0 }}>AI排版</Title>
          {novelTitle && <Text type="secondary">- {novelTitle}</Text>}
        </Space>
        <Space>
          {hasData && (
            <Button icon={<SaveOutlined />} type="primary" loading={saveStatus === 'saving'} onClick={handleSave}>
              保存
            </Button>
          )}
          {saveStatus === 'saving' && <Text type="secondary" style={{ fontSize: 12 }}>保存中...</Text>}
          {saveStatus === 'saved' && layoutData.length > 0 && <Text type="success" style={{ fontSize: 12 }}>已保存</Text>}
          {saveStatus === 'error' && <Text type="danger" style={{ fontSize: 12 }}>保存失败</Text>}
          {hasData && (
            <Button icon={<DeleteOutlined />} danger onClick={handleDeleteAllLayout}>
              删除所有排版
            </Button>
          )}
          <Button
            type="primary"
            icon={<ThunderboltOutlined />}
            loading={layoutGenerating}
            onClick={handleGenerate}
            style={{ background: '#722ed1', borderColor: '#722ed1' }}
          >
            一键排版
          </Button>
        </Space>
      </div>

      <TaskProgressBar
        visible={taskProgress.isRunning || taskProgress.isFailed}
        status={taskProgress.status}
        progress={taskProgress.progress}
        errorMessage={taskProgress.errorMessage}
        logs={taskProgress.logs}
      />

      {/* 流式输出：AI 排版时实时展示生成内容 */}
      <StreamOutputPanel
        visible={taskProgress.isRunning}
        sections={taskProgress.streamSections}
        title="AI 正在生成排版（流式输出）..."
      />

      {layoutLoading && !hasData ? (
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <Spin tip="加载排版数据..." />
        </div>
      ) : !hasData ? (
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <Empty description="暂无排版数据，请先生成分镜，然后点击「一键排版」" />
        </div>
      ) : (
        <div style={{ flex: 1, display: 'flex', gap: 16, overflow: 'hidden' }}>
          {/* 左侧：章节列表 */}
          <div style={{
            width: 220, flexShrink: 0, overflowY: 'auto',
            borderRight: '1px solid #f0f0f0', paddingRight: 12,
          }}>
            <div style={{ marginBottom: 8, fontWeight: 600, color: '#666', fontSize: 13 }}>
              章节列表 ({layoutData.length})
            </div>
            {layoutData.map((chapter, idx) => (
              <div
                key={chapter.id}
                onClick={() => setSelectedChapterId(chapter.id)}
                style={{
                  padding: '10px 12px', marginBottom: 4, borderRadius: 6, cursor: 'pointer',
                  background: selectedChapterId === chapter.id ? '#e6f4ff' : 'transparent',
                  border: selectedChapterId === chapter.id ? '1px solid #91caff' : '1px solid transparent',
                }}
                onMouseEnter={(e) => {
                  if (selectedChapterId !== chapter.id) e.currentTarget.style.background = '#f5f5f5'
                }}
                onMouseLeave={(e) => {
                  if (selectedChapterId !== chapter.id) e.currentTarget.style.background = 'transparent'
                }}
              >
                <div style={{ fontSize: 13, fontWeight: 500, marginBottom: 2 }}>
                  <span style={{ color: '#1677ff', marginRight: 4 }}>第{idx + 1}章</span>
                  {chapter.title || `场景 ${idx + 1}`}
                </div>
                <div style={{ fontSize: 12, color: '#999' }}>{chapter.pages.length} 页</div>
              </div>
            ))}
          </div>

          {/* 右侧：排版页面列表 - 交替颜色 */}
          <div style={{ flex: 1, overflowY: 'auto' }}>
            {selectedChapter ? (
              <>
                <div style={{
                  display: 'flex', alignItems: 'center', marginBottom: 16,
                  padding: '8px 12px', background: '#fafafa', borderRadius: 6,
                  border: '1px solid #f0f0f0', flexShrink: 0,
                }}>
                  <Text type="secondary" style={{ marginRight: 8, fontSize: 13 }}>章节标题：</Text>
                  <Text style={{ fontSize: 15, fontWeight: 600, flex: 1 }}>{selectedChapter.title}</Text>
                  <Button
                    type="text"
                    size="small"
                    danger
                    icon={<DeleteOutlined />}
                    onClick={() => handleDeleteChapter(selectedChapter.id, selectedChapter.title)}
                    style={{ fontSize: 12 }}
                  >
                    删除此章节排版
                  </Button>
                </div>

                {selectedChapter.pages.map((page, idx) => {
                  const isDark = idx % 2 === 0 // P1/P3/P5 深色，P2/P4/P6 浅色
                  return (
                    <div
                      key={page.id}
                      style={{
                        padding: 16,
                        marginBottom: 12,
                        borderRadius: 8,
                        background: isDark ? '#f0f5ff' : '#fafafa',
                        border: `1px solid ${isDark ? '#d6e4ff' : '#f0f0f0'}`,
                      }}
                    >
                      {/* 页面头部：pageId + layoutType */}
                      <div style={{
                        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                        marginBottom: 8,
                      }}>
                        <Space>
                          <Text strong style={{
                            color: isDark ? '#1677ff' : '#666',
                            fontSize: 16,
                          }}>
                            {page.page_id}
                          </Text>
                          <Tag color={isDark ? 'blue' : 'default'}>{page.layout_type}</Tag>
                        </Space>
                      </div>

                      {/* pagePurpose */}
                      <div style={{ marginBottom: 8, fontSize: 13, color: '#666' }}>
                        <Text type="secondary">目的：</Text>
                        <Text style={{ fontSize: 13 }}>{page.page_purpose}</Text>
                      </div>

                      {/* visualFocus */}
                      <div style={{ marginBottom: 12, fontSize: 13, color: '#666' }}>
                        <Text type="secondary">焦点：</Text>
                        <Text style={{ fontSize: 13 }}>{page.visual_focus}</Text>
                      </div>

                      {/* shots 列表 */}
                      {page.shots.map((shot: any) => (
                        <div
                          key={shot.shotId}
                          style={{
                            display: 'flex', alignItems: 'flex-start', gap: 12,
                            padding: '8px 10px', marginBottom: 6,
                            background: isDark ? '#fff' : '#fff',
                            borderRadius: 4,
                            border: `1px solid ${isDark ? '#e6f4ff' : '#f5f5f5'}`,
                          }}
                        >
                          <Text style={{
                            fontFamily: 'monospace', fontSize: 11,
                            color: '#1677ff', background: '#e6f4ff',
                            padding: '1px 5px', borderRadius: 3, whiteSpace: 'nowrap',
                          }}>
                            {formatGlobalShotId(selectedChapter.id, page.id, shot.shotId)}
                          </Text>
                          <div style={{ flex: 1, fontSize: 13, lineHeight: 1.5 }}>
                            <div style={{ color: '#333', marginBottom: 2 }}>{shot.content}</div>
                            <div style={{ color: '#888', fontSize: 12 }}>
                              {shot.storyboardDetails || ''}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )
                })}
              </>
            ) : (
              <div style={{ textAlign: 'center', paddingTop: 60 }}>
                <Text type="secondary">请从左侧选择一个章节</Text>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export default function ProjectLayoutPage() {
  const { id: projectId } = useParams<{ id: string }>()
  const [novelId, setNovelId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  // 每项目仅允许一本小说：自动获取项目小说，直接进入排版详情（不再经过小说选择过渡页）
  useEffect(() => {
    if (!projectId) return
    setLoading(true)
    novelApi.list(projectId).then((res: any) => {
      const items = res.data?.items || []
      setNovelId(items[0]?.id || null)
    }).catch(() => {
      setNovelId(null)
    }).finally(() => setLoading(false))
  }, [projectId])

  if (!projectId) {
    return <Empty description="请先选择一个项目" />
  }

  if (loading) {
    return <Spin style={{ display: 'block', margin: '60px auto' }} tip="加载小说..." />
  }

  if (!novelId) {
    return <Empty description="该项目暂无小说，请先导入小说并生成脚本" />
  }

  return <LayoutDetail projectId={projectId} novelId={novelId} />
}
