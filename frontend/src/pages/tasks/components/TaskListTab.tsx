import { Button, Card, Col, DatePicker, Input, Row, Select, Space, Table, Tag, Tooltip, Typography } from 'antd'
import {
  PlusOutlined,
  ReloadOutlined,
  RedoOutlined,
  StopOutlined,
} from '@ant-design/icons'
import { formatDate } from '../../../utils/format'
import StatusIndicator from './StatusIndicator'
import TaskProgress from './TaskProgress'
import TaskDetailPanel from './TaskDetailPanel'
import {
  PRIORITY_COLORS,
  PRIORITY_FILTERS,
  PRIORITY_LABELS,
  SORT_OPTIONS,
  STATUS_FILTERS,
  TYPE_FILTERS,
  TYPE_LABELS,
} from './types'
import type { TaskItem } from './types'

const { Text } = Typography
const { RangePicker } = DatePicker

export interface TaskListTabProps {
  tasks: TaskItem[]
  loading: boolean
  total: number
  page: number
  pageSize: number
  statusFilter: string
  typeFilter: string
  priorityFilter: string
  projectFilter: string
  sortBy: string
  sortOrder: string
  selectedRowKeys: string[]
  expandedRowKeys: string[]
  actionLoading: string | null
  batchLoading: boolean
  onStatusFilterChange: (v: string) => void
  onTypeFilterChange: (v: string) => void
  onPriorityFilterChange: (v: string) => void
  onProjectFilterChange: (v: string) => void
  onDateRangeChange: (range: [string, string] | null) => void
  onSortByChange: (v: string) => void
  onSortOrderChange: (v: string) => void
  onPageChange: (page: number, pageSize: number) => void
  onSelectedRowKeysChange: (keys: string[]) => void
  onExpandedRowKeysChange: (keys: string[]) => void
  onSortChange: (field: string, order: 'asc' | 'desc') => void
  onRefresh: () => void
  onBatchCancel: () => void
  onBatchRetry: () => void
  onCreateTask: () => void
  onCancelTask: (id: string) => void
  onRetryTask: (id: string) => void
}

