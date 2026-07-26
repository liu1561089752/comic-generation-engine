import { useEffect, useState, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Button,
  Descriptions,
  Space,
  Card,
  Tag,
  Typography,
  Table,
  Divider,
  message,
  Input,
  Modal,
  Select,
  Tooltip,
  Alert,
} from 'antd'
import {
  ArrowLeftOutlined,
  ThunderboltOutlined,
  ReloadOutlined,
  EditOutlined,
  MergeCellsOutlined,
  SplitCellsOutlined,
  SearchOutlined,
  EyeOutlined,
  CloseOutlined,
  SaveOutlined,
} from '@ant-design/icons'
import { formatDate, formatWordCount } from '../../utils/format'
import { useNovelStore } from '../../stores/novelStore'
import EmptyState from '../../components/common/EmptyState'
import Loading from '../../components/common/Loading'
import type { Chapter, ParagraphStats } from '../../types/novel'

const { Title, Text } = Typography

// 状态映射
const STATUS_MAP: Record<string, { color: string; text: string }> = {
  draft: { color: 'default', text: '草稿' },
  pending: { color: 'default', text: '待处理' },
  confirmed: { color: 'success', text: '已确认' },
  processing: { color: 'processing', text: '处理中' },
  completed: { color: 'success', text: '已完成' },
  failed: { color: 'error', text: '失败' },
}

// 标注类型颜色映射
const STATS_COLOR_MAP: Record<string, string> = {
  dialogue: 'blue',
  narration: 'purple',
  action: 'orange',
  description: 'green',
  unmarked: 'default',
}

const STATS_LABEL_MAP: Record<string, string> = {
  dialogue: '对话',
  narration: '旁白',
  action: '动作',
  description: '描述',
  unmarked: '未标注',
}

