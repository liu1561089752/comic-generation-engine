import { useState } from 'react'
import { Button, Space, Table, Tag, Modal, Form, Input, Select, Image, message } from 'antd'
import { EditOutlined, DeleteOutlined, PlusOutlined, PictureOutlined, SaveOutlined } from '@ant-design/icons'
import { useWorldStore } from '../../../stores/worldStore'
import { useMultiTaskProgress } from '../../../hooks/useMultiTaskProgress'
import EmptyState from '../../../components/common/EmptyState'
import { extractNovelText } from './extractNovelText'
import type { Building } from '../../../types/world'

const { TextArea } = Input

interface EditingDescription {
  id: string
  description: string
}

interface Props {
  projectId: string
  worldId: string
}

const BUILDING_STYLE_OPTIONS = [
  { label: '东方', value: '东方' },
  { label: '西方', value: '西方' },
  { label: '科幻', value: '科幻' },
  { label: '古典', value: '古典' },
  { label: '现代', value: '现代' },
]

const INTERIOR_EXTERIOR_OPTIONS = [
  { label: '内景', value: '内景' },
  { label: '外景', value: '外景' },
  { label: '两者', value: '两者' },
]

export default function BuildingTab({ projectId, worldId }: Props) {
  const {
    buildings,
    fetchBuildings,
    createBuilding,
    updateBuilding,
    deleteBuilding,
    aiExtractBuildings,
    generateBuildingImage,
  } = useWorldStore()

  const [buildingModalOpen, setBuildingModalOpen] = useState(false)
  const [buildingForm] = Form.useForm()
  const [editingBuilding, setEditingBuilding] = useState<Building | null>(null)
  const [extractBuildingLoading, setExtractBuildingLoading] = useState(false)
  const [editingBuildingDescription, setEditingBuildingDescription] = useState<EditingDescription | null>(null)
  const [generatingBuildingImage, setGeneratingBuildingImage] = useState<string | null>(null)

  // AI 任务进度（一键提取建筑 / 生成建筑图片 均纳入任务中心管理）
  const taskProgress = useMultiTaskProgress({
    projectId,
    onTaskCompleted: (taskId) => {
      const output = taskProgress.getTask(taskId)?.outputData
      if (output?.total != null) {
        message.success(`成功提取 ${output.total} 个建筑`)
      } else if (output?.building_name) {
        message.success(`建筑「${output.building_name}」图片生成成功`)
      } else {
        message.success('任务完成')
      }
      fetchBuildings(projectId, worldId)
    },
    onTaskFailed: (_taskId, error) => {
      message.error(error || '任务失败')
    },
  })

  const handleExtractBuildings = async () => {
    setExtractBuildingLoading(true)
    try {
      const novelText = await extractNovelText(projectId)
      if (!novelText) return
      const taskId = await aiExtractBuildings(projectId, worldId, novelText)
      if (taskId) {
        taskProgress.startPolling(taskId)
        message.info('提取建筑任务已提交，可在任务中心查看进度')
      }
    } catch (e: any) {
      message.error(e.response?.data?.detail || '提取失败')
    } finally {
      setExtractBuildingLoading(false)
    }
  }

  const handleSaveBuildingDescription = async (record: Building) => {
    if (!editingBuildingDescription) return
    try {
      await updateBuilding(projectId, worldId, record.id, { description: editingBuildingDescription.description })
      message.success('描述更新成功')
      setEditingBuildingDescription(null)
      fetchBuildings(projectId, worldId)
    } catch (e: any) {
      message.error(e.response?.data?.detail || '更新失败')
    }
  }

  const handleGenerateBuildingImage = async (record: Building) => {
    setGeneratingBuildingImage(record.id)
    try {
      const taskId = await generateBuildingImage(projectId, worldId, record.id)
      if (taskId) {
        taskProgress.startPolling(taskId)
        message.info('生成图片任务已提交，可在任务中心查看进度')
      }
    } catch (e: any) {
      message.error(e.response?.data?.detail || '生成失败')
    } finally {
      setGeneratingBuildingImage(null)
    }
  }

  const handleCreateBuilding = async (values: any) => {
    try {
      if (editingBuilding) {
        await updateBuilding(projectId, worldId, editingBuilding.id, values)
        message.success('建筑更新成功')
      } else {
        await createBuilding(projectId, worldId, values)
        message.success('建筑创建成功')
      }
      setBuildingModalOpen(false)
      setEditingBuilding(null)
      buildingForm.resetFields()
      fetchBuildings(projectId, worldId)
    } catch {
      message.error('操作失败')
    }
  }

  const handleEditBuilding = (building: Building) => {
    setEditingBuilding(building)
    buildingForm.setFieldsValue(building)
    setBuildingModalOpen(true)
  }

  const handleDeleteBuilding = (buildingId: string) => {
    Modal.confirm({
      title: '确认删除',
      content: '确定要删除该建筑吗？',
      okType: 'danger',
      onOk: async () => {
        try {
          await deleteBuilding(projectId, worldId, buildingId)
          message.success('删除成功')
          fetchBuildings(projectId, worldId)
        } catch {
          message.error('删除失败')
        }
      },
    })
  }

  const buildingColumns = [
    {
      title: '建筑图片',
      key: 'image',
      width: 120,
      render: (_: any, record: Building) => {
        const imageUrl = record.image_url ||
          (record.description ? `https://trae-api-cn.mchost.guru/api/ide/v1/text_to_image?prompt=${encodeURIComponent(record.description)}&image_size=landscape_16_9` : null)

        return (
          <div>
            {imageUrl ? (
              <Image
                src={imageUrl.startsWith('/storage/') ? `${window.location.origin}${imageUrl}` : imageUrl}
                alt={record.name}
                width={100}
                height={56}
                style={{ objectFit: 'cover', borderRadius: 4 }}
                preview={{ src: imageUrl.startsWith('/storage/') ? `${window.location.origin}${imageUrl}` : imageUrl }}
              />
            ) : (
              <div style={{ width: 100, height: 56, background: '#f5f5f5', borderRadius: 4, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#999', fontSize: 12 }}>
                <PictureOutlined />
              </div>
            )}
          </div>
        )
      },
    },
    {
      title: '建筑信息',
      key: 'info',
      width: 180,
      render: (_: any, record: Building) => (
        <div>
          <div style={{ fontSize: 14, fontWeight: 600 }}>{record.name}</div>
          <Space wrap size={4} style={{ marginTop: 4 }}>
            {record.style && <Tag>{record.style}</Tag>}
            {record.interior_exterior && <Tag>{record.interior_exterior}</Tag>}
          </Space>
        </div>
      ),
    },
    {
      title: '建筑描述',
      key: 'description',
      render: (_: any, record: Building) => {
        const isEditing = editingBuildingDescription?.id === record.id
        if (isEditing) {
          return (
            <div>
              <TextArea
                rows={3}
                value={editingBuildingDescription!.description}
                onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setEditingBuildingDescription({ ...editingBuildingDescription!, description: e.target.value })}
                style={{ marginBottom: 8 }}
              />
              <Space>
                <Button size="small" icon={<SaveOutlined />} onClick={() => handleSaveBuildingDescription(record)}>
                  保存
                </Button>
                <Button size="small" onClick={() => setEditingBuildingDescription(null)}>
                  取消
                </Button>
              </Space>
            </div>
          )
        }
        return (
          <div>
            <div style={{ fontSize: 12, color: '#666', lineHeight: 1.6, maxHeight: 80, overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {record.description || '暂无描述'}
            </div>
            {record.description && (
              <Button
                size="small"
                icon={<EditOutlined />}
                onClick={() => setEditingBuildingDescription({ id: record.id, description: record.description || '' })}
                style={{ marginTop: 8 }}
              >
                编辑描述
              </Button>
            )}
          </div>
        )
      },
    },
    {
      title: '操作',
      key: 'action',
      width: 160,
      render: (_: any, record: Building) => (
        <Space>
          <Button size="small" icon={<EditOutlined />} onClick={() => handleEditBuilding(record)}>
            编辑
          </Button>
          <Button
            size="small"
            loading={generatingBuildingImage === record.id}
            onClick={() => handleGenerateBuildingImage(record)}
          >
            生成图片
          </Button>
          <Button size="small" danger icon={<DeleteOutlined />} onClick={() => handleDeleteBuilding(record.id)}>
            删除
          </Button>
        </Space>
      ),
    },
  ]

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 16 }}>
        <Space>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => { buildingForm.resetFields(); setBuildingModalOpen(true); }}
          >
            添加建筑
          </Button>
          <Button
            type="primary"
            icon={<PictureOutlined />}
            loading={extractBuildingLoading}
            onClick={handleExtractBuildings}
          >
            一键提取建筑
          </Button>
        </Space>
      </div>
      {buildings.length === 0 ? (
        <EmptyState description="暂无建筑" />
      ) : (
        <Table dataSource={buildings} columns={buildingColumns} rowKey="id" pagination={{ pageSize: 10 }} scroll={{ x: 800 }} />
      )}

      <Modal title={editingBuilding ? '编辑建筑' : '添加建筑'} open={buildingModalOpen} onCancel={() => { setBuildingModalOpen(false); setEditingBuilding(null); }} footer={null} destroyOnClose>
        <Form form={buildingForm} layout="vertical" onFinish={handleCreateBuilding}>
          <Form.Item name="name" label="名称" rules={[{ required: true }]}>
            <Input placeholder="如：城堡、神庙" />
          </Form.Item>
          <Form.Item name="style" label="风格">
            <Select allowClear options={BUILDING_STYLE_OPTIONS} placeholder="选择建筑风格" />
          </Form.Item>
          <Form.Item name="interior_exterior" label="内外景">
            <Select allowClear options={INTERIOR_EXTERIOR_OPTIONS} placeholder="选择内外景" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item name="interior_description" label="内部描述">
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit">保存</Button>
              <Button onClick={() => { setBuildingModalOpen(false); setEditingBuilding(null); }}>取消</Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
