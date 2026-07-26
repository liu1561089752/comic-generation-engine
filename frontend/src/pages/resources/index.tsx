import { useState, useEffect } from 'react'
import { Card, Tabs, Table, Tag, Space, Input, Button, Rate, Row, Col, Typography, Empty, Tooltip } from 'antd'
import {
  PictureOutlined,
  ThunderboltOutlined,
  AppstoreOutlined,
  FileOutlined,
  SearchOutlined,
  StarOutlined,
  CopyOutlined,
  DownloadOutlined,
} from '@ant-design/icons'
import { formatDate } from '../../utils/format'

const { Text, Title } = Typography

// ---------- Mock Data ----------

const mockImages = [
  { id: '1', name: 'example_001.png', url: '', size: '2.3 MB', width: 1080, height: 1440, format: 'PNG', created_at: '2026-06-28T10:00:00Z', tags: ['角色', '女性'] },
  { id: '2', name: 'scene_bg_01.png', url: '', size: '3.1 MB', width: 1920, height: 1080, format: 'PNG', created_at: '2026-06-27T15:30:00Z', tags: ['背景', '城市'] },
  { id: '3', name: 'character_sprite.png', url: '', size: '1.8 MB', width: 512, height: 1024, format: 'PNG', created_at: '2026-06-26T09:15:00Z', tags: ['角色', '男性'] },
]

const mockPrompts = [
  { id: '1', content: 'A mysterious young woman with flowing silver hair, standing in a moonlit garden, intricate details, ethereal atmosphere, digital painting', rating: 4.5, used_count: 12, category: '角色', created_at: '2026-06-25T08:00:00Z' },
  { id: '2', content: 'Cyberpunk city street at night, neon lights reflecting on wet pavement, futuristic architecture, volumetric lighting, 8k', rating: 4.8, used_count: 25, category: '场景', created_at: '2026-06-20T14:00:00Z' },
  { id: '3', content: 'Ancient Chinese palace interior, ornate pillars, red and gold decorations, dragon motifs, warm candlelight, majestic', rating: 4.2, used_count: 8, category: '场景', created_at: '2026-06-15T11:00:00Z' },
]

const mockTemplates = [
  { id: '1', name: '少年漫画标准', type: '分镜', category: '少年', panel_count: 6, used_count: 45, created_at: '2026-06-01T00:00:00Z' },
  { id: '2', name: '少女漫画浪漫', type: '分镜', category: '少女', panel_count: 8, used_count: 32, created_at: '2026-05-20T00:00:00Z' },
  { id: '3', name: '四格搞笑', type: '版式', category: '搞笑', panel_count: 4, used_count: 78, created_at: '2026-05-10T00:00:00Z' },
]

const mockMaterials = [
  { id: '1', name: '网点纸-樱花', type: '纹理', category: '背景', size: '512 KB', format: 'PNG', created_at: '2026-06-10T00:00:00Z' },
  { id: '2', name: '速度线-动作', type: '特效', category: '动作', size: '256 KB', format: 'PNG', created_at: '2026-06-08T00:00:00Z' },
  { id: '3', name: '对话框-气泡', type: 'UI', category: '对话框', size: '128 KB', format: 'SVG', created_at: '2026-06-05T00:00:00Z' },
]

// ---------- Resource Page ----------

export default function ResourceCenter() {
  return (
    <div>
      <Title level={4} style={{ marginTop: 0, marginBottom: 24 }}>
        资源中心
      </Title>

      <Tabs
        defaultActiveKey="images"
        items={[
          {
            key: 'images',
            label: <span><PictureOutlined /> 图片资源库</span>,
            children: <ImageLibrary />,
          },
          {
            key: 'prompts',
            label: <span><ThunderboltOutlined /> Prompt 资源库</span>,
            children: <PromptLibrary />,
          },
          {
            key: 'templates',
            label: <span><AppstoreOutlined /> 模板资源库</span>,
            children: <TemplateLibrary />,
          },
          {
            key: 'materials',
            label: <span><FileOutlined /> 素材资源库</span>,
            children: <MaterialLibrary />,
          },
        ]}
      />
    </div>
  )
}

// ---------- Image Library ----------

function ImageLibrary() {
  const [search, setSearch] = useState('')
  const [data, setData] = useState(mockImages)

  useEffect(() => {
    if (search) {
      setData(mockImages.filter(i =>
        i.name.toLowerCase().includes(search.toLowerCase()) ||
        i.tags.some(t => t.includes(search))
      ))
    } else {
      setData(mockImages)
    }
  }, [search])

  const columns = [
    { title: '文件名', dataIndex: 'name', key: 'name', render: (name: string) => <Text code>{name}</Text> },
    { title: '尺寸', key: 'dimensions', render: (_: any, r: any) => `${r.width}×${r.height}` },
    { title: '大小', dataIndex: 'size', key: 'size' },
    { title: '格式', dataIndex: 'format', key: 'format' },
    { title: '标签', dataIndex: 'tags', key: 'tags', render: (tags: string[]) => tags.map(t => <Tag key={t}>{t}</Tag>) },
    { title: '创建时间', dataIndex: 'created_at', key: 'created_at', render: (t: string) => formatDate(t) },
    {
      title: '操作', key: 'action', render: () => (
        <Space>
          <Tooltip title="预览"><Button type="link" size="small" icon={<PictureOutlined />} /></Tooltip>
          <Tooltip title="下载"><Button type="link" size="small" icon={<DownloadOutlined />} /></Tooltip>
        </Space>
      ),
    },
  ]

  return (
    <Card extra={
      <Input.Search
        placeholder="搜索图片..."
        prefix={<SearchOutlined />}
        style={{ width: 250 }}
        value={search}
        onChange={e => setSearch(e.target.value)}
        allowClear
      />
    }>
      <Table dataSource={data} columns={columns} rowKey="id" pagination={{ pageSize: 10 }} size="small" locale={{ emptyText: <Empty description="暂无图片资源" /> }} />
    </Card>
  )
}