export default function NovelDetail() {
  const { id: projectId, novelId } = useParams<{ id: string; novelId: string }>()
  const navigate = useNavigate()

  const {
    currentNovel,
    chapters,
    loading,
    preprocessing,
    fetchNovel,
    preprocessNovel,
    updateNovelText,
    fetchChapters,
    updateChapter,
    mergeChapters,
    splitChapter,
  } = useNovelStore()

  const [paragraphs, setParagraphs] = useState<any[]>([])
  const [preprocessingResult, setPreprocessingResult] = useState<any>(null)

  // 编辑器模态框
  const [editorOpen, setEditorOpen] = useState(false)
  const [editorText, setEditorText] = useState('')
  const [showTip, setShowTip] = useState(false)
  const tipTimer = useRef<ReturnType<typeof setTimeout>>()

  // 编辑章节弹窗
  const [editModalVisible, setEditModalVisible] = useState(false)
  const [editingChapter, setEditingChapter] = useState<Chapter | null>(null)
  const [editTitle, setEditTitle] = useState('')
  const [editStatus, setEditStatus] = useState('')

  // 合并章节弹窗
  const [mergeModalVisible, setMergeModalVisible] = useState(false)
  const [sourceChapter, setSourceChapter] = useState<Chapter | null>(null)
  const [targetChapterId, setTargetChapterId] = useState('')

  // 分割章节弹窗
  const [splitModalVisible, setSplitModalVisible] = useState(false)
  const [splittingChapter, setSplittingChapter] = useState<Chapter | null>(null)
  const [splitParagraphNumber, setSplitParagraphNumber] = useState('')

  // 搜索/筛选
  const [searchText, setSearchText] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('all')

  useEffect(() => {
    if (projectId && novelId) {
      fetchNovel(projectId, novelId)
      fetchChapters(projectId, novelId)
    }
  }, [projectId, novelId])

  const handlePreprocess = async () => {
    if (!projectId || !novelId) return
    try {
      const result: any = await preprocessNovel(projectId, novelId)
      if (result) {
        setPreprocessingResult(result)
        if (result.paragraphs) {
          setParagraphs(result.paragraphs)
        }
        message.success('预处理完成')
      }
    } catch {
      message.error('预处理失败')
    }
  }

  // 编辑章节
  const handleEditChapter = (chapter: Chapter) => {
    setEditingChapter(chapter)
    setEditTitle(chapter.title || '')
    setEditStatus(chapter.status)
    setEditModalVisible(true)
  }

  const handleSaveEdit = async () => {
    if (!projectId || !novelId || !editingChapter) return
    try {
      await updateChapter(projectId, novelId, editingChapter.id, {
        title: editTitle,
        status: editStatus,
      })
      message.success('章节已更新')
      setEditModalVisible(false)
      // 刷新小说详情
      fetchNovel(projectId, novelId)
    } catch {
      message.error('更新失败')
    }
  }

  // 合并章节
  const handleMergeClick = (chapter: Chapter) => {
    setSourceChapter(chapter)
    setTargetChapterId('')
    setMergeModalVisible(true)
  }

  const handleMergeConfirm = async () => {
    if (!projectId || !novelId || !sourceChapter || !targetChapterId) return
    if (targetChapterId === sourceChapter.id) {
      message.warning('不能合并到自身')
      return
    }
    try {
      await mergeChapters(projectId, novelId, sourceChapter.id, targetChapterId)
      message.success('章节合并成功')
      setMergeModalVisible(false)
      fetchNovel(projectId, novelId)
    } catch {
      message.error('合并失败')
    }
  }

  // 分割章节
  const handleSplitClick = (chapter: Chapter) => {
    setSplittingChapter(chapter)
    setSplitParagraphNumber('')
    setSplitModalVisible(true)
  }

  const handleSplitConfirm = async () => {
    if (!projectId || !novelId || !splittingChapter || !splitParagraphNumber) {
      message.warning('请输入分割点段落编号')
      return
    }
    try {
      await splitChapter(projectId, novelId, splittingChapter.id, splitParagraphNumber)
      message.success('章节分割成功')
      setSplitModalVisible(false)
      fetchNovel(projectId, novelId)
    } catch {
      message.error('分割失败')
    }
  }

  // 打开编辑器
  const handleOpenEditor = (chapterId?: string) => {
    // 如果传了 chapterId，仍然跳转到独立编辑器页（用于编辑具体章节）
    if (chapterId) {
      const basePath = `/projects/${projectId}/novels/${novelId}/editor`
      navigate(`${basePath}?chapterId=${chapterId}`)
      return
    }
    // 否则打开模态框编辑器，显示小说原始文本
    setEditorText(currentNovel?.raw_text || currentNovel?.cleaned_text || '')
    setEditorOpen(true)
    setShowTip(true)
    // 3 秒后自动关闭温馨提示
    if (tipTimer.current) clearTimeout(tipTimer.current)
    tipTimer.current = setTimeout(() => setShowTip(false), 3000)
  }

  // 保存编辑器文本
  const handleSaveEditorText = async () => {
    if (!projectId || !novelId) return
    try {
      const result = await updateNovelText(projectId, novelId, editorText)
      if (result) {
        message.success('文本已保存')
        setEditorOpen(false)
        fetchNovel(projectId, novelId)
        fetchChapters(projectId, novelId)
      }
    } catch {
      message.error('保存失败')
    }
  }

  // 关闭编辑器
  const handleCloseEditor = () => {
    if (tipTimer.current) clearTimeout(tipTimer.current)
    setEditorOpen(false)
    setShowTip(false)
  }

  // 获取状态标签
  const renderStatusTag = (status: string) => {
    const info = STATUS_MAP[status] || { color: 'default', text: status }
    return <Tag color={info.color}>{info.text}</Tag>
  }

  // 渲染段落统计
  const renderStats = (stats?: ParagraphStats) => {
    if (!stats) return null
    return (
      <Space size={4} wrap>
        {Object.entries(stats).map(([key, count]) => {
          if (count === 0) return null
          return (
            <Tag key={key} color={STATS_COLOR_MAP[key]} style={{ fontSize: 11 }}>
              {STATS_LABEL_MAP[key]}: {count}
            </Tag>
          )
        })}
      </Space>
    )
  }

  // 过滤章节
  const filteredChapters = chapters.filter((ch) => {
    const matchSearch =
      !searchText ||
      (ch.title || '').toLowerCase().includes(searchText.toLowerCase()) ||
      `第${ch.chapter_number}章`.includes(searchText)
    const matchStatus = statusFilter === 'all' || ch.status === statusFilter
    return matchSearch && matchStatus
  })

  const chapterColumns = [
    {
      title: '#',
      dataIndex: 'chapter_number',
      key: 'chapter_number',
      width: 60,
      render: (num: number) => (
        <Text style={{ fontFamily: 'monospace', fontSize: 12 }}>{num}</Text>
      ),
    },
    {
      title: '章节标题',
      dataIndex: 'title',
      key: 'title',
      render: (title?: string, record?: Chapter) => (
        <Space>
          <span
            style={{ cursor: 'pointer', color: '#1677ff' }}
            onClick={() => handleOpenEditor(record?.id)}
          >
            {title || `第 ${record?.chapter_number} 章`}
          </span>
          {record?.paragraph_count !== undefined && (
            <Text type="secondary" style={{ fontSize: 12 }}>
              ({record.paragraph_count}段)
            </Text>
          )}
        </Space>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: string) => renderStatusTag(status),
    },
    {
      title: '段落统计',
      key: 'stats',
      width: 240,
      render: (_: any, record: Chapter) => renderStats(record.paragraph_stats),
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 160,
      render: (date: string) => formatDate(date),
    },
    {
      title: '操作',
      key: 'actions',
      width: 180,
      render: (_: any, record: Chapter) => (
        <Space>
          <Tooltip title="编辑章节">
            <Button
              type="text"
              size="small"
              icon={<EditOutlined />}
              onClick={() => handleEditChapter(record)}
            />
          </Tooltip>
          <Tooltip title="合并章节">
            <Button
              type="text"
              size="small"
              icon={<MergeCellsOutlined />}
              onClick={() => handleMergeClick(record)}
            />
          </Tooltip>
          <Tooltip title="分割章节">
            <Button
              type="text"
              size="small"
              icon={<SplitCellsOutlined />}
              onClick={() => handleSplitClick(record)}
            />
          </Tooltip>
          <Tooltip title="编辑内容">
            <Button
              type="link"
              size="small"
              icon={<EyeOutlined />}
              onClick={() => handleOpenEditor(record.id)}
            >
              编辑
            </Button>
          </Tooltip>
        </Space>
      ),
    },
  ]

  if (loading && !currentNovel) {
    return <Loading tip="加载小说详情..." />
  }

  return (
    <div>
      <Space style={{ marginBottom: 16 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(-1)}>
          返回
        </Button>
      </Space>

      {/* 小说基本信息 */}
      <Card>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <Title level={4} style={{ margin: 0 }}>
              {currentNovel?.title || '小说详情'}
            </Title>
            {currentNovel?.author && (
              <Text type="secondary" style={{ marginTop: 4, display: 'block' }}>
                作者：{currentNovel.author}
              </Text>
            )}
          </div>
          <Space>
            <Button type="primary" onClick={() => handleOpenEditor()}>
              打开编辑器
            </Button>
            <Button
              icon={<ThunderboltOutlined />}
              loading={preprocessing}
              onClick={handlePreprocess}
            >
              预处理
            </Button>
          </Space>
        </div>

        <Divider />

        <Descriptions column={3} bordered size="small">
          <Descriptions.Item label="字数">
            {formatWordCount(currentNovel?.word_count || 0)}
          </Descriptions.Item>
          <Descriptions.Item label="格式">
            <Tag>{currentNovel?.format || '-'}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="创建时间">
            {currentNovel ? formatDate(currentNovel.created_at) : '-'}
          </Descriptions.Item>
          <Descriptions.Item label="章节数">
            {chapters.length}
          </Descriptions.Item>
          <Descriptions.Item label="总段落数">
            {chapters.reduce((sum, ch) => sum + (ch.paragraph_count || 0), 0)}
          </Descriptions.Item>
          <Descriptions.Item label="更新时间">
            {currentNovel ? formatDate(currentNovel.updated_at) : '-'}
          </Descriptions.Item>
        </Descriptions>
      </Card>

      {/* 预处理结果 */}
      {preprocessingResult && paragraphs.length > 0 && (
        <Card title="预处理结果" style={{ marginTop: 16 }}>
          <div style={{ maxHeight: 300, overflow: 'auto' }}>
            {paragraphs.map((para: any, idx: number) => (
              <div
                key={idx}
                style={{
                  display: 'flex',
                  gap: 12,
                  padding: '8px 0',
                  borderBottom: '1px solid #f5f5f5',
                }}
              >
                <Text
                  type="secondary"
                  style={{
                    minWidth: 40,
                    textAlign: 'right',
                    fontFamily: 'monospace',
                    fontSize: 12,
                    lineHeight: '22px',
                    userSelect: 'none',
                  }}
                >
                  {para.id || idx + 1}
                </Text>
                <div style={{ flex: 1 }}>
                  <Text
                    strong={para.is_chapter_title}
                    style={{
                      fontSize: para.is_chapter_title ? 16 : undefined,
                      whiteSpace: 'pre-wrap',
                    }}
                  >
                    {para.text}
                  </Text>
                  {para.annotation && (
                    <div style={{ marginTop: 4 }}>
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        标注：{para.annotation}
                      </Text>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* 章节管理 */}
      <Card
        title="章节管理"
        style={{ marginTop: 16 }}
        extra={
          <Space>
            <Input
              size="small"
              placeholder="搜索章节..."
              prefix={<SearchOutlined />}
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
              style={{ width: 160 }}
              allowClear
            />
            <Select
              size="small"
              value={statusFilter}
              onChange={setStatusFilter}
              style={{ width: 110 }}
              options={[
                { value: 'all', label: '全部状态' },
                { value: 'draft', label: '草稿' },
                { value: 'pending', label: '待处理' },
                { value: 'confirmed', label: '已确认' },
                { value: 'processing', label: '处理中' },
                { value: 'completed', label: '已完成' },
              ]}
            />
            <Button
              size="small"
              icon={<ReloadOutlined />}
              onClick={() => projectId && novelId && fetchChapters(projectId, novelId)}
            >
              刷新
            </Button>
          </Space>
        }
      >
        {filteredChapters.length === 0 ? (
          <EmptyState description={searchText ? '未找到匹配的章节' : '暂无章节数据'} />
        ) : (
          <Table
            dataSource={filteredChapters}
            columns={chapterColumns}
            rowKey="id"
            pagination={{ pageSize: 10, showSizeChanger: true, pageSizeOptions: ['10', '20', '50'] }}
            size="small"
          />
        )}
      </Card>

      {/* 编辑章节弹窗 */}
      <Modal
        title="编辑章节"
        open={editModalVisible}
        onOk={handleSaveEdit}
        onCancel={() => setEditModalVisible(false)}
        okText="保存"
        cancelText="取消"
      >
        <div style={{ marginBottom: 16 }}>
          <Text style={{ display: 'block', marginBottom: 4 }}>章节标题</Text>
          <Input
            value={editTitle}
            onChange={(e) => setEditTitle(e.target.value)}
            placeholder="输入章节标题"
          />
        </div>
        <div>
          <Text style={{ display: 'block', marginBottom: 4 }}>状态</Text>
          <Select
            value={editStatus}
            onChange={setEditStatus}
            style={{ width: '100%' }}
            options={[
              { value: 'draft', label: '草稿' },
              { value: 'pending', label: '待处理' },
              { value: 'confirmed', label: '已确认' },
              { value: 'processing', label: '处理中' },
              { value: 'completed', label: '已完成' },
            ]}
          />
        </div>
      </Modal>

      {/* 合并章节弹窗 */}
      <Modal
        title={`合并章节 - ${sourceChapter?.title || `第 ${sourceChapter?.chapter_number} 章`}`}
        open={mergeModalVisible}
        onOk={handleMergeConfirm}
        onCancel={() => setMergeModalVisible(false)}
        okText="合并"
        cancelText="取消"
      >
        <div style={{ marginBottom: 8 }}>
          <Text>将当前章节合并到：</Text>
        </div>
        <Select
          value={targetChapterId}
          onChange={setTargetChapterId}
          style={{ width: '100%' }}
          placeholder="选择目标章节"
          options={chapters
            .filter((ch) => ch.id !== sourceChapter?.id)
            .map((ch) => ({
              value: ch.id,
              label: `${ch.title || `第 ${ch.chapter_number} 章`} (${ch.paragraph_count || 0}段)`,
            }))}
        />
        <div style={{ marginTop: 8 }}>
          <Text type="warning" style={{ fontSize: 12 }}>
            合并后源章节将被删除，其内容追加到目标章节末尾。
          </Text>
        </div>
      </Modal>

      {/* 分割章节弹窗 */}
      <Modal
        title={`分割章节 - ${splittingChapter?.title || `第 ${splittingChapter?.chapter_number} 章`}`}
        open={splitModalVisible}
        onOk={handleSplitConfirm}
        onCancel={() => setSplitModalVisible(false)}
        okText="分割"
        cancelText="取消"
      >
        <div style={{ marginBottom: 8 }}>
          <Text>在此段落编号之后分割（该段落及之后的内容将移至新章节）：</Text>
        </div>
        <Input
          value={splitParagraphNumber}
          onChange={(e) => setSplitParagraphNumber(e.target.value)}
          placeholder="例如: 0003"
        />
        <div style={{ marginTop: 8 }}>
          <Text type="secondary" style={{ fontSize: 12 }}>
            输入段落编号（如 0003），该段落之后的所有内容将分割到新章节。
          </Text>
        </div>
      </Modal>

      {/* 小说文本编辑器模态框 */}
      <Modal
        title="小说文本编辑器"
        open={editorOpen}
        onCancel={handleCloseEditor}
        width={800}
        footer={
          <Space>
            <Button onClick={handleCloseEditor} icon={<CloseOutlined />}>
              关闭
            </Button>
            <Button type="primary" onClick={handleSaveEditorText} icon={<SaveOutlined />} loading={preprocessing}>
              保存
            </Button>
          </Space>
        }
        destroyOnClose
      >
        {showTip && (
          <Alert
            message="温馨提示：请手动删除无意义的章节标题（如'第一章'、'序言'等只作为章节标记的文字），确保正文内容干净连续。"
            type="info"
            showIcon
            closable
            style={{ marginBottom: 16 }}
          />
        )}
        <Input.TextArea
          value={editorText}
          onChange={(e) => setEditorText(e.target.value)}
          rows={20}
          style={{ fontFamily: 'monospace', fontSize: 14 }}
          placeholder="粘贴或编辑小说文本..."
        />
      </Modal>
    </div>
  )
}
