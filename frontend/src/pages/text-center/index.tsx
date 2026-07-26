import { useEffect, useState } from 'react'
import {
  Card, Row, Col, Button, Modal, Form, Input, Select, message, Space, Tag,
  Table, Slider, Tooltip, Popconfirm,
} from 'antd'
import {
  PlusOutlined, EditOutlined, DeleteOutlined, SortAscendingOutlined,
  SoundOutlined, MessageOutlined, BookOutlined, BulbOutlined,
} from '@ant-design/icons'
import { useParams } from 'react-router-dom'
import apiClient from '../../api/client'
import EmptyState from '../../components/common/EmptyState'
import Loading from '../../components/common/Loading'

const { TextArea } = Input

const BUBBLE_TYPE_OPTIONS = [
  { label: '对话', value: 'dialogue', icon: <MessageOutlined /> },
  { label: '旁白', value: 'narration', icon: <BookOutlined /> },
  { label: '内心独白', value: 'thinking', icon: <BulbOutlined /> },
  { label: '拟声词', value: 'sfx', icon: <SoundOutlined /> },
]

const FONT_OPTIONS = [
  { label: '默认', value: 'default' },
  { label: '黑体', value: 'simhei' },
  { label: '宋体', value: 'simsun' },
  { label: '楷体', value: 'kai' },
  { label: '圆体', value: 'round' },
  { label: '手写体', value: 'handwrite' },
  { label: '特效', value: 'effect' },
]

const STYLE_OPTIONS = [
  { label: '椭圆气泡', value: 'oval' },
  { label: '矩形气泡', value: 'rect' },
  { label: '云朵气泡', value: 'cloud' },
  { label: '锯齿气泡', value: 'jagged' },
  { label: '无框文字', value: 'no-border' },
  { label: '爆炸框', value: 'explosion' },
  { label: '旁白框', value: 'narration-box' },
]

interface Bubble {
  id: string
  panel_id: string
  bubble_type: string
  text: string
  speaker: string | null
  speaker_id: string | null
  order: number
  style: string | null
  font: string | null
  font_size: number
  created_at: string
  updated_at: string
}

