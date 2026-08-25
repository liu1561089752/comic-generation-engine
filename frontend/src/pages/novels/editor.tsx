import { useEffect, useState } from 'react'
import { useParams, useNavigate, useSearchParams } from 'react-router-dom'
import {
  Button,
  Space,
  Card,
  Typography,
  message,
  Tag,
  Tooltip,
  Drawer,
  List,
  Modal,
  Input,
  Select,
  Badge,
  Popconfirm,
} from 'antd'
import {
  ArrowLeftOutlined,
  SaveOutlined,
  HistoryOutlined,
  EyeOutlined,
  RollbackOutlined,
} from '@ant-design/icons'
import { formatRelativeTime } from '../../utils/format'
import { useNovelStore } from '../../stores/novelStore'
import Loading from '../../components/common/Loading'
import {
  EditorParagraph,
  VersionHistoryItem,
} from '../../types/novel'

const { Title, Text } = Typography
const { TextArea } = Input

export default function NovelEditor() {
  const { id: projectId, novelId } = useParams<{
    id: string
    novelId: string
  }>()
  const [searchParams] = useSearchParams()
  const routeChapterId = searchParams.get('chapterId')
  const navigate = useNavigate()

  const {
    currentNovel,
    chapters,
    chapterDetail,
    editorLoading,
    saving,
    versionHistory,
    historyLoading,
    fetchNovel,
    fetchChapters,
    fetchChapterDetail,
    saveEditor,
    fetchVersionHistory,
    restoreVersion,
  } = useNovelStore()

  const [editorContent, setEditorContent] = useState('')
  const [activeChapterId, setActiveChapterId] = useState<string | null>(null)
  const [saveStatus, setSaveStatus] = useState<'saved' | 'unsaved' | 'saving'>('saved')

  const [historyDrawerOpen, setHistoryDrawerOpen] = useState(false)
  const [selectedVersion, setSelectedVersion] = useState<VersionHistoryItem | null>(null)
  const [versionDiffVisible, setVersionDiffVisible] = useState(false)
  const [versionDetail, setVersionDetail] = useState<EditorParagraph[] | null>(null)

  useEffect(() => {
    if (projectId && novelId) {
      fetchNovel(projectId, novelId)
      fetchChapters(projectId, novelId)
    }
  }, [projectId, novelId])

  useEffect(() => {
    const cid = routeChapterId
    if (cid && cid !== activeChapterId) {
      setActiveChapterId(cid)
      if (projectId && novelId) {
        fetchChapterDetail(projectId, novelId, cid)
      }
    }
  }, [routeChapterId, activeChapterId, projectId, novelId])

  useEffect(() => {
    if (chapters.length > 0 && !activeChapterId && !routeChapterId && projectId && novelId) {
      const firstChapter = chapters[0]
      setActiveChapterId(firstChapter.id)
      fetchChapterDetail(projectId, novelId, firstChapter.id)
    }
  }, [chapters, activeChapterId, routeChapterId, projectId, novelId])

  useEffect(() => {
    if (chapterDetail) {
      setEditorContent(chapterDetail.content || '')
    }
  }, [chapterDetail])

  const handleSave = async () => {
    if (!projectId || !novelId || !activeChapterId) return
    setSaveStatus('saving')
    try {
      const paragraphs = editorContent.split(/\n\s*\n/).filter(p => p.trim()).map((text, i) => ({
        paragraph_number: String(i + 1).padStart(4, '0'),
        text: text.trim(),
        sort_order: i,
      }))
      await saveEditor(projectId, novelId, activeChapterId, paragraphs)
      setSaveStatus('saved')
    } catch {
      setSaveStatus('unsaved')
      message.error('保存失败')
    }
  }

  const handleOpenHistory = () => {
    if (!projectId || !novelId || !activeChapterId) return
    fetchVersionHistory(projectId, novelId, activeChapterId)
    setHistoryDrawerOpen(true)
  }

  const handleViewVersion = async (version: VersionHistoryItem) => {
    if (!projectId || !novelId) return
    try {
      const { novelApi } = await import('../../api/novelApi')
      const detailRes: any = await novelApi.getVersionDetail(projectId, novelId, version.id)
      if (detailRes?.data?.content_snapshot) {
        setVersionDetail(detailRes.data.content_snapshot)
        setSelectedVersion(version)
        setVersionDiffVisible(true)
      }
    } catch {
      message.error('获取版本详情失败')
    }
  }

  const handleRestoreVersion = async (version: VersionHistoryItem) => {
    if (!projectId || !novelId || !activeChapterId) return
    try {
      await restoreVersion(projectId, novelId, version.id, activeChapterId)
      message.success(`已恢复至版本 ${version.version_number}`)
      setHistoryDrawerOpen(false)
      fetchChapterDetail(projectId, novelId, activeChapterId)
    } catch {
      message.error('恢复版本失败')
    }
  }

  const saveStatusConfig = {
    saved: { color: 'success' as const, text: '已保存' },
    unsaved: { color: 'warning' as const, text: '未保存' },
    saving: { color: 'processing' as const, text: '保存中...' },
  }

  if (!currentNovel && editorLoading) {
    return <Loading tip="加载编辑器..." />
  }

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '12px 16px',
          borderBottom: '1px solid #f0f0f0',
          background: '#fff',
        }}
      >
        <Space>
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(-1)}>
            返回
          </Button>
          <Title level={5} style={{ margin: 0 }}>
            {currentNovel?.title || '小说编辑器'}
          </Title>
          {activeChapterId && chapters.find((c) => c.id === activeChapterId) && (
            <Text type="secondary">
              - {chapters.find((c) => c.id === activeChapterId)?.title || ''}
            </Text>
          )}
        </Space>
        <Space>
          <Select
            placeholder="选择章节"
            style={{ width: 160 }}
            value={activeChapterId}
            onChange={(val) => {
              if (projectId && novelId) {
                setActiveChapterId(val)
                fetchChapterDetail(projectId, novelId, val)
              }
            }}
            options={chapters.map((ch) => ({
              value: ch.id,
              label: ch.title || `第 ${ch.chapter_number} 章`,
            }))}
          />
          <Badge
            status={saveStatusConfig[saveStatus].color}
            text={saveStatusConfig[saveStatus].text}
          />
          <Button
            type="primary"
            icon={<SaveOutlined />}
            loading={saving}
            onClick={handleSave}
          >
            保存
          </Button>
          <Button icon={<HistoryOutlined />} onClick={handleOpenHistory}>
            版本历史
          </Button>
        </Space>
      </div>

      <div style={{ flex: 1, overflow: 'auto', padding: 16, background: '#f5f5f5' }}>
        {editorLoading ? (
          <Loading tip="加载章节内容..." />
        ) : (
          <div style={{ maxWidth: 800, margin: '0 auto' }}>
            <Card style={{ background: '#fff' }}>
              <TextArea
                value={editorContent}
                onChange={(e) => {
                  setEditorContent(e.target.value)
                  setSaveStatus('unsaved')
                }}
                rows={30}
                style={{
                  fontFamily: 'monospace',
                  fontSize: 14,
                  lineHeight: 1.8,
                  border: 'none',
                  resize: 'none',
                }}
                placeholder="章节内容..."
              />
            </Card>
          </div>
        )}
      </div>

      <Drawer
        title="版本历史"
        open={historyDrawerOpen}
        onClose={() => setHistoryDrawerOpen(false)}
        width={360}
      >
        {historyLoading ? (
          <Loading tip="加载版本历史..." />
        ) : versionHistory.length === 0 ? (
          <div style={{ textAlign: 'center', padding: 40 }}>
            <Text type="secondary">暂无版本历史</Text>
          </div>
        ) : (
          <List
            dataSource={versionHistory}
            renderItem={(version) => (
              <List.Item
                actions={[
                  <Tooltip title="查看">
                    <Button
                      type="text"
                      icon={<EyeOutlined />}
                      onClick={() => handleViewVersion(version)}
                    />
                  </Tooltip>,
                  <Popconfirm
                    title={`恢复至版本 ${version.version_number}？`}
                    onConfirm={() => handleRestoreVersion(version)}
                    okText="恢复"
                    cancelText="取消"
                  >
                    <Tooltip title="恢复此版本">
                      <Button
                        type="text"
                        icon={<RollbackOutlined />}
                      />
                    </Tooltip>
                  </Popconfirm>,
                ]}
              >
                <List.Item.Meta
                  title={
                    <Space>
                      <Tag color="blue">v{version.version_number}</Tag>
                      <Text>{version.summary || `版本 ${version.version_number}`}</Text>
                    </Space>
                  }
                  description={
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      {formatRelativeTime(version.created_at)}
                    </Text>
                  }
                />
              </List.Item>
            )}
          />
        )}
      </Drawer>

      <Modal
        title={`版本 ${selectedVersion?.version_number || ''} 内容预览`}
        open={versionDiffVisible}
        onCancel={() => {
          setVersionDiffVisible(false)
          setVersionDetail(null)
        }}
        footer={null}
        width={700}
      >
        {versionDetail ? (
          <div style={{ maxHeight: 500, overflow: 'auto' }}>
            <Text style={{ whiteSpace: 'pre-wrap', fontSize: 14, lineHeight: 1.8 }}>
              {versionDetail.map(p => p.text).join('\n\n')}
            </Text>
          </div>
        ) : (
          <Loading tip="加载版本内容..." />
        )}
      </Modal>
    </div>
  )
}
