import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Button,
  Space,
  Card,
  Tag,
  Tabs,
  Modal,
  Form,
  Input,
  Select,
  message,
  Typography,
  Descriptions,
  Image,
} from 'antd'
import { ArrowLeftOutlined, EditOutlined, DeleteOutlined, GlobalOutlined } from '@ant-design/icons'
import { useWorldStore } from '../../stores/worldStore'
import EmptyState from '../../components/common/EmptyState'
import Loading from '../../components/common/Loading'
import { formatDate } from '../../utils/format'
import SceneAssetTab from './components/SceneAssetTab'
import PropTab from './components/PropTab'
import BuildingTab from './components/BuildingTab'
import OutfitTab from './components/OutfitTab'
import StyleTemplateTab from './components/StyleTemplateTab'

const { Title } = Typography
const { TextArea } = Input

const ERA_TYPE_OPTIONS = [
  { label: '古代', value: '古代' }, { label: '中世纪', value: '中世纪' },
  { label: '近代', value: '近代' }, { label: '现代', value: '现代' },
  { label: '未来', value: '未来' }, { label: '奇幻', value: '奇幻' },
]
const REGION_STYLE_OPTIONS = [
  { label: '东方', value: '东方' }, { label: '西方', value: '西方' },
  { label: '架空', value: '架空' }, { label: '科幻', value: '科幻' },
]
const CIVILIZATION_OPTIONS = [
  { label: '原始', value: '原始' }, { label: '农业', value: '农业' },
  { label: '工业', value: '工业' }, { label: '信息', value: '信息' },
  { label: '星际', value: '星际' },
]

