import { useState } from 'react'
import { Button, Space, Table, Tag, Modal, Form, Input, Select, Image, message } from 'antd'
import { EditOutlined, DeleteOutlined, PlusOutlined, PictureOutlined, SaveOutlined } from '@ant-design/icons'
import { useWorldStore } from '../../../stores/worldStore'
import EmptyState from '../../../components/common/EmptyState'
import { extractNovelText } from './extractNovelText'
import type { SceneAsset } from '../../../types/world'

const { TextArea } = Input

interface EditingDescription {
  id: string
  description: string
}

interface Props {
  projectId: string
  worldId: string
}

export default function SceneAssetTab({ projectId, worldId }: Props) {
  const {
    sceneAssets,
    fetchSceneAssets,
    createSceneAsset,
    updateSceneAsset,
    deleteSceneAsset,
    aiExtractScenes,
    generateSceneImage,
  } = useWorldStore()

  const [assetModalOpen, setAssetModalOpen] = useState(false)
  const [assetForm] = Form.useForm()
  const [editingAsset, setEditingAsset] = useState<SceneAsset | null>(null)
  const [extractLoading, setExtractLoading] = useState(false)
  const [editingDescription, setEditingDescription] = useState<EditingDescription | null>(null)
  const [generatingImage, setGeneratingImage] = useState<string | null>(null)

  const handleExtractScenes = async () => {
    setExtractLoading(true)
    try {
      const novelText = await extractNovelText(projectId)
      if (!novelText) return
      await aiExtractScenes(projectId, worldId, novelText)
      fetchSceneAssets(projectId, worldId)
    } catch (e: any) {
      message.error(e.response?.data?.detail || '提取失败')
    } finally {
      setExtractLoading(false)
    }
  }

  const handleSaveDescription = async (record: SceneAsset) => {
    if (!editingDescription) return
    try {
      await updateSceneAsset(projectId, worldId, record.id, { description: editingDescription.description })
      message.success('描述更新成功')
      setEditingDescription(null)
      fetchSceneAssets(projectId, worldId)
    } catch (e: any) {
      message.error(e.response?.data?.detail || '更新失败')
    }
  }

  const handleGenerateImage = async (record: SceneAsset) => {
    setGeneratingImage(record.id)
    try {
      await generateSceneImage(projectId, worldId, record.id)
      message.success(`场景「${record.name}」图片生成成功`)
    } catch (e: any) {
      message.error(e.response?.data?.detail || '生成失败')
    } finally {
      setGeneratingImage(null)
    }
  }

  const handleCreateAsset = async (values: any) => {
    try {
      if (editingAsset) {
        await updateSceneAsset(projectId, worldId, editingAsset.id, values)
        message.success('场景资产更新成功')
      } else {
        await createSceneAsset(projectId, worldId, values)
        message.success('场景资产创建成功')
      }
      setAssetModalOpen(false)
      setEditingAsset(null)
      assetForm.resetFields()
      fetchSceneAssets(projectId, worldId)
    } catch {
      message.error('操作失败')
    }
  }

  const handleEditAsset = (asset: SceneAsset) => {
    setEditingAsset(asset)
    assetForm.setFieldsValue(asset)
    setAssetModalOpen(true)
  }

  const handleDeleteAsset = (assetId: string) => {
    Modal.confirm({
      title: '确认删除',
      content: '确定要删除该场景资产吗？',
      okType: 'danger',
      onOk: async () => {
        try {
          await deleteSceneAsset(projectId, worldId, assetId)
          message.success('删除成功')
          fetchSceneAssets(projectId, worldId)
        } catch {
          message.error('删除失败')
        }
      },
    })
  }

  const assetColumns = [
    {
      title: '场景图片',
      key: 'image',
      width: 120,
      render: (_: any, record: SceneAsset) => {
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
      title: '场景信息',
      key: 'info',
      width: 180,
      render: (_: any, record: SceneAsset) => (
        <div>
          <div style={{ fontSize: 14, fontWeight: 600 }}>{record.name}</div>
          <Space wrap size={4} style={{ marginTop: 4 }}>
            {record.season && <Tag>{record.season}</Tag>}
            {record.weather && <Tag>{record.weather}</Tag>}
            {record.time_of_day && <Tag>{record.time_of_day}</Tag>}
          </Space>
        </div>
      ),
    },
    {
      title: '场景描述',
      key: 'description',
      render: (_: any, record: SceneAsset) => {
        const isEditing = editingDescription?.id === record.id
        if (isEditing) {
          return (
            <div>
              <TextArea
                rows={3}
                value={editingDescription!.description}
                onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setEditingDescription({ ...editingDescription!, description: e.target.value })}
                style={{ marginBottom: 8 }}
              />
              <Space>
                <Button size="small" icon={<SaveOutlined />} onClick={() => handleSaveDescription(record)}>
                  保存
                </Button>
                <Button size="small" onClick={() => setEditingDescription(null)}>
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
                onClick={() => setEditingDescription({ id: record.id, description: record.description || '' })}
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
      render: (_: any, record: SceneAsset) => (
        <Space>
          <Button size="small" icon={<EditOutlined />} onClick={() => handleEditAsset(record)}>
            编辑
          </Button>
          <Button
            size="small"
            loading={generatingImage === record.id}
            onClick={() => handleGenerateImage(record)}
          >
            生成图片
          </Button>
          <Button size="small" danger icon={<DeleteOutlined />} onClick={() => handleDeleteAsset(record.id)}>
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
            onClick={() => { setEditingAsset(null); assetForm.resetFields(); setAssetModalOpen(true); }}
          >
            添加场景资产
          </Button>
          <Button
            type="primary"
            icon={<PictureOutlined />}
            loading={extractLoading}
            onClick={handleExtractScenes}
          >
            一键提取场景
          </Button>
        </Space>
      </div>
      {sceneAssets.length === 0 ? (
        <EmptyState description="暂无场景资产" />
      ) : (
        <Table dataSource={sceneAssets} columns={assetColumns} rowKey="id" pagination={{ pageSize: 10 }} scroll={{ x: 800 }} />
      )}

      <Modal title={editingAsset ? '编辑场景资产' : '添加场景资产'} open={assetModalOpen} onCancel={() => { setAssetModalOpen(false); setEditingAsset(null); }} footer={null} width={640}>
        <Form form={assetForm} layout="vertical" onFinish={handleCreateAsset}>
          <Form.Item name="name" label="名称" rules={[{ required: true }]}>
            <Input placeholder="如：森林、海滩" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item name="season" label="季节">
            <Select allowClear options={[
              { label: '春', value: '春' }, { label: '夏', value: '夏' },
              { label: '秋', value: '秋' }, { label: '冬', value: '冬' },
            ]} />
          </Form.Item>
          <Form.Item name="weather" label="天气">
            <Select allowClear options={[
              { label: '晴', value: '晴' }, { label: '阴', value: '阴' },
              { label: '雨', value: '雨' }, { label: '雪', value: '雪' },
            ]} />
          </Form.Item>
          <Form.Item name="time_of_day" label="时段">
            <Select allowClear options={[
              { label: '黎明', value: '黎明' }, { label: '清晨', value: '清晨' },
              { label: '正午', value: '正午' }, { label: '黄昏', value: '黄昏' },
              { label: '夜晚', value: '夜晚' },
            ]} />
          </Form.Item>
          <Form.Item name="lighting" label="光照">
            <Input placeholder="如：柔光、逆光" />
          </Form.Item>
          <Form.Item name="atmosphere" label="氛围">
            <Input placeholder="如：宁静、紧张" />
          </Form.Item>
          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit">保存</Button>
              <Button onClick={() => { setAssetModalOpen(false); setEditingAsset(null); }}>取消</Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
