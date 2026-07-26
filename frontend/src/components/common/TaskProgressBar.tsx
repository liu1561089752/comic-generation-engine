import React from 'react'
import { Progress } from 'antd'
import { AlertOutlined, CheckCircleOutlined, CloseCircleOutlined, LoadingOutlined } from '@ant-design/icons'

interface TaskProgressBarProps {
  visible: boolean
  status: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled' | null
  progress: number
  errorMessage?: string | null
  logs?: Array<{ timestamp: string; message: string; level: string }>
}

export const TaskProgressBar: React.FC<TaskProgressBarProps> = ({
  visible,
  status,
  progress,
  errorMessage,
  logs,
}) => {
  if (!visible) return null

  const getStatusInfo = () => {
    switch (status) {
      case 'queued':
        return { text: '等待中...', icon: <LoadingOutlined />, color: '#faad14' }
      case 'running':
        return { text: `生成中... ${progress}%`, icon: <LoadingOutlined />, color: '#1890ff' }
      case 'completed':
        return { text: '生成完成 ✓', icon: <CheckCircleOutlined />, color: '#52c41a' }
      case 'failed':
        return { text: `生成失败: ${errorMessage || '未知错误'}`, icon: <CloseCircleOutlined />, color: '#ff4d4f' }
      default:
        return { text: '', icon: null, color: '#ccc' }
    }
  }

  const info = getStatusInfo()

  return (
    <div style={{
      padding: '16px',
      background: '#fafafa',
      borderRadius: '8px',
      border: `1px solid ${info.color}33`,
      marginBottom: '16px',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
        <span style={{ color: info.color }}>{info.icon}</span>
        <span style={{ fontSize: '14px', color: info.color }}>{info.text}</span>
      </div>

      {(status === 'queued' || status === 'running') && (
        <Progress percent={progress} status="active" strokeColor={info.color} />
      )}

      {status === 'failed' && errorMessage && (
        <div style={{ marginTop: '8px', padding: '8px', background: '#fff2f0', borderRadius: '4px', fontSize: '12px', color: '#ff4d4f' }}>
          <AlertOutlined style={{ marginRight: '4px' }} />
          {errorMessage}
        </div>
      )}

      {logs && logs.length > 0 && (
        <div style={{ marginTop: '8px', maxHeight: '120px', overflow: 'auto', fontSize: '12px', color: '#888' }}>
          {logs.slice(-5).map((log, i) => (
            <div key={i} style={{ padding: '2px 0' }}>
              {log.message}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
