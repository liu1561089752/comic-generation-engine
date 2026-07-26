import { useState } from 'react'
import { Input, Modal, Select, Space, Typography, message } from 'antd'
import apiClient from '../../../api/client'
import { PRIORITY_FILTERS, TYPE_FILTERS } from './types'

const { Text } = Typography

export interface CreateTaskModalProps {
  open: boolean
  onClose: () => void
  onSuccess: () => void
}

export default function CreateTaskModal({
  open,
  onClose,
  onSuccess,
}: CreateTaskModalProps) {
  const [taskType, setTaskType] = useState('generation')
  const [priority, setPriority] = useState('normal')
  const [projectId, setProjectId] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const handleSubmit = async () => {
    setSubmitting(true)
    try {
      const body: any = {
        task_type: taskType,
        priority,
        input_data: {},
      }
      if (projectId.trim()) {
        body.project_id = projectId.trim()
      }
      await apiClient.post('/tasks', body)
      message.success('任务创建成功')
      onClose()
      onSuccess()
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '创建失败')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Modal
      title="手动创建任务"
      open={open}
      onOk={handleSubmit}
      onCancel={onClose}
      confirmLoading={submitting}
      okText="创建"
      cancelText="取消"
    >
      <Space direction="vertical" style={{ width: '100%' }} size="middle">
        <div>
          <Text strong>任务类型</Text>
          <Select
            style={{ width: '100%', marginTop: 4 }}
            value={taskType}
            onChange={setTaskType}
            options={TYPE_FILTERS.filter((f) => f.value)}
          />
        </div>
        <div>
          <Text strong>优先级</Text>
          <Select
            style={{ width: '100%', marginTop: 4 }}
            value={priority}
            onChange={setPriority}
            options={PRIORITY_FILTERS.filter((f) => f.value)}
          />
        </div>
        <div>
          <Text strong>项目ID（可选）</Text>
          <Input
            style={{ marginTop: 4 }}
            placeholder="输入项目 UUID"
            value={projectId}
            onChange={(e) => setProjectId(e.target.value)}
          />
        </div>
      </Space>
    </Modal>
  )
}
