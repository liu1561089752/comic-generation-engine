import { useState } from 'react'
import { Button, Space, Table, Tag, Modal, Form, Input, Select, Image, message } from 'antd'
import { EditOutlined, DeleteOutlined, PlusOutlined, PictureOutlined, SaveOutlined } from '@ant-design/icons'
import { useWorldStore } from '../../../stores/worldStore'
import EmptyState from '../../../components/common/EmptyState'
import { extractNovelText } from './extractNovelText'
import type { Outfit } from '../../../types/world'

const { TextArea } = Input

interface EditingDescription {
  id: string
  description: string
}

interface Props {
  projectId: string
  worldId: string
}

const OUTFIT_STYLE_OPTIONS = [
  { label: '日常', value: '日常' },
  { label: '战斗', value: '战斗' },
  { label: '正式', value: '正式' },
  { label: '传统', value: '传统' },
  { label: '奇幻', value: '奇幻' },
]

export default function OutfitTab({ projectId, worldId }: Props) {
  const {
    outfits,
    fetchOutfits,
    createOutfit,
    updateOutfit,
    deleteOutfit,
    aiExtractOutfits,
    generateOutfitImage,
  } = useWorldStore()

  const [outfitModalOpen, setOutfitModalOpen] = useState(false)
  const [outfitForm] = Form.useForm()
  const [editingOutfit, setEditingOutfit] = useState<Outfit | null>(null)
  const [extractOutfitLoading, setExtractOutfitLoading] = useState(false)
  const [editingOutfitDescription, setEditingOutfitDescription] = useState<EditingDescription | null>(null)
  const [generatingOutfitImage, setGeneratingOutfitImage] = useState<string | null>(null)

  const handleExtractOutfits = async () => {
    setExtractOutfitLoading(true)
    try {
      const novelText = await extractNovelText(projectId)
      if (!novelText) return
      await aiExtractOutfits(projectId, worldId, novelText)
      fetchOutfits(projectId, worldId)
    } catch (e: any) {
      message.error(e.response?.data?.detail || '提取失败')
    } finally {
      setExtractOutfitLoading(false)
    }
  }

  const handleSaveOutfitDescription = async (record: Outfit) => {
    if (!editingOutfitDescription) return
    try {
      await updateOutfit(projectId, worldId, record.id, { description: editingOutfitDescription.description })
      message.success('描述更新成功')
      setEditingOutfitDescription(null)
      fetchOutfits(projectId, worldId)
    } catch (e: any) {
      message.error(e.response?.data?.detail || '更新失败')
    }
  }

  const handleGenerateOutfitImage = async (record: Outfit) => {
    setGeneratingOutfitImage(record.id)
    try {
      await generateOutfitImage(projectId, worldId, record.id)
      message.success(`服装「${record.name}」图片生成成功`)
    } catch (e: any) {
      message.error(e.response?.data?.detail || '生成失败')
    } finally {
      setGeneratingOutfitImage(null)
    }
  }

  const handleCreateOutfit = async (values: any) => {
    try {
      if (editingOutfit) {
        await updateOutfit(projectId, worldId, editingOutfit.id, values)
        message.success('服装更新成功')
      } else {
        await createOutfit(projectId, worldId, values)
        message.success('服装创建成功')
      }
      setOutfitModalOpen(false)
      setEditingOutfit(null)
      outfitForm.resetFields()
      fetchOutfits(projectId, worldId)
    } catch {
      message.error('操作失败')
    }
  }

  const handleEditOutfit = (outfit: Outfit) => {
    setEditingOutfit(outfit)
    outfitForm.setFieldsValue(outfit)
    setOutfitModalOpen(true)
  }

  const handleDeleteOutfit = (outfitId: string) => {
    Modal.confirm({
      title: '确认删除',
      content: '确定要删除该服装吗？',
      okType: 'danger',
      onOk: async () => {
        try {
          await deleteOutfit(projectId, worldId, outfitId)
          message.success('删除成功')
          fetchOutfits(projectId, worldId)
        } catch {
          message.error('删除失败')
        }
      },
    })
  }

  const outfitColumns = [
    {
      title: '服装图片',
      key: 'image',
      width: 120,
      render: (_: any, record: Outfit) => {
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
      title: '服装信息',
      key: 'info',
      width: 180,
      render: (_: any, record: Outfit) => (
        <div>
          <div style={{ fontSize: 14, fontWeight: 600 }}>{record.name}</div>
          <Space wrap size={4} style={{ marginTop: 4 }}>
            {record.style && <Tag>{record.style}</Tag>}
            {record.belongs_to_character && <Tag color="orange">{record.belongs_to_character}</Tag>}
          </Space>
        </div>
      ),
    },
    {
      title: '服装描述',
      key: 'description',
      render: (_: any, record: Outfit) => {
        const isEditing = editingOutfitDescription?.id === record.id
        if (isEditing) {
          return (
            <div>
              <TextArea
                rows={3}
                value={editingOutfitDescription!.description}
                onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setEditingOutfitDescription({ ...editingOutfitDescription!, description: e.target.value })}
                style={{ marginBottom: 8 }}
              />
              <Space>
                <Button size="small" icon={<SaveOutlined />} onClick={() => handleSaveOutfitDescription(record)}>
                  保存
                </Button>
                <Button size="small" onClick={() => setEditingOutfitDescription(null)}>
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
                onClick={() => setEditingOutfitDescription({ id: record.id, description: record.description || '' })}
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
      render: (_: any, record: Outfit) => (
        <Space>
          <Button size="small" icon={<EditOutlined />} onClick={() => handleEditOutfit(record)}>
            编辑
          </Button>
          <Button
            size="small"
            loading={generatingOutfitImage === record.id}
            onClick={() => handleGenerateOutfitImage(record)}
          >
            生成图片
          </Button>
          <Button size="small" danger icon={<DeleteOutlined />} onClick={() => handleDeleteOutfit(record.id)}>
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
            onClick={() => { outfitForm.resetFields(); setOutfitModalOpen(true); }}
          >
            添加服装
          </Button>
          <Button
            type="primary"
            icon={<PictureOutlined />}
            loading={extractOutfitLoading}
            onClick={handleExtractOutfits}
          >
            一键提取服装
          </Button>
        </Space>
      </div>
      {outfits.length === 0 ? (
        <EmptyState description="暂无服装" />
      ) : (
        <Table dataSource={outfits} columns={outfitColumns} rowKey="id" pagination={{ pageSize: 10 }} scroll={{ x: 800 }} />
      )}

      <Modal title={editingOutfit ? '编辑服装' : '添加服装'} open={outfitModalOpen} onCancel={() => { setOutfitModalOpen(false); setEditingOutfit(null); }} footer={null} destroyOnClose>
        <Form form={outfitForm} layout="vertical" onFinish={handleCreateOutfit}>
          <Form.Item name="name" label="名称" rules={[{ required: true }]}>
            <Input placeholder="如：贵族礼服、战士铠甲" />
          </Form.Item>
          <Form.Item name="style" label="风格">
            <Select allowClear options={OUTFIT_STYLE_OPTIONS} placeholder="选择服装风格" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item name="belongs_to_character" label="归属角色">
            <Input placeholder="输入角色名称" />
          </Form.Item>
          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit">保存</Button>
              <Button onClick={() => { setOutfitModalOpen(false); setEditingOutfit(null); }}>取消</Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
