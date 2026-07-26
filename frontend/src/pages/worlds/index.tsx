import { useEffect, useState } from 'react'
import { Card, Row, Col, Button, Modal, Form, Input, Select, message, Space, Tag } from 'antd'
import { PlusOutlined, GlobalOutlined, RobotOutlined } from '@ant-design/icons'
import { useNavigate, useParams } from 'react-router-dom'
import { useWorldStore } from '../../stores/worldStore'
import type { WorldBuilding } from '../../types/world'
import ProjectFilter from '../../components/common/ProjectFilter'
import EmptyState from '../../components/common/EmptyState'
import Loading from '../../components/common/Loading'
import { formatDate } from '../../utils/format'

const { TextArea } = Input

const ERA_TYPE_OPTIONS = [
  { label: '古代', value: '古代' },
  { label: '中世纪', value: '中世纪' },
  { label: '近代', value: '近代' },
  { label: '现代', value: '现代' },
  { label: '未来', value: '未来' },
  { label: '奇幻', value: '奇幻' },
]

const REGION_STYLE_OPTIONS = [
  { label: '东方', value: '东方' },
  { label: '西方', value: '西方' },
  { label: '架空', value: '架空' },
  { label: '科幻', value: '科幻' },
]

const CIVILIZATION_OPTIONS = [
  { label: '原始', value: '原始' },
  { label: '农业', value: '农业' },
  { label: '工业', value: '工业' },
  { label: '信息', value: '信息' },
  { label: '星际', value: '星际' },
]

