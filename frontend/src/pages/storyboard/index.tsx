import { useEffect, useState, useCallback } from 'react'
import { useParams } from 'react-router-dom'
import {
  Card, Row, Col, Select, Tag, Button, Space, Typography,
  message, Spin, Table, Modal, Input, Form, Divider,
} from 'antd'
import {
  EditOutlined, CameraOutlined, LayoutOutlined,
} from '@ant-design/icons'
import apiClient from '../../api/client'
import ProjectFilter from '../../components/common/ProjectFilter'
import EmptyState from '../../components/common/EmptyState'

const { Title, Text } = Typography
const { TextArea } = Input

interface Panel {
  id: string
  scene_id: string
  panel_number: number
  source_text?: string
  characters?: string[]
  action?: string
  emotion?: string
  camera_type?: string
  camera_movement?: string
  composition?: string
  layout_type?: string
  beat?: string
  status: string
  created_at: string
  updated_at: string
}

interface Scene {
  id: string
  scene_number: number
  summary?: string
  status: string
}

// 镜头类型选项
const CAMERA_TYPE_OPTIONS = [
  { value: 'long_shot', label: '远景 (Long Shot)' },
  { value: 'medium_shot', label: '中景 (Medium Shot)' },
  { value: 'close_up', label: '近景 (Close-up)' },
  { value: 'extreme_close_up', label: '特写 (Extreme Close-up)' },
  { value: 'overhead_shot', label: '俯拍 (Overhead Shot)' },
  { value: 'low_angle_shot', label: '仰拍 (Low Angle Shot)' },
  { value: 'pov', label: 'POV (Point of View)' },
]

// 运镜方式选项
const CAMERA_MOVEMENT_OPTIONS = [
  { value: 'fixed', label: '固定镜头' },
  { value: 'pan', label: '横摇 (Pan)' },
  { value: 'tilt', label: '纵摇 (Tilt)' },
  { value: 'dolly', label: '推拉 (Dolly)' },
  { value: 'track', label: '平移 (Track)' },
  { value: 'follow', label: '跟拍 (Follow)' },
  { value: 'crane', label: '升降 (Crane)' },
]

// 构图规则选项
const COMPOSITION_OPTIONS = [
  { value: 'rule_of_thirds', label: '三分法' },
  { value: 'symmetry', label: '对称构图' },
  { value: 'leading_lines', label: '引导线' },
  { value: 'framing', label: '框架构图' },
  { value: 'diagonal', label: '对角线' },
  { value: 'golden_ratio', label: '黄金比例' },
  { value: 'center', label: '居中构图' },
]

const PANEL_STATUS_MAP: Record<string, string> = {
  pending: '待处理',
  prompt_ready: '已分镜',
  generating: '生成中',
  generated: '已生成',
  selected: '已选择',
  approved: '已审核',
}

const PANEL_STATUS_COLOR: Record<string, string> = {
  pending: 'default',
  prompt_ready: 'processing',
  generating: 'warning',
  generated: 'warning',
  selected: 'success',
  approved: 'success',
}