export default function WorldDetail() {
  const { id: projectId, worldId } = useParams<{ id: string; worldId: string }>()
  const navigate = useNavigate()

  const {
    currentWorld,
    loading,
    fetchWorld,
    updateWorld,
    deleteWorld,
    fetchSceneAssets,
    fetchProps,
    fetchBuildings,
    fetchOutfits,
    fetchTemplates,
  } = useWorldStore()

  const [editModalOpen, setEditModalOpen] = useState(false)
  const [editForm] = Form.useForm()
  const [editLoading, setEditLoading] = useState(false)

  useEffect(() => {
    if (projectId && worldId) {
      fetchWorld(projectId, worldId)
      fetchSceneAssets(projectId, worldId)
      fetchProps(projectId, worldId)
      fetchBuildings(projectId, worldId)
      fetchOutfits(projectId, worldId)
      fetchTemplates(projectId)
    }
  }, [projectId, worldId])

  const handleEdit = async (values: any) => {
    if (!projectId || !worldId) return
    setEditLoading(true)
    try {
      await updateWorld(projectId, worldId, values)
      message.success('世界观更新成功')
      setEditModalOpen(false)
      fetchWorld(projectId, worldId)
    } catch {
      message.error('更新失败')
    } finally {
      setEditLoading(false)
    }
  }

  const handleDelete = () => {
    if (!projectId || !worldId) return
    Modal.confirm({
      title: '确认删除',
      content: '确定要删除该世界观吗？此操作不可恢复。',
      okText: '确认删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        try {
          await deleteWorld(projectId, worldId)
          message.success('删除成功')
          navigate(`/projects/${projectId}/worlds`)
        } catch {
          message.error('删除失败')
        }
      },
    })
  }

  if (loading && !currentWorld) {
    return <Loading tip="加载世界观详情..." />
  }

  if (!currentWorld) {
    return <EmptyState description="世界观不存在" />
  }

  const tabItems = projectId && worldId ? [
    {
      key: 'scene-assets',
      label: '场景资产',
      children: <SceneAssetTab projectId={projectId} worldId={worldId} />,
    },
    {
      key: 'props',
      label: '道具',
      children: <PropTab projectId={projectId} worldId={worldId} />,
    },
    {
      key: 'buildings',
      label: '建筑',
      children: <BuildingTab projectId={projectId} worldId={worldId} />,
    },
    {
      key: 'outfits',
      label: '服装',
      children: <OutfitTab projectId={projectId} worldId={worldId} />,
    },
    {
      key: 'templates',
      label: '风格模板',
      children: <StyleTemplateTab projectId={projectId} />,
    },
  ] : []

  return (
    <div>
      <Space style={{ marginBottom: 16 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(`/projects/${projectId}/worlds`)}>
          返回
        </Button>
      </Space>

      <Card style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Space>
            {currentWorld.cover_image ? (
              <Image src={currentWorld.cover_image} alt={currentWorld.name} width={80} height={80} style={{ borderRadius: 8, objectFit: 'cover' }} />
            ) : (
              <GlobalOutlined style={{ fontSize: 48, color: '#1677ff' }} />
            )}
            <div>
              <Title level={4} style={{ margin: 0 }}>
                {currentWorld.name}
              </Title>
              <Space wrap size={4} style={{ marginTop: 4 }}>
                {currentWorld.era_type && <Tag color="blue">{currentWorld.era_type}</Tag>}
                {currentWorld.region_style && <Tag color="green">{currentWorld.region_style}</Tag>}
                {currentWorld.civilization_level && <Tag color="purple">{currentWorld.civilization_level}</Tag>}
                {currentWorld.era && <Tag>{currentWorld.era}</Tag>}
              </Space>
            </div>
          </Space>
          <Space>
            <Button icon={<EditOutlined />} onClick={() => { editForm.setFieldsValue(currentWorld); setEditModalOpen(true); }}>
              编辑
            </Button>
            <Button danger icon={<DeleteOutlined />} onClick={handleDelete}>
              删除
            </Button>
          </Space>
        </div>
        {currentWorld.description && (
          <div style={{ marginTop: 12, color: '#666' }}>{currentWorld.description}</div>
        )}
        <Descriptions size="small" column={2} style={{ marginTop: 12 }}>
          {currentWorld.time_span && <Descriptions.Item label="时间跨度">{currentWorld.time_span}</Descriptions.Item>}
          {currentWorld.background && <Descriptions.Item label="背景描述" span={2}>{currentWorld.background}</Descriptions.Item>}
          {currentWorld.core_tags && currentWorld.core_tags.length > 0 && (
            <Descriptions.Item label="核心设定" span={2}>
              <Space wrap>{currentWorld.core_tags.map((t, i) => <Tag key={i}>{t}</Tag>)}</Space>
            </Descriptions.Item>
          )}
        </Descriptions>
        <div style={{ marginTop: 8, fontSize: 12, color: '#999' }}>
          创建于 {formatDate(currentWorld.created_at)}
        </div>
      </Card>

      <Tabs items={tabItems} />

      {/* ===== 编辑世界观 Modal ===== */}
      <Modal title="编辑世界观" open={editModalOpen} onCancel={() => setEditModalOpen(false)} footer={null} width={720}>
        <Form form={editForm} layout="vertical" onFinish={handleEdit}>
          <Form.Item name="name" label="世界观名称" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Space style={{ width: '100%' }} size="large">
            <Form.Item name="era_type" label="年代类型">
              <Select allowClear style={{ width: 180 }} options={ERA_TYPE_OPTIONS} />
            </Form.Item>
            <Form.Item name="time_span" label="时间跨度">
              <Input placeholder="如：公元前1000年-公元1000年" style={{ width: 250 }} />
            </Form.Item>
          </Space>
          <Form.Item name="background" label="背景描述">
            <TextArea rows={2} />
          </Form.Item>
          <Space style={{ width: '100%' }} size="large">
            <Form.Item name="region_style" label="地域风格">
              <Select allowClear style={{ width: 180 }} options={REGION_STYLE_OPTIONS} />
            </Form.Item>
            <Form.Item name="civilization_level" label="文明水平">
              <Select allowClear style={{ width: 180 }} options={CIVILIZATION_OPTIONS} />
            </Form.Item>
          </Space>
          <Form.Item name="core_tags" label="核心设定标签">
            <Select mode="tags" placeholder="输入标签后回车" tokenSeparators={[',']} />
          </Form.Item>
          <Form.Item name="era" label="时代/纪元">
            <Input />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={4} />
          </Form.Item>
          <Form.Item name="cover_image" label="封面图URL">
            <Input placeholder="输入封面图片URL地址" />
          </Form.Item>
          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit" loading={editLoading}>保存</Button>
              <Button onClick={() => setEditModalOpen(false)}>取消</Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
