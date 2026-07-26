import { Badge, Button, Col, Empty, Progress, Row, Space, Spin, Tag, Typography } from 'antd'
import {
  ReloadOutlined,
  ClockCircleOutlined,
  CheckCircleFilled,
  CloseCircleFilled,
  LoadingOutlined,
} from '@ant-design/icons'
import { formatDate } from '../../../utils/format'
import { PRIORITY_COLORS, PRIORITY_LABELS, TYPE_LABELS } from './types'
import type { QueueData, TaskItem } from './types'

const { Text, Title } = Typography

const KANBAN_COLUMNS = [
  { key: 'queued', title: '排队中', color: '#d9d9d9', icon: <ClockCircleOutlined /> },
  { key: 'running', title: '处理中', color: '#1890ff', icon: <LoadingOutlined /> },
  { key: 'completed', title: '已完成', color: '#52c41a', icon: <CheckCircleFilled /> },
  { key: 'failed', title: '失败', color: '#ff4d4f', icon: <CloseCircleFilled /> },
]

function KanbanCard({ task }: { task: TaskItem }) {
  return (
    <div
      style={{
        background: '#fff',
        border: '1px solid #f0f0f0',
        borderRadius: 8,
        padding: '10px 12px',
        marginBottom: 8,
        boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
        transition: 'all 0.3s ease',
        cursor: 'default',
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.boxShadow = '0 2px 8px rgba(0,0,0,0.12)'
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.boxShadow = '0 1px 3px rgba(0,0,0,0.06)'
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
        <Tag style={{ marginRight: 0, fontSize: 11 }}>
          {TYPE_LABELS[task.task_type] || task.task_type}
        </Tag>
        <Tag color={PRIORITY_COLORS[task.priority]} style={{ fontSize: 11 }}>
          {PRIORITY_LABELS[task.priority] || task.priority}
        </Tag>
      </div>
      <Text
        copyable={{ text: task.id }}
        style={{ fontFamily: 'monospace', fontSize: 11, color: '#888' }}
      >
        {task.id.slice(0, 8)}...
      </Text>
      {task.status === 'running' && (
        <div style={{ marginTop: 6 }}>
          <Progress percent={task.progress} size="small" />
          <Text type="secondary" style={{ fontSize: 11 }}>
            {task.progress}%
          </Text>
        </div>
      )}
      <div style={{ marginTop: 4, fontSize: 11, color: '#999' }}>
        {task.created_at ? formatDate(task.created_at, 'MM-DD HH:mm') : '-'}
      </div>
    </div>
  )
}

function KanbanColumn({
  title,
  color,
  icon,
  tasks,
  total,
  loading,
}: {
  title: string
  color: string
  icon: React.ReactNode
  tasks: TaskItem[]
  total: number
  loading: boolean
}) {
  return (
    <div
      style={{
        background: '#fafafa',
        borderRadius: 8,
        padding: 12,
        minHeight: 300,
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          marginBottom: 12,
          paddingBottom: 8,
          borderBottom: `2px solid ${color}`,
        }}
      >
        <span style={{ color }}>{icon}</span>
        <Text strong style={{ fontSize: 14 }}>{title}</Text>
        <Tag style={{ marginLeft: 'auto' }}>{total}</Tag>
      </div>
      <div style={{ flex: 1, overflow: 'auto' }}>
        {loading ? (
          <div style={{ textAlign: 'center', padding: 40 }}><Spin /></div>
        ) : tasks.length === 0 ? (
          <Empty description="暂无任务" image={Empty.PRESENTED_IMAGE_SIMPLE} />
        ) : (
          tasks.map((task) => <KanbanCard key={task.id} task={task} />)
        )}
      </div>
    </div>
  )
}

export interface KanbanViewProps {
  kanbanData: QueueData | null
  kanbanLoading: boolean
  onRefresh: () => void
}

export default function KanbanView({ kanbanData, kanbanLoading, onRefresh }: KanbanViewProps) {
  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={5} style={{ margin: 0 }}>实时队列看板</Title>
        <Space>
          <Badge status="processing" text="WebSocket 实时推送" />
          <Button icon={<ReloadOutlined />} onClick={onRefresh} size="small">
            手动刷新
          </Button>
        </Space>
      </div>
      <Row gutter={16}>
        {KANBAN_COLUMNS.map((col) => (
          <Col key={col.key} span={6}>
            <KanbanColumn
              title={col.title}
              color={col.color}
              icon={col.icon}
              tasks={kanbanData?.[col.key]?.items || []}
              total={kanbanData?.[col.key]?.total || 0}
              loading={kanbanLoading}
            />
          </Col>
        ))}
      </Row>
    </div>
  )
}
