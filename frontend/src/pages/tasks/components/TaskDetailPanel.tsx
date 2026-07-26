import { Alert, Descriptions, Divider, Progress, Tag, Typography } from 'antd'
import { formatDate } from '../../../utils/format'
import StatusIndicator from './StatusIndicator'
import { PRIORITY_COLORS, PRIORITY_LABELS, TYPE_LABELS } from './types'
import type { TaskItem } from './types'

const { Text, Paragraph } = Typography

export interface TaskDetailPanelProps {
  task: TaskItem
}

export default function TaskDetailPanel({ task }: TaskDetailPanelProps) {
  const items: any[] = [
    { key: 'id', label: '任务ID', children: <Text copyable style={{ fontFamily: 'monospace', fontSize: 12 }}>{task.id}</Text>, span: 2 },
    { key: 'type', label: '类型', children: TYPE_LABELS[task.task_type] || task.task_type },
    { key: 'status', label: '状态', children: <StatusIndicator status={task.status} /> },
    { key: 'priority', label: '优先级', children: <Tag color={PRIORITY_COLORS[task.priority]}>{PRIORITY_LABELS[task.priority] || task.priority}</Tag> },
    { key: 'project', label: '项目ID', children: task.project_id ? <Text copyable style={{ fontFamily: 'monospace', fontSize: 12 }}>{task.project_id}</Text> : '-' },
    { key: 'progress', label: '进度', children: <Progress percent={task.progress} size="small" style={{ width: 160 }} /> },
    { key: 'created_at', label: '创建时间', children: task.created_at ? formatDate(task.created_at) : '-', span: 2 },
    { key: 'started_at', label: '开始时间', children: task.started_at ? formatDate(task.started_at) : '-', span: 2 },
    { key: 'completed_at', label: '完成时间', children: task.completed_at ? formatDate(task.completed_at) : '-', span: 2 },
  ]

  if (task.error_message) {
    items.push({
      key: 'error',
      label: '失败信息',
      children: <Alert type="error" message={task.error_message} style={{ whiteSpace: 'pre-wrap' }} showIcon />,
      span: 2,
    })
  }

  if (task.input_data) {
    items.push({
      key: 'input',
      label: '执行参数',
      children: (
        <Paragraph
          ellipsis={{ rows: 3, expandable: true, symbol: '展开' }}
          style={{ marginBottom: 0, fontFamily: 'monospace', fontSize: 12, whiteSpace: 'pre-wrap' }}
        >
          {JSON.stringify(task.input_data, null, 2)}
        </Paragraph>
      ),
      span: 2,
    })
  }

  if (task.output_data) {
    items.push({
      key: 'output',
      label: '产出列表',
      children: (
        <Paragraph
          ellipsis={{ rows: 3, expandable: true, symbol: '展开' }}
          style={{ marginBottom: 0, fontFamily: 'monospace', fontSize: 12, whiteSpace: 'pre-wrap' }}
        >
          {JSON.stringify(task.output_data, null, 2)}
        </Paragraph>
      ),
      span: 2,
    })
  }

  return (
    <div style={{ padding: '12px 0' }}>
      <Descriptions column={2} bordered size="small" items={items} />
      {task.logs && task.logs.length > 0 && (
        <>
          <Divider orientation="left" orientationMargin={0}>
            <Text type="secondary" style={{ fontSize: 13 }}>执行日志</Text>
          </Divider>
          <div
            style={{
              background: '#1e1e1e',
              color: '#d4d4d4',
              fontFamily: 'monospace',
              fontSize: 12,
              padding: '8px 12px',
              borderRadius: 4,
              height: 200,
              overflow: 'auto',
              lineHeight: 1.6,
            }}
          >
            {task.logs.map((log, i) => (
              <div key={i}>{log}</div>
            ))}
            {task.logs.length === 0 && <Text type="secondary">暂无日志</Text>}
          </div>
        </>
      )}
    </div>
  )
}
