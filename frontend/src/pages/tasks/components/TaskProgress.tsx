import { useEffect, useState } from 'react'
import { Progress, Typography } from 'antd'
import dayjs from 'dayjs'
import type { TaskItem } from './types'

const { Text } = Typography

export interface TaskProgressProps {
  task: TaskItem
}

export default function TaskProgress({ task }: TaskProgressProps) {
  const [elapsed, setElapsed] = useState('')

  useEffect(() => {
    if (task.status !== 'running' || !task.started_at) {
      setElapsed('')
      return
    }
    const update = () => {
      const start = dayjs(task.started_at)
      const now = dayjs()
      const diff = now.diff(start, 'second')
      const h = Math.floor(diff / 3600)
      const m = Math.floor((diff % 3600) / 60)
      const s = diff % 60
      setElapsed(`${h > 0 ? h + 'h ' : ''}${m}m ${s}s`)
    }
    update()
    const timer = setInterval(update, 1000)
    return () => clearInterval(timer)
  }, [task.status, task.started_at])

  if (task.status === 'completed') {
    return <Progress percent={100} size="small" status="success" />
  }
  if (task.status === 'failed') {
    return <Progress percent={task.progress} size="small" status="exception" />
  }
  if (task.status === 'running') {
    const remaining = task.progress > 0
      ? Math.round((elapsed ? dayjs().diff(dayjs(task.started_at), 'second') : 0) * (100 - task.progress) / task.progress)
      : 0

    return (
      <div>
        <Progress percent={task.progress} size="small" />
        <div style={{ fontSize: 11, color: '#888', marginTop: 2 }}>
          {elapsed && <span>已用 {elapsed}</span>}
          {remaining > 0 && <span> · 预计剩余 {Math.round(remaining / 60)}m</span>}
          <span> · {task.progress}%</span>
        </div>
      </div>
    )
  }
  return <Text type="secondary">-</Text>
}
