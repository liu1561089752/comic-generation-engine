import { useState } from 'react'
import { Card, Table, Tag, Space, Button, Switch, Typography, Modal, Descriptions, message, Empty, Tooltip } from 'antd'
import {
  ApiOutlined,
  InfoCircleOutlined,
  ReloadOutlined,
} from '@ant-design/icons'
import { formatDate } from '../../utils/format'

const { Title } = Typography

// ---------- Mock Plugin Data ----------

interface Plugin {
  id: string
  name: string
  version: string
  description: string
  plugin_type: string
  enabled: boolean
  config_schema?: Record<string, any>
  created_at: string
}

const mockPlugins: Plugin[] = [
  {
    id: '1',
    name: 'Stable Diffusion 增强器',
    version: '1.2.0',
    description: '增强 Stable Diffusion 出图质量，支持 ControlNet、LoRA 等高级功能',
    plugin_type: '生图',
    enabled: true,
    created_at: '2026-06-01T00:00:00Z',
  },
  {
    id: '2',
    name: '翻译引擎',
    version: '2.0.1',
    description: '多语言翻译支持，可将中文Prompt自动翻译为英文',
    plugin_type: '工具',
    enabled: true,
    created_at: '2026-05-15T00:00:00Z',
  },
  {
    id: '3',
    name: '漫画风格迁移',
    version: '1.0.0',
    description: '将真实照片转换为漫画风格，支持多种漫画风格',
    plugin_type: '生图',
    enabled: false,
    created_at: '2026-04-20T00:00:00Z',
  },
  {
    id: '4',
    name: '批量导出器',
    version: '1.1.0',
    description: '批量导出漫画为 PDF / CBZ / 图片序列格式',
    plugin_type: '导出',
    enabled: true,
    created_at: '2026-03-10T00:00:00Z',
  },
  {
    id: '5',
    name: 'AI 对话助手',
    version: '0.9.0',
    description: '在编辑器内集成 AI 对话助手，辅助创作',
    plugin_type: '工具',
    enabled: false,
    created_at: '2026-02-01T00:00:00Z',
  },
]

const PLUGIN_TYPE_COLORS: Record<string, string> = {
  '生图': 'blue',
  '工具': 'green',
  '导出': 'purple',
  '分析': 'orange',
}

// ---------- Component ----------

export default function PluginCenter() {
  const [plugins, setPlugins] = useState<Plugin[]>(mockPlugins)
  const [detailOpen, setDetailOpen] = useState(false)
  const [selectedPlugin, setSelectedPlugin] = useState<Plugin | null>(null)

  const handleToggle = (id: string, enabled: boolean) => {
    setPlugins(prev => prev.map(p => p.id === id ? { ...p, enabled } : p))
    message.success(`插件已${enabled ? '启用' : '禁用'}`)
  }

  const showDetail = (plugin: Plugin) => {
    setSelectedPlugin(plugin)
    setDetailOpen(true)
  }

  const columns = [
    {
      title: '插件名称', dataIndex: 'name', key: 'name',
      render: (name: string, record: Plugin) => (
        <Space>
          <ApiOutlined style={{ color: record.enabled ? '#1677ff' : '#999' }} />
          <Button type="link" style={{ padding: 0 }} onClick={() => showDetail(record)}>
            {name}
          </Button>
        </Space>
      ),
    },
    { title: '版本', dataIndex: 'version', key: 'version' },
    { title: '描述', dataIndex: 'description', key: 'description', ellipsis: true },
    {
      title: '类型', dataIndex: 'plugin_type', key: 'plugin_type',
      render: (type: string) => <Tag color={PLUGIN_TYPE_COLORS[type] || 'default'}>{type}</Tag>,
    },
    {
      title: '状态', key: 'status',
      render: (_: any, record: Plugin) => (
        <Tag color={record.enabled ? 'success' : 'default'}>
          {record.enabled ? '已启用' : '已禁用'}
        </Tag>
      ),
    },
    {
      title: '操作', key: 'action',
      render: (_: any, record: Plugin) => (
        <Space>
          <Switch
            checked={record.enabled}
            onChange={(checked) => handleToggle(record.id, checked)}
            checkedChildren="启用"
            unCheckedChildren="禁用"
            size="small"
          />
          <Tooltip title="详情">
            <Button type="link" size="small" icon={<InfoCircleOutlined />} onClick={() => showDetail(record)} />
          </Tooltip>
        </Space>
      ),
    },
  ]

  return (
    <div>
      <Title level={4} style={{ marginTop: 0, marginBottom: 24 }}>
        插件中心
      </Title>

      <Card
        extra={
          <Space>
            <Button icon={<ReloadOutlined />} onClick={() => setPlugins([...mockPlugins])}>
              刷新
            </Button>
          </Space>
        }
      >
        <Table
          dataSource={plugins}
          columns={columns}
          rowKey="id"
          pagination={false}
          locale={{ emptyText: <Empty description="暂无插件" /> }}
        />
      </Card>

      <Modal
        title={selectedPlugin?.name}
        open={detailOpen}
        onCancel={() => setDetailOpen(false)}
        footer={
          <Space>
            <Button onClick={() => setDetailOpen(false)}>关闭</Button>
          </Space>
        }
        width={560}
      >
        {selectedPlugin && (
          <Descriptions bordered size="small" column={1}>
            <Descriptions.Item label="名称">{selectedPlugin.name}</Descriptions.Item>
            <Descriptions.Item label="版本">{selectedPlugin.version}</Descriptions.Item>
            <Descriptions.Item label="类型">
              <Tag color={PLUGIN_TYPE_COLORS[selectedPlugin.plugin_type]}>{selectedPlugin.plugin_type}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="描述">{selectedPlugin.description}</Descriptions.Item>
            <Descriptions.Item label="状态">
              <Tag color={selectedPlugin.enabled ? 'success' : 'default'}>
                {selectedPlugin.enabled ? '已启用' : '已禁用'}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="创建时间">{formatDate(selectedPlugin.created_at)}</Descriptions.Item>
          </Descriptions>
        )}
      </Modal>
    </div>
  )
}