export default function TaskListTab({
  tasks,
  loading,
  total,
  page,
  pageSize,
  statusFilter,
  typeFilter,
  priorityFilter,
  projectFilter,
  sortBy,
  sortOrder,
  selectedRowKeys,
  expandedRowKeys,
  actionLoading,
  batchLoading,
  onStatusFilterChange,
  onTypeFilterChange,
  onPriorityFilterChange,
  onProjectFilterChange,
  onDateRangeChange,
  onSortByChange,
  onSortOrderChange,
  onPageChange,
  onSelectedRowKeysChange,
  onExpandedRowKeysChange,
  onSortChange,
  onRefresh,
  onBatchCancel,
  onBatchRetry,
  onCreateTask,
  onCancelTask,
  onRetryTask,
}: TaskListTabProps) {
  const columns = [
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (_: string, record: TaskItem) => <StatusIndicator status={record.status} />,
    },
    {
      title: 'ID',
      dataIndex: 'id',
      key: 'id',
      width: 100,
      render: (id: string) => (
        <Tooltip title={id}>
          <Text copyable={{ text: id }} style={{ fontFamily: 'monospace', fontSize: 12 }}>
            {id.slice(0, 8)}...
          </Text>
        </Tooltip>
      ),
    },
    {
      title: '类型',
      dataIndex: 'task_type',
      key: 'task_type',
      width: 80,
      render: (type: string) => TYPE_LABELS[type] || type,
    },
    {
      title: '优先级',
      dataIndex: 'priority',
      key: 'priority',
      width: 70,
      render: (p: string) => (
        <Tag color={PRIORITY_COLORS[p] || 'default'}>{PRIORITY_LABELS[p] || p}</Tag>
      ),
    },
    {
      title: '进度',
      dataIndex: 'progress',
      key: 'progress',
      width: 200,
      render: (_: number, record: TaskItem) => <TaskProgress task={record} />,
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 160,
      render: (t: string) => (t ? formatDate(t) : '-'),
      sorter: true,
    },
    {
      title: '操作',
      key: 'actions',
      width: 100,
      render: (_: any, record: TaskItem) => (
        <Space size="small">
          {(record.status === 'queued' || record.status === 'running') && (
            <Tooltip title="取消任务">
              <Button
                type="link"
                size="small"
                danger
                icon={<StopOutlined />}
                loading={actionLoading === record.id}
                onClick={(e) => { e.stopPropagation(); onCancelTask(record.id) }}
              />
            </Tooltip>
          )}
          {record.status === 'failed' && (
            <Tooltip title="重试">
              <Button
                type="link"
                size="small"
                icon={<RedoOutlined />}
                loading={actionLoading === record.id}
                onClick={(e) => { e.stopPropagation(); onRetryTask(record.id) }}
              />
            </Tooltip>
          )}
          {record.status === 'cancelled' && (
            <Tooltip title="重试">
              <Button
                type="link"
                size="small"
                icon={<RedoOutlined />}
                loading={actionLoading === record.id}
                onClick={(e) => { e.stopPropagation(); onRetryTask(record.id) }}
              />
            </Tooltip>
          )}
        </Space>
      ),
    },
  ]

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      {/* 筛选栏 */}
      <Card size="small">
        <Row gutter={[12, 12]} align="middle">
          <Col>
            <Select
              style={{ width: 120 }}
              value={statusFilter}
              onChange={onStatusFilterChange}
              options={STATUS_FILTERS}
            />
          </Col>
          <Col>
            <Select
              style={{ width: 120 }}
              value={typeFilter}
              onChange={onTypeFilterChange}
              options={TYPE_FILTERS}
            />
          </Col>
          <Col>
            <Select
              style={{ width: 130 }}
              value={priorityFilter}
              onChange={onPriorityFilterChange}
              options={PRIORITY_FILTERS}
            />
          </Col>
          <Col>
            <Input
              style={{ width: 200 }}
              placeholder="项目ID"
              allowClear
              value={projectFilter}
              onChange={(e) => onProjectFilterChange(e.target.value)}
            />
          </Col>
          <Col>
            <RangePicker
              showTime
              onChange={(dates) => {
                if (dates && dates[0] && dates[1]) {
                  onDateRangeChange([dates[0].toISOString(), dates[1].toISOString()])
                } else {
                  onDateRangeChange(null)
                }
              }}
            />
          </Col>
          <Col>
            <Select style={{ width: 110 }} value={sortBy} onChange={onSortByChange} options={SORT_OPTIONS} />
          </Col>
          <Col>
            <Select
              style={{ width: 80 }}
              value={sortOrder}
              onChange={onSortOrderChange}
              options={[
                { value: 'desc', label: '降序' },
                { value: 'asc', label: '升序' },
              ]}
            />
          </Col>
          <Col>
            <Button icon={<ReloadOutlined />} onClick={onRefresh}>
              刷新
            </Button>
          </Col>
        </Row>
      </Card>

      {/* 批量操作栏 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Space>
          {selectedRowKeys.length > 0 && (
            <>
              <Text type="secondary">已选 {selectedRowKeys.length} 项</Text>
              <Button
                size="small"
                icon={<StopOutlined />}
                onClick={onBatchCancel}
                loading={batchLoading}
                danger
              >
                批量取消
              </Button>
              <Button
                size="small"
                icon={<RedoOutlined />}
                onClick={onBatchRetry}
                loading={batchLoading}
              >
                批量重试
              </Button>
            </>
          )}
        </Space>
        <Space>
          <Button type="primary" icon={<PlusOutlined />} onClick={onCreateTask}>
            手动创建任务
          </Button>
        </Space>
      </div>

      {/* 任务列表 */}
      <Card>
        <Table
          dataSource={tasks}
          columns={columns}
          rowKey="id"
          loading={loading}
          pagination={{
            current: page,
            pageSize,
            total,
            showSizeChanger: true,
            showTotal: (t) => `共 ${t} 条`,
            onChange: (p, ps) => onPageChange(p, ps),
          }}
          locale={{ emptyText: '暂无任务' }}
          scroll={{ x: 900 }}
          expandable={{
            expandedRowKeys,
            onExpandedRowsChange: (keys: readonly React.Key[]) => onExpandedRowKeysChange(keys as string[]),
            expandedRowRender: (record: TaskItem) => <TaskDetailPanel task={record} />,
            rowExpandable: () => true,
          }}
          rowSelection={{
            selectedRowKeys,
            onChange: (keys: React.Key[]) => onSelectedRowKeysChange(keys.map(String)),
          }}
          onChange={(_pagination, _filters, sorter: any) => {
            if (sorter.field === 'created_at') {
              onSortChange('created_at', sorter.order === 'ascend' ? 'asc' : 'desc')
            }
          }}
        />
      </Card>
    </Space>
  )
}