// ---------- Prompt Library ----------

function PromptLibrary() {
  const [search, setSearch] = useState('')
  const [data, setData] = useState(mockPrompts)

  useEffect(() => {
    if (search) {
      setData(mockPrompts.filter(p =>
        p.content.toLowerCase().includes(search.toLowerCase()) ||
        p.category.includes(search)
      ))
    } else {
      setData(mockPrompts)
    }
  }, [search])

  const columns = [
    {
      title: 'Prompt', dataIndex: 'content', key: 'content', width: 400,
      render: (text: string) => (
        <Text ellipsis={{ tooltip: text }} style={{ maxWidth: 380, display: 'block' }}>
          {text}
        </Text>
      ),
    },
    { title: '分类', dataIndex: 'category', key: 'category', render: (c: string) => <Tag>{c}</Tag> },
    { title: '评分', dataIndex: 'rating', key: 'rating', render: (r: number) => <Rate disabled allowHalf value={r} style={{ fontSize: 14 }} /> },
    { title: '使用次数', dataIndex: 'used_count', key: 'used_count', render: (n: number) => <Text type="secondary">{n} 次</Text> },
    { title: '创建时间', dataIndex: 'created_at', key: 'created_at', render: (t: string) => formatDate(t) },
    {
      title: '操作', key: 'action', render: (_: any, record: any) => (
        <Space>
          <Tooltip title="复制">
            <Button type="link" size="small" icon={<CopyOutlined />} onClick={() => navigator.clipboard.writeText(record.content)} />
          </Tooltip>
          <Tooltip title="收藏">
            <Button type="link" size="small" icon={<StarOutlined />} />
          </Tooltip>
        </Space>
      ),
    },
  ]

  return (
    <Card extra={
      <Input.Search
        placeholder="搜索 Prompt..."
        prefix={<SearchOutlined />}
        style={{ width: 250 }}
        value={search}
        onChange={e => setSearch(e.target.value)}
        allowClear
      />
    }>
      <Table dataSource={data} columns={columns} rowKey="id" pagination={{ pageSize: 10 }} size="small" locale={{ emptyText: <Empty description="暂无 Prompt 资源" /> }} />
    </Card>
  )
}

// ---------- Template Library ----------

function TemplateLibrary() {
  const columns = [
    { title: '名称', dataIndex: 'name', key: 'name' },
    { title: '类型', dataIndex: 'type', key: 'type', render: (t: string) => <Tag color="blue">{t}</Tag> },
    { title: '分类', dataIndex: 'category', key: 'category', render: (c: string) => <Tag color="green">{c}</Tag> },
    { title: '面板数', dataIndex: 'panel_count', key: 'panel_count' },
    { title: '使用次数', dataIndex: 'used_count', key: 'used_count', render: (n: number) => <Text type="secondary">{n} 次</Text> },
    { title: '创建时间', dataIndex: 'created_at', key: 'created_at', render: (t: string) => formatDate(t) },
    {
      title: '操作', key: 'action', render: () => (
        <Space>
          <Button type="link" size="small">预览</Button>
          <Button type="link" size="small">使用</Button>
        </Space>
      ),
    },
  ]

  return (
    <Card>
      <Row gutter={16} style={{ marginBottom: 16 }}>
        {mockTemplates.map(t => (
          <Col key={t.id} xs={24} sm={12} md={8}>
            <Card
              size="small"
              hoverable
              style={{ marginBottom: 16, cursor: 'pointer' }}
              actions={[
                <Button type="link" size="small" key="preview">预览</Button>,
                <Button type="link" size="small" key="use">使用</Button>,
              ]}
            >
              <div style={{ fontWeight: 600, marginBottom: 8 }}>{t.name}</div>
              <div style={{ fontSize: 12, color: '#666' }}>
                <div>类型：{t.type} · {t.category}</div>
                <div>{t.panel_count} 个面板 · 使用 {t.used_count} 次</div>
              </div>
            </Card>
          </Col>
        ))}
      </Row>
      <Table dataSource={mockTemplates} columns={columns} rowKey="id" pagination={false} size="small" locale={{ emptyText: <Empty description="暂无模板资源" /> }} />
    </Card>
  )
}

// ---------- Material Library ----------

function MaterialLibrary() {
  const columns = [
    { title: '名称', dataIndex: 'name', key: 'name' },
    { title: '类型', dataIndex: 'type', key: 'type', render: (t: string) => <Tag>{t}</Tag> },
    { title: '分类', dataIndex: 'category', key: 'category', render: (c: string) => <Tag color="purple">{c}</Tag> },
    { title: '大小', dataIndex: 'size', key: 'size' },
    { title: '格式', dataIndex: 'format', key: 'format' },
    { title: '创建时间', dataIndex: 'created_at', key: 'created_at', render: (t: string) => formatDate(t) },
    {
      title: '操作', key: 'action', render: () => (
        <Space>
          <Tooltip title="预览"><Button type="link" size="small" icon={<PictureOutlined />} /></Tooltip>
          <Tooltip title="下载"><Button type="link" size="small" icon={<DownloadOutlined />} /></Tooltip>
        </Space>
      ),
    },
  ]

  return (
    <Card>
      <Table dataSource={mockMaterials} columns={columns} rowKey="id" pagination={{ pageSize: 10 }} size="small" locale={{ emptyText: <Empty description="暂无素材资源" /> }} />
    </Card>
  )
}