export default function TextCenter() {
  const { id: projectId } = useParams<{ id: string }>()
  const [bubbles, setBubbles] = useState<Bubble[]>([])
  const [loading, setLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [editingBubble, setEditingBubble] = useState<Bubble | null>(null)
  const [form] = Form.useForm()
  const [activeType, setActiveType] = useState<string>('')
  const [saveLoading, setSaveLoading] = useState(false)

  const fetchBubbles = async () => {
    if (!projectId) return
    setLoading(true)
    try {
      const res = await apiClient.get(`/projects/${projectId}/panels?limit=100`)
      const panels = res.data?.items || []
      // 收集所有 panel 的气泡
      const allBubbles: Bubble[] = []
      for (const panel of panels.slice(0, 20)) { // 限制 panel 数量
        try {
          const bubbleRes = await apiClient.get(`/projects/${projectId}/panels/${panel.id}/bubbles`)
          allBubbles.push(...(bubbleRes.data?.items || []))
        } catch {
          // 跳过获取失败的 panel
        }
      }
      allBubbles.sort((a, b) => a.order - b.order)
      setBubbles(allBubbles)
    } catch {
      message.error('加载失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchBubbles()
  }, [projectId])

  const filteredBubbles = activeType
    ? bubbles.filter((b) => b.bubble_type === activeType)
    : bubbles

  const handleCreate = async (values: any) => {
    if (!projectId) return
    setSaveLoading(true)
    try {
      // 使用第一个 panel 作为示例
      const res = await apiClient.get(`/projects/${projectId}/panels?limit=1`)
      const panels = res.data?.items || []
      if (panels.length === 0) {
        message.warning('请先创建分镜')
        return
      }
      await apiClient.post(`/projects/${projectId}/panels/${panels[0].id}/bubbles`, values)
      message.success('气泡创建成功')
      setModalOpen(false)
      form.resetFields()
      fetchBubbles()
    } catch {
      message.error('创建失败')
    } finally {
      setSaveLoading(false)
    }
  }

  const handleUpdate = async (values: any) => {
    if (!projectId || !editingBubble) return
    setSaveLoading(true)
    try {
      await apiClient.put(
        `/projects/${projectId}/panels/${editingBubble.panel_id}/bubbles/${editingBubble.id}`,
        values,
      )
      message.success('更新成功')
      setModalOpen(false)
      setEditingBubble(null)
      form.resetFields()
      fetchBubbles()
    } catch {
      message.error('更新失败')
    } finally {
      setSaveLoading(false)
    }
  }

  const handleDelete = async (bubble: Bubble) => {
    if (!projectId) return
    try {
      await apiClient.delete(
        `/projects/${projectId}/panels/${bubble.panel_id}/bubbles/${bubble.id}`,
      )
      message.success('删除成功')
      fetchBubbles()
    } catch {
      message.error('删除失败')
    }
  }

  const openEditModal = (bubble: Bubble) => {
    setEditingBubble(bubble)
    form.setFieldsValue(bubble)
    setModalOpen(true)
  }

  const openCreateModal = () => {
    setEditingBubble(null)
    form.resetFields()
    setModalOpen(true)
  }

  const getTypeTag = (type: string) => {
    const config: Record<string, { color: string; label: string }> = {
      dialogue: { color: 'blue', label: '对话' },
      narration: { color: 'green', label: '旁白' },
      thinking: { color: 'purple', label: '内心独白' },
      sfx: { color: 'orange', label: '拟声词' },
    }
    const c = config[type] || { color: 'default', label: type }
    return <Tag color={c.color}>{c.label}</Tag>
  }

  const typeCounts = {
    dialogue: bubbles.filter((b) => b.bubble_type === 'dialogue').length,
    narration: bubbles.filter((b) => b.bubble_type === 'narration').length,
    thinking: bubbles.filter((b) => b.bubble_type === 'thinking').length,
    sfx: bubbles.filter((b) => b.bubble_type === 'sfx').length,
  }

  const columns = [
    {
      title: '顺序',
      dataIndex: 'order',
      key: 'order',
      width: 60,
    },
    {
      title: '类型',
      dataIndex: 'bubble_type',
      key: 'bubble_type',
      width: 100,
      render: (type: string) => getTypeTag(type),
    },
    {
      title: '内容',
      dataIndex: 'text',
      key: 'text',
      ellipsis: true,
      render: (text: string) => (
        <Tooltip title={text}>
          <span>{text?.substring(0, 50)}{text?.length > 50 ? '...' : ''}</span>
        </Tooltip>
      ),
    },
    {
      title: '说话人',
      dataIndex: 'speaker',
      key: 'speaker',
      width: 120,
      render: (speaker: string | null) => speaker || <span style={{ color: '#999' }}>未指定</span>,
    },
    {
      title: '字体',
      dataIndex: 'font',
      key: 'font',
      width: 80,
      render: (font: string | null) => font || '默认',
    },
    {
      title: '字号',
      dataIndex: 'font_size',
      key: 'font_size',
      width: 60,
    },
    {
      title: '样式',
      dataIndex: 'style',
      key: 'style',
      width: 100,
      render: (style: string | null) => {
        const s = STYLE_OPTIONS.find((o) => o.value === style)
        return s ? s.label : (style || '默认')
      },
    },
    {
      title: '操作',
      key: 'actions',
      width: 120,
      render: (_: any, record: Bubble) => (
        <Space>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => openEditModal(record)}>
            编辑
          </Button>
          <Popconfirm title="确定删除?" onConfirm={() => handleDelete(record)}>
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  if (!projectId) {
    return <EmptyState description="请先选择一个项目" />
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <h2 style={{ margin: 0, fontSize: 20, fontWeight: 600 }}>漫画文本中心</h2>
        <Space>
          <Button icon={<SortAscendingOutlined />} onClick={() => message.info('拖拽排序功能待实现')}>
            排序管理
          </Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreateModal}>
            新建气泡
          </Button>
        </Space>
      </div>

      {/* 类型统计卡片 */}
      <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
        <Col span={6}>
          <Card size="small" hoverable onClick={() => setActiveType('')}
            style={{ border: activeType === '' ? '2px solid #1677ff' : undefined }}>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 24, fontWeight: 600 }}>{bubbles.length}</div>
              <div style={{ fontSize: 13, color: '#666' }}>全部文本</div>
            </div>
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small" hoverable onClick={() => setActiveType('dialogue')}
            style={{ border: activeType === 'dialogue' ? '2px solid #1677ff' : undefined }}>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 24, fontWeight: 600, color: '#1677ff' }}>{typeCounts.dialogue}</div>
              <div style={{ fontSize: 13, color: '#666' }}>对话</div>
            </div>
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small" hoverable onClick={() => setActiveType('narration')}
            style={{ border: activeType === 'narration' ? '2px solid #52c41a' : undefined }}>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 24, fontWeight: 600, color: '#52c41a' }}>{typeCounts.narration}</div>
              <div style={{ fontSize: 13, color: '#666' }}>旁白</div>
            </div>
          </Card>
        </Col>
        <Col span={4}>
          <Card size="small" hoverable onClick={() => setActiveType('thinking')}
            style={{ border: activeType === 'thinking' ? '2px solid #722ed1' : undefined }}>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 24, fontWeight: 600, color: '#722ed1' }}>{typeCounts.thinking}</div>
              <div style={{ fontSize: 13, color: '#666' }}>内心独白</div>
            </div>
          </Card>
        </Col>
        <Col span={4}>
          <Card size="small" hoverable onClick={() => setActiveType('sfx')}
            style={{ border: activeType === 'sfx' ? '2px solid #fa8c16' : undefined }}>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 24, fontWeight: 600, color: '#fa8c16' }}>{typeCounts.sfx}</div>
              <div style={{ fontSize: 13, color: '#666' }}>拟声词</div>
            </div>
          </Card>
        </Col>
      </Row>

      {/* 气泡列表 */}
      {loading ? (
        <Loading tip="加载文本列表..." />
      ) : filteredBubbles.length === 0 ? (
        <EmptyState
          description={activeType ? `暂无${BUBBLE_TYPE_OPTIONS.find(o => o.value === activeType)?.label}类型文本` : '暂无文本气泡'}
          actionText="新建气泡"
          onAction={openCreateModal}
        />
      ) : (
        <Table
          dataSource={filteredBubbles}
          columns={columns}
          rowKey="id"
          pagination={{ pageSize: 50, showSizeChanger: true, showTotal: (t) => `共 ${t} 条` }}
          size="small"
        />
      )}

      {/* 创建/编辑 Modal */}
      <Modal
        title={editingBubble ? '编辑气泡' : '新建气泡'}
        open={modalOpen}
        onCancel={() => { setModalOpen(false); setEditingBubble(null) }}
        footer={null}
        width={640}
        destroyOnClose
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={editingBubble ? handleUpdate : handleCreate}
          initialValues={{ bubble_type: 'dialogue', font_size: 16, order: 0 }}
        >
          <Form.Item name="bubble_type" label="气泡类型" rules={[{ required: true }]}>
            <Select options={BUBBLE_TYPE_OPTIONS} />
          </Form.Item>
          <Form.Item name="text" label="文本内容" rules={[{ required: true, message: '请输入文本内容' }]}>
            <TextArea rows={4} placeholder="输入气泡文本内容" />
          </Form.Item>
          <Space style={{ width: '100%' }} size="large">
            <Form.Item name="speaker" label="说话人">
              <Input placeholder="说话人名称" style={{ width: 200 }} />
            </Form.Item>
            <Form.Item name="order" label="阅读顺序">
              <Input type="number" style={{ width: 100 }} />
            </Form.Item>
          </Space>
          <Space style={{ width: '100%' }} size="large">
            <Form.Item name="font" label="字体">
              <Select allowClear style={{ width: 180 }} options={FONT_OPTIONS} placeholder="选择字体" />
            </Form.Item>
            <Form.Item name="font_size" label="字号">
              <Slider min={8} max={72} style={{ width: 180 }} />
            </Form.Item>
          </Space>
          <Form.Item name="style" label="气泡样式">
            <Select allowClear options={STYLE_OPTIONS} placeholder="选择气泡样式" />
          </Form.Item>
          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit" loading={saveLoading}>
                {editingBubble ? '保存' : '创建'}
              </Button>
              <Button onClick={() => { setModalOpen(false); setEditingBubble(null) }}>取消</Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
