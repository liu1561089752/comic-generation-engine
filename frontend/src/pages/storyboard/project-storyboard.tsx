import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Button,
  Space,
  Typography,
  message,
  Input,
  Spin,
  Empty,
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
const { TextArea } = Input

/** 分镜详情子组件 */
function StoryboardDetail({
  projectId,
  novelId,
}: {
  projectId: string
  novelId: string
}) {
  const navigate = useNavigate()
  const {
    storyboardData,
    storyboardLoading,
    fetchStoryboard,
    generateStoryboard,
    saveStoryboard,
    deleteAllStoryboard,
    updateGenerationTask,
  } = usePipelineStore()

  const taskProgress = useTaskProgress({
    projectId,
    // 流式任务轮询间隔 1s
    pollInterval: 1000,
    onCompleted: () => {
      if (projectId && novelId) {
        fetchStoryboard(projectId, novelId)
        updateGenerationTask('', 'completed')
      }
    },
    onFailed: (error) => {
      console.error('分镜生成失败:', error)
      updateGenerationTask('', 'failed')
    },
  })

  const [selectedChapterId, setSelectedChapterId] = useState<string | null>(null)

  const { saveStatus, triggerSave, markDirty } = useAutoSave({
    onSave: async () => {
      if (!projectId || !novelId) return
      const chapters = storyboardData.map((ch) => ({
        chapterTitle: ch.title,
        shots: ch.shots.map((s) => ({
          shotId: s.shot_id,
          storyboardDetails: s.storyboard_details,
        })),
      }))
      await saveStoryboard(projectId, novelId, chapters)
      message.success('分镜保存成功')
    },
  })

  useBeforeUnload(saveStatus === 'unsaved')

  useEffect(() => {
    fetchStoryboard(projectId, novelId)
  }, [projectId, novelId])

  useEffect(() => {
    if (storyboardData.length > 0) {
      if (!selectedChapterId || !storyboardData.find((ch) => ch.id === selectedChapterId)) {
        setSelectedChapterId(storyboardData[0].id)
      }
    } else {
      setSelectedChapterId(null)
    }
  }, [storyboardData])

  const selectedChapter = storyboardData.find((ch) => ch.id === selectedChapterId) || null

  // 计算 shot 的全局连续序号（仅用于展示）。
  // 后端 shot_id 按章独立编号（"01"、"02"...），跨章会重复，
  // 但分镜/排版的关联键是 (章节序号, shot_id)，因此只在 UI 层做全局映射。
  const shotGlobalIndexMap = new Map<string, number>()
  let _globalCounter = 1
  storyboardData.forEach((ch) => {
    ch.shots.forEach((s) => {
      shotGlobalIndexMap.set(s.id, _globalCounter++)
    })
  })
  const formatGlobalShotId = (shot: { id: string } | null | undefined): string => {
    if (!shot) return '--'
    const n = shotGlobalIndexMap.get(shot.id)
    return n == null ? '--' : String(n).padStart(2, '0')
  }

  const handleGenerateStoryboard = async () => {
    if (!projectId || !novelId) return
    try {
      const taskId = await generateStoryboard(projectId, novelId)
      if (taskId) {
        taskProgress.startPolling(taskId)
      }
    } catch (e) {
      console.error('生成分镜失败:', e)
    }
  }

  const handleDeleteAllStoryboard = () => {
    if (!projectId || !novelId) return
    Modal.confirm({
      title: '确认删除所有分镜？',
      content: '将删除所有分镜数据，以及基于分镜生成的排版数据（生图提示词、参考图、漫画页图片），此操作不可撤销。建议先确认数据已备份。',
      okText: '确认删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        try {
          await deleteAllStoryboard(projectId, novelId)
          message.success('已删除所有分镜及下游数据')
        } catch {
          message.error('删除失败')
        }
      },
    })
  }

  const handleSave = async () => {
    await triggerSave()
  }

  const handleDetailChange = (chapterId: string, shotDbId: string, newVal: string) => {
    const updated = storyboardData.map((ch) => {
      if (ch.id === chapterId) {
        return {
          ...ch,
          shots: ch.shots.map((s) =>
            s.id === shotDbId ? { ...s, storyboard_details: newVal } : s
          ),
        }
      }
      return ch
    })
    usePipelineStore.setState({ storyboardData: updated })
    markDirty()
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

  const hasData = storyboardData.length > 0

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: 16,
        flexShrink: 0,
      }}>
        <Space>
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(-1)}>返回</Button>
          <Title level={4} style={{ margin: 0 }}>分镜设计</Title>
          {novelTitle && <Text type="secondary">- {novelTitle}</Text>}
        </Space>
        <Space>
          {hasData && (
            <Button icon={<SaveOutlined />} type="primary" loading={saveStatus === 'saving'} onClick={handleSave}>
              保存分镜
            </Button>
          )}
          {saveStatus === 'saving' && <Text type="secondary" style={{ fontSize: 12 }}>保存中...</Text>}
          {saveStatus === 'saved' && storyboardData.length > 0 && <Text type="success" style={{ fontSize: 12 }}>已保存</Text>}
          {saveStatus === 'error' && <Text type="danger" style={{ fontSize: 12 }}>保存失败</Text>}
          {hasData && (
            <Button icon={<DeleteOutlined />} danger onClick={handleDeleteAllStoryboard}>
              删除所有分镜
            </Button>
          )}
          <Button
            type="primary"
            icon={<ThunderboltOutlined />}
            loading={taskProgress.isRunning}
            onClick={handleGenerateStoryboard}
            style={{ background: '#722ed1', borderColor: '#722ed1' }}
          >
            一键生成分镜
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

      {/* 流式输出：AI 生成分镜时实时展示生成内容 */}
      <StreamOutputPanel
        visible={taskProgress.isRunning}
        streamText={taskProgress.streamText}
        title="AI 正在生成分镜（流式输出）..."
      />

      {storyboardLoading && !hasData ? (
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <Spin tip="加载分镜数据..." />
        </div>
      ) : !hasData ? (
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <Empty description="暂无分镜数据，请先生成脚本，然后点击「一键生成分镜」" />
        </div>
      ) : (
        <div style={{ flex: 1, display: 'flex', gap: 16, overflow: 'hidden' }}>
          <div style={{
            width: 220,
            flexShrink: 0,
            overflowY: 'auto',
            borderRight: '1px solid #f0f0f0',
            paddingRight: 12,
          }}>
            <div style={{ marginBottom: 8, fontWeight: 600, color: '#666', fontSize: 13 }}>
              章节列表 ({storyboardData.length})
            </div>
            {storyboardData.map((chapter, idx) => (
              <div
                key={chapter.id}
                onClick={() => setSelectedChapterId(chapter.id)}
                style={{
                  padding: '10px 12px',
                  marginBottom: 4,
                  borderRadius: 6,
                  cursor: 'pointer',
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
                <div style={{ fontSize: 12, color: '#999' }}>{chapter.shots.length} 个镜头</div>
              </div>
            ))}
          </div>

          <div style={{ flex: 1, overflowY: 'auto' }}>
            {selectedChapter ? (
              <>
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  marginBottom: 16,
                  padding: '8px 12px',
                  background: '#fafafa',
                  borderRadius: 6,
                  border: '1px solid #f0f0f0',
                  flexShrink: 0,
                }}>
                  <Text type="secondary" style={{ marginRight: 8, fontSize: 13 }}>章节标题：</Text>
                  <Text style={{ fontSize: 15, fontWeight: 600 }}>{selectedChapter.title}</Text>
                </div>

                {selectedChapter.shots.map((shot) => (
                  <div
                    key={shot.id}
                    style={{
                      display: 'flex',
                      alignItems: 'flex-start',
                      padding: '10px 12px',
                      borderBottom: '1px solid #f0f0f0',
                      position: 'relative',
                    }}
                  >
                    <div style={{
                      minWidth: 36,
                      textAlign: 'center',
                      paddingTop: 6,
                      flexShrink: 0,
                    }}>
                      <Text style={{
                        fontFamily: 'monospace',
                        fontSize: 12,
                        color: '#1677ff',
                        background: '#e6f4ff',
                        padding: '2px 6px',
                        borderRadius: 4,
                      }}>
                        {formatGlobalShotId(shot)}
                      </Text>
                    </div>
                    <div style={{ flex: 1, marginLeft: 12 }}>
                      <TextArea
                        value={shot.storyboard_details}
                        onChange={(e) => handleDetailChange(selectedChapter.id, shot.id, e.target.value)}
                        variant="borderless"
                        style={{ fontSize: 14, lineHeight: 1.6 }}
                        rows={Math.max(2, Math.ceil((shot.storyboard_details?.length || 1) / 80))}
                      />
                    </div>
                  </div>
                ))}
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

/** 小说选择器 */
export default function ProjectStoryboard() {
  const { id: projectId } = useParams<{ id: string }>()
  const [novelId, setNovelId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  // 每项目仅允许一本小说：自动获取项目小说，直接进入分镜详情（不再经过小说选择过渡页）
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

  return <StoryboardDetail projectId={projectId} novelId={novelId} />
}
