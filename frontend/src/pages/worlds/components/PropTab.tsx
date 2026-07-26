import { useState } from 'react'
import { Button, Space, Table, Tag, Modal, Form, Input, Select, Image, message } from 'antd'
import { EditOutlined, DeleteOutlined, PlusOutlined, PictureOutlined, SaveOutlined } from '@ant-design/icons'
import { useWorldStore } from '../../../stores/worldStore'
import EmptyState from '../../../components/common/EmptyState'
import { extractNovelText } from './extractNovelText'
import type { Prop } from '../../../types/world'

const { TextArea } = Input

interface EditingDescription {
  id: string
  description: string
}

interface Props {
  projectId: string
  worldId: string
}

const PROP_CATEGORY_OPTIONS = [
  { label: '武器', value: '武器' },
  { label: '日常', value: '日常' },
  { label: '魔法', value: '魔法' },
  { label: '科技', value: '科技' },
  { label: '其他', value: '其他' },
]

export default function PropTab({ projectId, worldId }: Props) {
  const {
    props,
    fetchProps,
    createProp,
    updateProp,
    deleteProp,
    aiExtractProps,
    generatePropImage,
  } = useWorldStore()

  const [propModalOpen, setPropModalOpen] = useState(false)
  const [propForm] = Form.useForm()
  const [editingProp, setEditingProp] = useState<Prop | null>(null)
  const [extractPropLoading, setExtractPropLoading] = useState(false)
  const [editingPropDescription, setEditingPropDescription] = useState<EditingDescription | null>(null)
  const [generatingPropImage, setGeneratingPropImage] = useState<string | null>(null)

  const handleExtractProps = async () => {
    setExtractPropLoading(true)
    try {
      const novelText = await extractNovelText(projectId)
      if (!novelText) return
      await aiExtractProps(projectId, worldId, novelText)
      fetchProps(projectId, worldId)
    } catch (e: any) {
      message.error(e.response?.data?.detail || '提取失败')
    } finally {
      setExtractPropLoading(false)
    }
  }

  const handleSavePropDescription = async (record: Prop) => {
    if (!editingPropDescription) return
    try {
      await updateProp(projectId, worldId, record.id, { description: editingPropDescription.description })
      message.success('描述更新成功')
      setEditingPropDescription(null)
      fetchProps(projectId, worldId)
    } catch (e: any) {
      message.error(e.response?.data?.detail || '更新失败')
    }
  }

  const handleGeneratePropImage = async (record: Prop) => {
    setGeneratingPropImage(record.id)
    try {
      await generatePropImage(projectId, worldId, record.id)
      message.success(`道具「${record.name}」图片生成成功`)
    } catch (e: any) {
      message.error(e.response?.data?.detail || '生成失败')
    } finally {
      setGeneratingPropImage(null)
    }
  }

  const handleCreateProp = async (values: any) => {
    try {
      if (editingProp) {
        await updateProp(projectId, worldId, editingProp.id, values)
        message.success('道具更新成功')
      } else {
        await createProp(projectId, worldId, values)
        message.success('道具创建成功')
      }
      setPropModalOpen(false)
      setEditingProp(null)
      propForm.resetFields()
      fetchProps(projectId, worldId)
    } catch {
      message.error('操作失败')
    }
  }

  const handleEditProp = (prop: Prop) => {
    setEditingProp(prop)
    propForm.setFieldsValue(prop)
    setPropModalOpen(true)
  }

  const handleDeleteProp = (propId: string) => {
    Modal.confirm({
      title: '确认删除',
      content: '确定要删除该道具吗？',
      okType: 'danger',
      onOk: async () => {
        try {
          await deleteProp(projectId, worldId, propId)
          message.success('删除成功')
          fetchProps(projectId, worldId)
        } catch {
          message.error('删除失败')
        }
      },
    })
  }

  const propColumns = [
    {
      title: '道具图片',
      key: 'image',
      width: 120,
      render: (_: any, record: Prop) => {
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
      title: '道具信息',
      key: 'info',
      width: 180,
      render: (_: any, record: Prop) => (
        <div>
          <div style={{ fontSize: 14, fontWeight: 600 }}>{record.name}</div>
          <Space wrap size={4} style={{ marginTop: 4 }}>
            {record.category && <Tag>{record.category}</Tag>}
          </Space>
        </div>
      ),
    },
    {
      title: '道具描述',
      key: 'description',
      render: (_: any, record: Prop) => {
        const isEditing = editingPropDescription?.id === record.id
        if (isEditing) {
          return (
            <div>
              <TextArea
                rows={3}
                value={editingPropDescription!.description}
                onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setEditingPropDescription({ ...editingPropDescription!, description: e.target.value })}
                style={{ marginBottom: 8 }}
              />
              <Space>
                <Button size="small" icon={<SaveOutlined />} onClick={() => handleSavePropDescription(record)}>
                  保存
                </Button>
                <Button size="small" onClick={() => setEditingPropDescription(null)}>
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
                onClick={() => setEditingPropDescription({ id: record.id, description: record.description || '' })}
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
      render: (_: any, record: Prop) => (
        <Space>
          <Button size="small" icon={<EditOutlined />} onClick={() => handleEditProp(record)}>
            编辑
          </Button>
          <Button
            size="small"
            loading={generatingPropImage === record.id}
            onClick={() => handleGeneratePropImage(record)}
          >
            生成图片
          </Button>
          <Button size="small" danger icon={<DeleteOutlined />} onClick={() => handleDeleteProp(record.id)}>
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
            onClick={() => { propForm.resetFields(); setPropModalOpen(true); }}
          >
            添加道具
          </Button>
          <Button
            type="primary"
            icon={<PictureOutlined />}
            loading={extractPropLoading}
            onClick={handleExtractProps}
          >
            一键提取道具
          </Button>
        </Space>
      </div>
      {props.length === 0 ? (
        <EmptyState description="暂无道具" />
      ) : (
        <Table dataSource={props} columns={propColumns} rowKey="id" pagination={{ pageSize: 10 }} scroll={{ x: 800 }} />
      )}

      <Modal title={editingProp ? '编辑道具' : '添加道具'} open={propModalOpen} onCancel={() => { setPropModalOpen(false); setEditingProp(null); }} footer={null} destroyOnClose>
        <Form form={propForm} layout="vertical" onFinish={handleCreateProp}>
          <Form.Item name="name" label="名称" rules={[{ required: true }]}>
            <Input placeholder="如：魔法杖、古剑" />
          </Form.Item>
          <Form.Item name="category" label="分类">
            <Select allowClear options={PROP_CATEGORY_OPTIONS} placeholder="选择道具类型" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item name="visual_description" label="视觉描述">
            <Input.TextArea rows={2} placeholder="道具的外观细节" />
          </Form.Item>
          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit">保存</Button>
              <Button onClick={() => { setPropModalOpen(false); setEditingProp(null); }}>取消</Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