export default function StoryboardCenter() {
  const { id: urlProjectId } = useParams<{ id: string }>()
  const [projectId, setProjectId] = useState<string | undefined>(urlProjectId)
  const [panels, setPanels] = useState<Panel[]>([])
  const [scenes, setScenes] = useState<Scene[]>([])
  const [loading, setLoading] = useState(false)
  const [selectedSceneId, setSelectedSceneId] = useState<string | undefined>(undefined)
  const [editPanel, setEditPanel] = useState<Panel | null>(null)
  const [editModalOpen, setEditModalOpen] = useState(false)
  const [saving, setSaving] = useState(false)

  // 编辑表单
  const [editForm] = Form.useForm()

  useEffect(() => {
    setProjectId(urlProjectId)
  }, [urlProjectId])

  // 获取场景列表
  const fetchScenes = useCallback(async () => {
    if (!projectId) return
    try {
      const res: any = await apiClient.get(`/projects/${projectId}/chapters/scenes`)
      setScenes((res as any)?.data?.items || [])
    } catch {
      setScenes([])
    }
  }, [projectId])

  // 获取Panel列表
  const fetchPanels = useCallback(async (sceneId?: string) => {
    if (!projectId) return
    setLoading(true)
    try {
      if (sceneId) {
        const res: any = await apiClient.get(`/projects/${projectId}/scenes/${sceneId}/panels`)
        const data = (res as { data?: { items?: Panel[] } }).data
        setPanels(data?.items || [])
      } else {
        setPanels([])
      }
    } catch {
      setPanels([])
    } finally {
      setLoading(false)
    }
  }, [projectId])

  useEffect(() => {
    fetchScenes()
  }, [fetchScenes])

  useEffect(() => {
    fetchPanels(selectedSceneId)
  }, [selectedSceneId, fetchPanels])

  const handleProjectChange = (newProjectId: string | undefined) => {
    if (newProjectId) {
      setProjectId(newProjectId)
      setSelectedSceneId(undefined)
    }
  }

  const handleSceneChange = (value: string | undefined) => {
    setSelectedSceneId(value)
  }

  const handleEditPanel = (panel: Panel) => {
    setEditPanel(panel)
    editForm.setFieldsValue({
      action: panel.action || '',
      emotion: panel.emotion || '',
      camera_type: panel.camera_type || undefined,
      camera_movement: panel.camera_movement || undefined,
      composition: panel.composition || undefined,
      beat: panel.beat || '',
      description: panel.source_text || '',
    })
    setEditModalOpen(true)
  }

  const handleSavePanel = async () => {
    if (!projectId || !editPanel) return
    setSaving(true)
    try {
      const values = await editForm.validateFields()
      await apiClient.put(`/projects/${projectId}/panels/${editPanel.id}`, {
        action: values.action,
        emotion: values.emotion,
        camera_type: values.camera_type,
        camera_movement: values.camera_movement,
        composition: values.composition,
        beat: values.beat,
        status: 'prompt_ready',
      })
      message.success('分镜信息保存成功')
      setEditModalOpen(false)
      fetchPanels(selectedSceneId)
    } catch {
      message.error('保存失败')
    } finally {
      setSaving(false)
    }
  }

  const columns = [
    {
      title: 'Panel #',
      dataIndex: 'panel_number',
      key: 'panel_number',
      width: 80,
    },
    {
      title: '原文',
      dataIndex: 'source_text',
      key: 'source_text',
      ellipsis: true,
      width: 250,
    },
    {
      title: '镜头类型',
      dataIndex: 'camera_type',
      key: 'camera_type',
      width: 120,
      render: (val: string) => {
        const opt = CAMERA_TYPE_OPTIONS.find((o) => o.value === val)
        return opt ? <Tag>{opt.label.split('(')[0].trim()}</Tag> : (val || '-')
      },
    },
    {
      title: '运镜',
      dataIndex: 'camera_movement',
      key: 'camera_movement',
      width: 120,
      render: (val: string) => {
        const opt = CAMERA_MOVEMENT_OPTIONS.find((o) => o.value === val)
        return opt?.label || val || '-'
      },
    },
    {
      title: '构图',
      dataIndex: 'composition',
      key: 'composition',
      width: 100,
      render: (val: string) => {
        const opt = COMPOSITION_OPTIONS.find((o) => o.value === val)
        return opt?.label || val || '-'
      },
    },
    {
      title: '动作',
      dataIndex: 'action',
      key: 'action',
      width: 120,
      ellipsis: true,
    },
    {
      title: '情绪',
      dataIndex: 'emotion',
      key: 'emotion',
      width: 80,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 90,
      render: (status: string) => (
        <Tag color={PANEL_STATUS_COLOR[status] || 'default'}>
          {PANEL_STATUS_MAP[status] || status}
        </Tag>
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: 80,
      render: (_: any, record: Panel) => (
        <Button
          type="link"
          icon={<EditOutlined />}
          onClick={() => handleEditPanel(record)}
        >
          编辑
        </Button>
      ),
    },
  ]

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>分镜中心</Title>
      </div>

      <Card style={{ marginBottom: 16 }}>
        <ProjectFilter
          projectId={projectId}
          onProjectChange={handleProjectChange}
          showSearch={false}
        />
      </Card>

      {!projectId ? (
        <EmptyState description="请先在顶部选择一个项目" />
      ) : (
        <>
          <Card style={{ marginBottom: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <Text strong>选择场景：</Text>
              <Select
                placeholder="请选择场景"
                style={{ width: 350 }}
                allowClear
                value={selectedSceneId}
                onChange={handleSceneChange}
                options={scenes.map((s) => ({
                  label: `场景 #${s.scene_number}${s.summary ? ` - ${s.summary}` : ''}`,
                  value: s.id,
                }))}
              />
            </div>
          </Card>

          {!selectedSceneId ? (
            <EmptyState description="请先选择一个场景开始分镜规划" />
          ) : loading ? (
            <Spin style={{ display: 'block', margin: '40px auto' }} />
          ) : panels.length === 0 ? (
            <EmptyState description="该场景暂无 Panel，请先在场景管理中执行语义切分" />
          ) : (
            <div>
              <div style={{ marginBottom: 12, color: '#666', fontSize: 13 }}>
                共 {panels.length} 个 Panel
              </div>
              <Table
                dataSource={panels}
                columns={columns}
                rowKey="id"
                pagination={false}
                size="middle"
              />
            </div>
          )}
        </>
      )}

      {/* 编辑 Modal */}
      <Modal
        title={
          <Space>
            <CameraOutlined />
            <span>分镜编辑 - Panel #{editPanel?.panel_number}</span>
          </Space>
        }
        open={editModalOpen}
        onCancel={() => setEditModalOpen(false)}
        onOk={handleSavePanel}
        confirmLoading={saving}
        width={700}
        okText="保存"
        cancelText="取消"
      >
        <Form
          form={editForm}
          layout="vertical"
          style={{ marginTop: 16 }}
        >
          <Form.Item label="原文" name="description">
            <TextArea rows={3} readOnly style={{ background: '#f5f5f5' }} />
          </Form.Item>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item label="动作描述" name="action">
                <Input placeholder="描述角色的动作" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item label="情绪" name="emotion">
                <Input placeholder="如：紧张、悲伤、愤怒" />
              </Form.Item>
            </Col>
          </Row>

          <Divider orientation="left" plain><CameraOutlined /> 镜头规划</Divider>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item label="镜头类型" name="camera_type">
                <Select
                  placeholder="选择镜头类型"
                  options={CAMERA_TYPE_OPTIONS}
                  allowClear
                />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item label="运镜方式" name="camera_movement">
                <Select
                  placeholder="选择运镜方式"
                  options={CAMERA_MOVEMENT_OPTIONS}
                  allowClear
                />
              </Form.Item>
            </Col>
          </Row>

          <Divider orientation="left" plain><LayoutOutlined /> 构图规划</Divider>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item label="构图规则" name="composition">
                <Select
                  placeholder="选择构图规则"
                  options={COMPOSITION_OPTIONS}
                  allowClear
                />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item label="节拍" name="beat">
                <Input placeholder="如：开场、高潮、转折" />
              </Form.Item>
            </Col>
          </Row>
        </Form>
      </Modal>
    </div>
  )
}