export default function WorldList() {
  const navigate = useNavigate()
  const { id: urlProjectId } = useParams<{ id: string }>()
  const [projectId, setProjectId] = useState<string | undefined>(urlProjectId)
  const { worlds, loading, fetchWorlds, createWorld, aiCreateWorld } = useWorldStore()

  const [modalOpen, setModalOpen] = useState(false)
  const [createLoading, setCreateLoading] = useState(false)
  const [aiLoading, setAiLoading] = useState(false)
  const [form] = Form.useForm()

  useEffect(() => {
    setProjectId(urlProjectId)
  }, [urlProjectId])

  useEffect(() => {
    if (projectId) {
      fetchWorlds(projectId)
    }
  }, [projectId, fetchWorlds])

  const handleProjectChange = (newProjectId: string | undefined) => {
    if (newProjectId) {
      navigate(`/projects/${newProjectId}/worlds`, { replace: true })
    }
  }

  const handleCreate = async (values: any) => {
    if (!projectId) return
    setCreateLoading(true)
    try {
      await createWorld(projectId, values)
      message.success('世界观创建成功')
      setModalOpen(false)
      form.resetFields()
      fetchWorlds(projectId)
    } catch {
      message.error('创建失败')
    } finally {
      setCreateLoading(false)
    }
  }

  const handleAiCreate = async () => {
    if (!projectId) return
    setAiLoading(true)
    try {
      // 获取项目小说文本
      const novelRes: any = await import('../../api/novelApi').then(m => m.novelApi.list(projectId))
      const novels = novelRes?.data?.items || []
      if (!novels || novels.length === 0) {
        message.warning('当前项目没有小说，请先上传小说')
        return
      }
      const firstNovel = novels[0]
      let novelText = firstNovel.cleaned_text || firstNovel.raw_text
      if (!novelText) {
        // 列表接口未返回文本内容，获取详情
        const detailRes: any = await import('../../api/novelApi').then(m => m.novelApi.getById(projectId, firstNovel.id))
        const detail = detailRes?.data
        novelText = detail?.cleaned_text || detail?.raw_text
        if (!novelText) {
          message.warning('小说内容为空')
          return
        }
      }

      const world = await aiCreateWorld(projectId, novelText)
      if (world) {
        message.success(`世界观「${world.name}」创建成功`)
        fetchWorlds(projectId)
      }
    } catch {
      message.error('AI创建世界观失败')
    } finally {
      setAiLoading(false)
    }
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <h2 style={{ margin: 0, fontSize: 20, fontWeight: 600 }}>世界观管理</h2>
        {projectId && (
          <Space>
            <Button icon={<RobotOutlined />} loading={aiLoading} onClick={handleAiCreate}>
              AI辅助创建
            </Button>
            <Button type="primary" icon={<PlusOutlined />} onClick={() => { form.resetFields(); setModalOpen(true); }}>
              新建世界观
            </Button>
          </Space>
        )}
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
      ) : loading && worlds.length === 0 ? (
        <Loading tip="加载世界观列表..." />
      ) : worlds.length === 0 ? (
        <EmptyState
          description="暂无世界观，点击按钮创建第一个世界观"
          actionText="新建世界观"
          onAction={() => { form.resetFields(); setModalOpen(true); }}
        />
      ) : (
        <Row gutter={[16, 16]}>
          {worlds.map((world: WorldBuilding) => (
            <Col key={world.id} xs={24} sm={12} md={8} lg={6}>
              <Card
                hoverable
                onClick={() => navigate(`/projects/${projectId}/worlds/${world.id}`)}
                style={{ height: '100%' }}
              >
                <div style={{ textAlign: 'center', marginBottom: 12 }}>
                  {world.cover_image ? (
                    <img src={world.cover_image} alt={world.name} style={{ width: '100%', height: 120, objectFit: 'cover', borderRadius: 4 }} />
                  ) : (
                    <GlobalOutlined style={{ fontSize: 48, color: '#1677ff' }} />
                  )}
                </div>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 4 }}>
                    {world.name}
                  </div>
                  <Space wrap size={4}>
                    {world.era_type && <Tag color="blue">{world.era_type}</Tag>}
                    {world.region_style && <Tag color="green">{world.region_style}</Tag>}
                    {world.era && <Tag>{world.era}</Tag>}
                  </Space>
                  <div
                    style={{
                      marginTop: 8,
                      fontSize: 13,
                      color: '#666',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      display: '-webkit-box',
                      WebkitLineClamp: 2,
                      WebkitBoxOrient: 'vertical',
                    }}
                  >
                    {world.description || '暂无描述'}
                  </div>
                  <div style={{ marginTop: 8, fontSize: 12, color: '#999' }}>
                    创建于 {formatDate(world.created_at, 'YYYY-MM-DD')}
                  </div>
                </div>
              </Card>
            </Col>
          ))}
        </Row>
      )}

      {/* 新建世界观 Modal */}
      <Modal
        title="新建世界观"
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        footer={null}
        width={720}
        destroyOnClose
      >
        <Form form={form} layout="vertical" onFinish={handleCreate}>
          <Form.Item name="name" label="世界观名称" rules={[{ required: true, message: '请输入世界观名称' }]}>
            <Input placeholder="如：星际联邦、魔法大陆" />
          </Form.Item>
          <Space style={{ width: '100%' }} size="large">
            <Form.Item name="era_type" label="年代类型">
              <Select allowClear style={{ width: 180 }} options={ERA_TYPE_OPTIONS} placeholder="选择年代类型" />
            </Form.Item>
            <Form.Item name="time_span" label="时间跨度">
              <Input placeholder="如：公元前1000年-公元1000年" style={{ width: 250 }} />
            </Form.Item>
          </Space>
          <Form.Item name="background" label="背景描述">
            <TextArea rows={2} placeholder="描述世界的历史背景和主要设定" />
          </Form.Item>
          <Space style={{ width: '100%' }} size="large">
            <Form.Item name="region_style" label="地域风格">
              <Select allowClear style={{ width: 180 }} options={REGION_STYLE_OPTIONS} placeholder="选择地域风格" />
            </Form.Item>
            <Form.Item name="civilization_level" label="文明水平">
              <Select allowClear style={{ width: 180 }} options={CIVILIZATION_OPTIONS} placeholder="选择文明水平" />
            </Form.Item>
          </Space>
          <Form.Item name="core_tags" label="核心设定标签">
            <Select mode="tags" placeholder="输入标签后回车" tokenSeparators={[',']} />
          </Form.Item>
          <Form.Item name="era" label="时代/纪元">
            <Input placeholder="如：公元3000年、魔法纪元" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={4} placeholder="描述世界观的基本设定" />
          </Form.Item>
          <Form.Item name="cover_image" label="封面图URL">
            <Input placeholder="输入封面图片URL地址" />
          </Form.Item>
          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit" loading={createLoading}>创建</Button>
              <Button onClick={() => setModalOpen(false)}>取消</Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
