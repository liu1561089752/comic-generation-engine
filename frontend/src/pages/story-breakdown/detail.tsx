import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Button,
  Space,
  Typography,
  message,
  Modal,
  Input,
  Spin,
  Empty,
  Tooltip,
} from 'antd'
import {
  ArrowLeftOutlined,
  ThunderboltOutlined,
  PlusOutlined,
  SaveOutlined,
  DeleteOutlined,
} from '@ant-design/icons'
import { useScriptStore } from '../../stores/scriptStore'
import type { ScriptShot } from '../../types/novel'
import { novelApi } from '../../api/novelApi'
import { useAutoSave, useBeforeUnload } from '../../hooks/useAutoSave'
import { useTaskProgress } from '../../hooks/useTaskProgress'
import { TaskProgressBar } from '../../components/common/TaskProgressBar'

const { Title, Text } = Typography
const { TextArea } = Input

interface StoryBreakdownDetailProps {
  projectId: string
  novelId: string
}

export default function StoryBreakdownDetail({ projectId, novelId }: StoryBreakdownDetailProps) {
  const navigate = useNavigate()
  const {
    scriptData,
    scriptLoading,
    scriptGenerating,
    scriptDeleting,
    fetchScript,
    generateScript,
    saveScript,
    splitShot,
    deleteScript,
    updateGenerationTask,
  } = useScriptStore()

  const [selectedChapterId, setSelectedChapterId] = useState<string | null>(null)

  // 流式输出面板自动滚动容器（ref 在渲染期可用，effect 在 taskProgress 声明后定义）

  // 拆分弹窗
  const [splitModalOpen, setSplitModalOpen] = useState(false)
  const [splittingShot, setSplittingShot] = useState<ScriptShot | null>(null)
  const [splitContentBefore, setSplitContentBefore] = useState('')
  const [splitContentAfter, setSplitContentAfter] = useState('')
  const [splitConfirming, setSplitConfirming] = useState(false)

  // 加载脚本数据
  useEffect(() => {
    if (projectId && novelId) {
      loadScript()
    }
  }, [projectId, novelId])

  const loadScript = async () => {
    if (!projectId || !novelId) return
    try {
      await fetchScript(projectId, novelId)
    } catch {
      // 忽略错误
    }
  }

  // 选中第一个章节
  useEffect(() => {
    if (scriptData.length > 0) {
      if (!selectedChapterId || !scriptData.find((ch) => ch.id === selectedChapterId)) {
        setSelectedChapterId(scriptData[0].id)
      }
    } else {
      setSelectedChapterId(null)
    }
  }, [scriptData])

  // 获取选中的章节（从store实时获取）
  const selectedChapter = scriptData.find((ch) => ch.id === selectedChapterId) || null

  // 计算 shot 的全局连续序号（仅用于展示，不修改数据库里的 shot_id）。
  // 后端 shot_id 是按章独立编号的（"01"、"02"...），跨章会重复，
  // 但 split_shot 与分镜/排版都依赖 (章节序号, shot_id) 组合键，
  // 因此只在 UI 层把 shot.id 映射成跨章连续序号展示。
  const shotGlobalIndexMap = new Map<string, number>()
  let _globalCounter = 1
  scriptData.forEach((ch) => {
    ch.shots.forEach((s) => {
      shotGlobalIndexMap.set(s.id, _globalCounter++)
    })
  })
  const formatGlobalShotId = (shot: { id: string } | null | undefined): string => {
    if (!shot) return '--'
    const n = shotGlobalIndexMap.get(shot.id)
    return n == null ? '--' : String(n).padStart(2, '0')
  }

  // 一键生成脚本
  const handleGenerateScript = async () => {
    if (!projectId || !novelId) return
    try {
      const taskId = await generateScript(projectId, novelId)
      if (taskId) {
        taskProgress.startPolling(taskId)
      }
    } catch (e) {
      console.error('生成脚本失败:', e)
    }
  }

  // 删除脚本确认
  const handleDeleteScript = () => {
    Modal.confirm({
      title: '确认删除脚本',
      content: '删除脚本会同时清空下游数据（分镜、排版、生图提示词、参考图、漫画页图片），此操作不可撤销。角色提取、世界观、场景、道具、建筑、服饰等资产数据不受影响。',
      okText: '确认删除',
      okType: 'danger',
      cancelText: '取消',
      okButtonProps: { loading: scriptDeleting },
      onOk: async () => {
        if (!projectId || !novelId) return
        try {
          await deleteScript(projectId, novelId)
          message.success('脚本已删除')
        } catch (e: any) {
          message.error(e?.response?.data?.detail || '删除脚本失败')
        }
      },
    })
  }

  const { saveStatus, triggerSave, markDirty } = useAutoSave({
    onSave: async () => {
      if (!projectId || !novelId || !scriptData) return
      const chapters = scriptData.map((ch) => ({
        chapterTitle: ch.title,
        shots: ch.shots.map((s) => ({
          shotId: s.shot_id,
          content: s.content,
        })),
      }))
      await saveScript(projectId, novelId, chapters)
      message.success('脚本保存成功')
    },
  })

  useBeforeUnload(saveStatus === 'unsaved')

  // 保存脚本
  const handleSaveScript = async () => {
    if (!projectId || !novelId || !scriptData) return
    await triggerSave()
  }

  // 修改镜头内容
  const handleShotContentChange = (chapterId: string, shotId: string, newContent: string) => {
    const updatedChapters = scriptData.map((ch) => {
      if (ch.id === chapterId) {
        return {
          ...ch,
          shots: ch.shots.map((s) =>
            s.id === shotId ? { ...s, content: newContent } : s
          ),
        }
      }
      return ch
    })
    useScriptStore.setState({ scriptData: updatedChapters })
    markDirty()
  }

  // 修改章节标题
  const handleChapterTitleChange = (chapterId: string, newTitle: string) => {
    const updatedChapters = scriptData.map((ch) =>
      ch.id === chapterId ? { ...ch, title: newTitle } : ch
    )
    useScriptStore.setState({ scriptData: updatedChapters })
    markDirty()
  }

  // 打开拆分弹窗
  const handleOpenSplitModal = (shot: ScriptShot) => {
    setSplittingShot(shot)
    setSplitContentBefore(shot.content)
    setSplitContentAfter('')
    setSplitModalOpen(true)
  }

  // 确认拆分
  const handleSplitConfirm = async () => {
    if (!projectId || !novelId || !splittingShot || !selectedChapter) return
    if (!splitContentAfter.trim()) return

    setSplitConfirming(true)
    try {
      await splitShot(
        projectId,
        novelId,
        selectedChapter.id,
        splittingShot.shot_id,
        splitContentBefore,
        splitContentAfter,
      )
      message.success('镜头拆分成功')
      setSplitModalOpen(false)
      setSplittingShot(null)
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '拆分镜头失败')
    } finally {
      setSplitConfirming(false)
    }
  }

  // 获取小说标题
  const [novelTitle, setNovelTitle] = useState('')
  useEffect(() => {
    if (!projectId || !novelId) return
    let cancelled = false
    novelApi.getById(projectId, novelId).then((res: any) => {
      if (!cancelled) setNovelTitle(res.data?.title || '')
    }).catch((err) => console.error('获取小说信息失败:', err))
    return () => { cancelled = true }
  }, [projectId, novelId])

  const hasScript = scriptData.length > 0

  const taskProgress = useTaskProgress({
    projectId,
    onCompleted: () => {
      if (projectId && novelId) {
        fetchScript(projectId, novelId)
        updateGenerationTask('', 'completed')
      }
    },
    onFailed: (error) => {
      console.error('脚本生成失败:', error)
      updateGenerationTask('', 'failed')
    },
  })

  return (
    <div style={{ height: 'calc(100vh - 104px)', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* 顶部栏 */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: 16,
        flexShrink: 0,
      }}>
        <Space>
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(-1)}>
            返回
          </Button>
          <Title level={4} style={{ margin: 0 }}>
            剧情拆解
          </Title>
          {novelTitle && (
            <Text type="secondary">- {novelTitle}</Text>
          )}
        </Space>
        <Space>
          {hasScript && (
            <>
              <Button
                icon={<SaveOutlined />}
                type="primary"
                loading={saveStatus === 'saving'}
                onClick={handleSaveScript}
              >
                保存
              </Button>
              <Button
                icon={<DeleteOutlined />}
                danger
                onClick={handleDeleteScript}
              >
                删除脚本
              </Button>
            </>
          )}
          {saveStatus === 'saving' && <Text type="secondary" style={{ fontSize: 12 }}>保存中...</Text>}
          {saveStatus === 'saved' && scriptData.length > 0 && <Text type="success" style={{ fontSize: 12 }}>已保存</Text>}
          {saveStatus === 'error' && <Text type="danger" style={{ fontSize: 12 }}>保存失败</Text>}
          <Button
            type="primary"
            icon={<ThunderboltOutlined />}
            loading={scriptGenerating}
            onClick={handleGenerateScript}
            style={{ background: '#722ed1', borderColor: '#722ed1' }}
          >
            一键生成脚本
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

      {/* 主体区域 */}
      {scriptLoading && !hasScript ? (
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <Spin tip="加载脚本数据..." />
        </div>
      ) : !hasScript ? (
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <Empty
            description="暂无脚本数据，点击右上角「一键生成脚本」开始"
          />
        </div>
      ) : (
        <div style={{ flex: 1, display: 'flex', gap: 16, overflow: 'hidden' }}>
          {/* 左侧：章节列表 */}
          <div style={{
            width: 220,
            flexShrink: 0,
            overflowY: 'auto',
            borderRight: '1px solid #f0f0f0',
            paddingRight: 12,
          }}>
            <div style={{ marginBottom: 8, fontWeight: 600, color: '#666', fontSize: 13 }}>
              章节列表 ({scriptData.length})
            </div>
            {scriptData.map((chapter, idx) => (
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
                  transition: 'all 0.2s',
                }}
                onMouseEnter={(e) => {
                  if (selectedChapterId !== chapter.id) {
                    e.currentTarget.style.background = '#f5f5f5'
                  }
                }}
                onMouseLeave={(e) => {
                  if (selectedChapterId !== chapter.id) {
                    e.currentTarget.style.background = 'transparent'
                  }
                }}
              >
                <div style={{ fontSize: 13, fontWeight: 500, marginBottom: 2 }}>
                  <span style={{ color: '#1677ff', marginRight: 4 }}>第{idx + 1}章</span>
                  {chapter.title || `场景 ${idx + 1}`}
                </div>
                <div style={{ fontSize: 12, color: '#999' }}>
                  {chapter.shots.length} 个镜头
                </div>
              </div>
            ))}
          </div>

          {/* 右侧：镜头列表 */}
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
                  <Input
                    value={selectedChapter.title}
                    onChange={(e) => handleChapterTitleChange(selectedChapter.id, e.target.value)}
                    variant="borderless"
                    style={{ fontSize: 15, fontWeight: 600, flex: 1 }}
                  />
                </div>

                {selectedChapter.shots.map((shot) => (
                  <div
                    key={shot.id}
                    className="shot-row"
                    style={{
                      display: 'flex',
                      alignItems: 'flex-start',
                      padding: '10px 12px',
                      borderBottom: '1px solid #f0f0f0',
                      position: 'relative',
                      transition: 'background 0.2s',
                    }}
                    onMouseEnter={(e) => {
                      const addBtn = e.currentTarget.querySelector('.shot-add-btn') as HTMLElement
                      if (addBtn) addBtn.style.opacity = '1'
                    }}
                    onMouseLeave={(e) => {
                      const addBtn = e.currentTarget.querySelector('.shot-add-btn') as HTMLElement
                      if (addBtn) addBtn.style.opacity = '0'
                    }}
                  >
                    <div style={{
                      minWidth: 36,
                      textAlign: 'center',
                      paddingTop: 4,
                      flexShrink: 0,
                    }}>
                      <Text
                        style={{
                          fontFamily: 'monospace',
                          fontSize: 12,
                          color: '#1677ff',
                          background: '#e6f4ff',
                          padding: '2px 6px',
                          borderRadius: 4,
                        }}
                      >
                        {formatGlobalShotId(shot)}
                      </Text>
                    </div>

                    <div style={{ flex: 1, marginLeft: 12 }}>
                      <TextArea
                        value={shot.content}
                        onChange={(e) => handleShotContentChange(selectedChapter.id, shot.id, e.target.value)}
                        variant="borderless"
                        style={{ fontSize: 14, lineHeight: 1.6 }}
                        rows={Math.max(1, Math.ceil((shot.content?.length || 1) / 60))}
                      />
                    </div>

                    <div
                      className="shot-add-btn"
                      style={{
                        position: 'absolute',
                        bottom: -12,
                        left: '50%',
                        transform: 'translateX(-50%)',
                        opacity: 0,
                        transition: 'opacity 0.2s',
                        zIndex: 10,
                        cursor: 'pointer',
                      }}
                    >
                      <Tooltip title="在此处拆分镜头">
                        <Button
                          type="primary"
                          shape="circle"
                          size="small"
                          icon={<PlusOutlined />}
                          style={{
                            background: '#52c41a',
                            borderColor: '#52c41a',
                            boxShadow: '0 2px 6px rgba(82,196,26,0.3)',
                          }}
                          onClick={() => handleOpenSplitModal(shot)}
                        />
                      </Tooltip>
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

      {/* 拆分镜头弹窗 */}
      <Modal
        title="单条脚本拆分"
        open={splitModalOpen}
        onCancel={() => {
          setSplitModalOpen(false)
          setSplittingShot(null)
        }}
        footer={
          <Space>
            <Button onClick={() => {
              setSplitModalOpen(false)
              setSplittingShot(null)
            }}>
              取消
            </Button>
            <Button
              type="primary"
              loading={splitConfirming}
              disabled={!splitContentAfter.trim()}
              onClick={handleSplitConfirm}
            >
              确定
            </Button>
          </Space>
        }
        width={700}
        destroyOnClose
        centered
      >
        <div style={{ marginBottom: 16 }}>
          <div style={{
            display: 'flex',
            alignItems: 'flex-start',
            gap: 12,
            marginBottom: 16,
          }}>
            <div style={{
              minWidth: 40,
              textAlign: 'center',
              paddingTop: 8,
            }}>
              <Text
                style={{
                  fontFamily: 'monospace',
                  fontSize: 13,
                  color: '#1677ff',
                  background: '#e6f4ff',
                  padding: '2px 8px',
                  borderRadius: 4,
                  fontWeight: 600,
                }}
              >
                {formatGlobalShotId(splittingShot)}
              </Text>
            </div>
            <div style={{ flex: 1 }}>
              <TextArea
                value={splitContentBefore}
                onChange={(e) => setSplitContentBefore(e.target.value)}
                rows={3}
                style={{ fontSize: 14 }}
                placeholder="编辑前半部分内容..."
              />
            </div>
          </div>

          <div style={{
            display: 'flex',
            alignItems: 'flex-start',
            gap: 12,
          }}>
            <div style={{
              minWidth: 40,
              textAlign: 'center',
              paddingTop: 8,
            }}>
              <Text
                style={{
                  fontFamily: 'monospace',
                  fontSize: 13,
                  color: '#52c41a',
                  background: '#f6ffed',
                  padding: '2px 8px',
                  borderRadius: 4,
                  fontWeight: 600,
                }}
              >
                {splittingShot && shotGlobalIndexMap.has(splittingShot.id)
                  ? String((shotGlobalIndexMap.get(splittingShot.id) || 0) + 1).padStart(2, '0')
                  : '--'}
              </Text>
            </div>
            <div style={{ flex: 1 }}>
              <TextArea
                value={splitContentAfter}
                onChange={(e) => setSplitContentAfter(e.target.value)}
                rows={3}
                style={{ fontSize: 14 }}
                placeholder="输入后半部分内容..."
              />
            </div>
          </div>
        </div>
      </Modal>
    </div>
  )
}
