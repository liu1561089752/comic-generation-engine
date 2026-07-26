import { Card, Select, Input, Button, Table, Tag, Space, Tooltip, Typography } from 'antd'
import { ReloadOutlined, ApiOutlined, PictureOutlined } from '@ant-design/icons'
import { formatDate } from '../../../utils/format'
import { LOG_TYPE_MAP, LOG_STATUS_COLOR, LOG_STATUS_LABEL } from './types'
import type { ModelLog } from './types'

const { Text } = Typography

interface Props {
  logs: ModelLog[]
  loading: boolean
  typeFilter: string
  statusFilter: string
  search: string
  onTypeFilterChange: (v: string) => void
  onStatusFilterChange: (v: string) => void
  onSearchChange: (v: string) => void
  onSearch: () => void
  onRefresh: () => void
}

export default function ModelLogsTab({
  logs,
  loading,
  typeFilter,
  statusFilter,
  search,
  onTypeFilterChange,
  onStatusFilterChange,
  onSearchChange,
  onSearch,
  onRefresh,
}: Props) {
  const logColumns = [
    {
      title: '时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 170,
      render: (t: string) => (t ? formatDate(t) : '-'),
    },
    {
      title: '模型',
      dataIndex: 'model_name',
      key: 'model_name',
      width: 140,
      render: (name: string, record: ModelLog) => (
        <Space>
          {record.model_type === 'llm' ? <ApiOutlined /> : <PictureOutlined />}
          <Text>{name || '-'}</Text>
        </Space>
      ),
    },
    {
      title: '调用类型',
      dataIndex: 'call_type',
      key: 'call_type',
      width: 120,
      render: (type: string) => LOG_TYPE_MAP[type] || type,
    },
    {
      title: '耗时',
      dataIndex: 'duration_ms',
      key: 'duration_ms',
      width: 100,
      sorter: (a: ModelLog, b: ModelLog) => a.duration_ms - b.duration_ms,
      render: (ms: number) => (ms != null ? `${(ms / 1000).toFixed(2)}s` : '-'),
    },
    {
      title: 'Token',
      dataIndex: 'total_tokens',
      key: 'total_tokens',
      width: 100,
      render: (tokens: number, record: ModelLog) => {
        if (tokens != null) return tokens
        if (record.prompt_tokens != null && record.completion_tokens != null) {
          return `${record.prompt_tokens}/${record.completion_tokens}`
        }
        return '-'
      },
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 90,
      render: (status: string) => (
        <Tag color={LOG_STATUS_COLOR[status] || 'default'}>
          {LOG_STATUS_LABEL[status] || status}
        </Tag>
      ),
    },
  ]

  return (
    <Card>
      <Space wrap style={{ marginBottom: 16 }}>
        <Select
          style={{ width: 130 }}
          placeholder="调用类型"
          allowClear
          value={typeFilter || undefined}
          onChange={(v) => onTypeFilterChange(v || '')}
          options={[
            { label: '全部类型', value: '' },
            ...Object.entries(LOG_TYPE_MAP).map(([value, label]) => ({
              label,
              value,
            })),
          ]}
        />
        <Select
          style={{ width: 100 }}
          placeholder="状态"
          allowClear
          value={statusFilter || undefined}
          onChange={(v) => onStatusFilterChange(v || '')}
          options={[
            { label: '全部状态', value: '' },
            { label: '成功', value: 'success' },
            { label: '失败', value: 'failed' },
            { label: '运行中', value: 'running' },
          ]}
        />
        <Input.Search
          placeholder="搜索模型名称..."
          style={{ width: 200 }}
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          onSearch={onSearch}
          allowClear
        />
        <Tooltip title="刷新日志">
          <Button icon={<ReloadOutlined />} onClick={onRefresh}>
            刷新
          </Button>
        </Tooltip>
      </Space>
      <Table
        dataSource={logs}
        columns={logColumns}
        rowKey="id"
        loading={loading}
        pagination={{
          showSizeChanger: true,
          showTotal: (t) => `共 ${t} 条`,
          pageSize: 15,
        }}
        locale={{ emptyText: '暂无调用日志' }}
        scroll={{ x: 800 }}
        size="small"
      />
    </Card>
  )
}
