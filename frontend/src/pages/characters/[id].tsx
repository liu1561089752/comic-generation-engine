import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Button,
  Descriptions,
  Space,
  Card,
  Tag,
  Tabs,
  Table,
  Modal,
  Form,
  Input,
  message,
  Typography,
  Row,
  Col,
  Upload,
  Avatar,
  Select,
  Image,
  Divider,
} from 'antd'
import {
  ArrowLeftOutlined,
  EditOutlined,
  DeleteOutlined,
  PlusOutlined,
  TeamOutlined,
  UploadOutlined,
  SmileOutlined,
  PictureOutlined,
} from '@ant-design/icons'
import ReactEChartsCore from 'echarts-for-react'
import { useCharacterStore } from '../../stores/characterStore'
import { EXPRESSION_TYPE_MAP } from '../../types/character'
import type { Character, CharacterState, CharacterExpression } from '../../types/character'
import { characterApi } from '../../api/characterApi'
import CharacterForm from '../../components/CharacterForm'
import EmptyState from '../../components/common/EmptyState'
import Loading from '../../components/common/Loading'
import { formatDate } from '../../utils/format'

const { Title, Text } = Typography
const { TextArea } = Input

export default function CharacterDetail() {
  const { id: projectId, characterId } = useParams<{ id: string; characterId: string }>()
  const navigate = useNavigate()

  const {
    currentCharacter,
    relations,
    outfits,
    expressions,
    loading,
    fetchCharacter,
    updateCharacter,
    deleteCharacter,
    fetchRelations,
    createRelation,
    fetchOutfits,
    createOutfit,
    fetchExpressions,
    createExpression,
    updateExpression,
    deleteExpression,
  } = useCharacterStore()

  const [editModalOpen, setEditModalOpen] = useState(false)
  const [editLoading, setEditLoading] = useState(false)
  const [configEditModalOpen, setConfigEditModalOpen] = useState(false)
  const [configForm] = Form.useForm()
  const [relationModalOpen, setRelationModalOpen] = useState(false)
  const [outfitModalOpen, setOutfitModalOpen] = useState(false)
  const [expressionModalOpen, setExpressionModalOpen] = useState(false)
  const [editingExpression, setEditingExpression] = useState<CharacterExpression | null>(null)
  const [generatingStateId, setGeneratingStateId] = useState<string | null>(null)
  const [stateImageMap, setStateImageMap] = useState<Record<string, string>>({})
  const [relationForm] = Form.useForm()
  const [outfitForm] = Form.useForm()
  const [expressionForm] = Form.useForm()
  const [allCharacters, setAllCharacters] = useState<Character[]>([])

  const charNameMap: Record<string, string> = {}
  allCharacters.forEach((c) => {
    charNameMap[c.id] = c.name
  })

  useEffect(() => {
    if (projectId && characterId) {
      fetchCharacter(projectId, characterId)
      fetchRelations(projectId, characterId)
      fetchOutfits(projectId, characterId)
      fetchExpressions(projectId, characterId)
      characterApi.list(projectId).then((res: any) => {
        setAllCharacters(res.data?.items || res.data || [])
      }).catch((e) => console.error('获取角色列表失败:', e))
    }
  }, [projectId, characterId])

  useEffect(() => {
    if (currentCharacter) {
      configForm.setFieldsValue({ name: currentCharacter.name, aliases: currentCharacter.aliases || '', description: currentCharacter.description || '' })
    }
  }, [currentCharacter])

  const handleEdit = async (values: any) => {
    if (!projectId || !characterId) return
    setEditLoading(true)
    try {
      await updateCharacter(projectId, characterId, values)
      message.success('人物信息更新成功')
      setEditModalOpen(false)
      fetchCharacter(projectId, characterId)
    } catch {
      message.error('更新失败')
    } finally {
      setEditLoading(false)
    }
  }

  const handleConfigEdit = async (values: any) => {
    if (!projectId || !characterId) return
    try {
      await updateCharacter(projectId, characterId, values)
      message.success('角色配置更新成功')
      setConfigEditModalOpen(false)
      fetchCharacter(projectId, characterId)
    } catch {
      message.error('更新失败')
    }
  }

  const handleDelete = () => {
    if (!projectId || !characterId) return
    Modal.confirm({
      title: '确认删除',
      content: '确定要删除该人物吗？此操作不可恢复。',
      okText: '确认删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        try {
          await deleteCharacter(projectId, characterId)
          message.success('删除成功')
          navigate(`/projects/${projectId}/characters`)
        } catch {
          message.error('删除失败')
        }
      },
    })
  }

  const handleCreateRelation = async (values: any) => {
    if (!projectId || !characterId) return
    try {
      await createRelation(projectId, characterId, values)
      message.success('关系创建成功')
      setRelationModalOpen(false)
      relationForm.resetFields()
      fetchRelations(projectId, characterId)
    } catch {
      message.error('创建失败')
    }
  }

  const handleCreateOutfit = async (values: any) => {
    if (!projectId || !characterId) return
    try {
      await createOutfit(projectId, characterId, values)
      message.success('服装添加成功')
      setOutfitModalOpen(false)
      outfitForm.resetFields()
      fetchOutfits(projectId, characterId)
    } catch {
      message.error('添加失败')
    }
  }

  const handleCreateExpression = async (values: any) => {
    if (!projectId || !characterId) return
    try {
      if (editingExpression) {
        await updateExpression(projectId, characterId, editingExpression.id, values)
        message.success('表情更新成功')
      } else {
        await createExpression(projectId, characterId, values)
        message.success('表情添加成功')
      }
      setExpressionModalOpen(false)
      setEditingExpression(null)
      expressionForm.resetFields()
      fetchExpressions(projectId, characterId)
    } catch {
      message.error('操作失败')
    }
  }

  const handleEditExpression = (expression: CharacterExpression) => {
    setEditingExpression(expression)
    expressionForm.setFieldsValue(expression)
    setExpressionModalOpen(true)
  }

  const handleDeleteExpression = (expressionId: string) => {
    if (!projectId || !characterId) return
    Modal.confirm({
      title: '确认删除',
      content: '确定要删除该表情吗？',
      okType: 'danger',
      onOk: async () => {
        try {
          await deleteExpression(projectId, characterId, expressionId)
          message.success('删除成功')
          fetchExpressions(projectId, characterId)
        } catch {
          message.error('删除失败')
        }
      },
    })
  }

  const handleGenerateStateImage = async (stateId: string) => {
    if (!projectId || !characterId) return
    setGeneratingStateId(stateId)
    try {
      const res: any = await characterApi.generateStateImage(projectId, characterId, stateId)
      const stateName = res.data?.state_name || ''
      const imageUrl = res.data?.image_url || ''
      setStateImageMap((prev) => ({ ...prev, [stateId]: imageUrl }))
      message.success(`状态「${stateName}」形象生成成功`)
      fetchCharacter(projectId, characterId)
    } catch (e: any) {
      message.error(e.response?.data?.detail || '生成失败')
    } finally {
      setGeneratingStateId(null)
    }
  }

  const getGraphOption = () => {
    const nodes: any[] = []
    const links: any[] = []

    if (currentCharacter) {
      nodes.push({
        id: currentCharacter.id,
        name: currentCharacter.name,
        symbolSize: 60,
        itemStyle: { color: '#1677ff' },
      })
    }

    const addedIds = new Set<string>()
    addedIds.add(currentCharacter?.id || '')

    relations.forEach((rel) => {
      const targetId = rel.character_b_id
      if (!addedIds.has(targetId)) {
        nodes.push({
          id: targetId,
          name: charNameMap[targetId] || rel.relation_type_b_to_a || targetId,
          symbolSize: 40,
          itemStyle: { color: '#1677ff' },
        })
        addedIds.add(targetId)
      }
      links.push({
        source: currentCharacter?.id || '',
        target: targetId,
        label: { show: true, formatter: rel.relation_type_a_to_b },
      })
    })

    return {
      title: { show: false },
      tooltip: { show: true },
      series: [
        {
          type: 'graph',
          layout: 'force',
          force: {
            repulsion: 300,
            edgeLength: 150,
          },
          roam: true,
          draggable: true,
          data: nodes,
          links,
          categories: [{ name: '当前人物' }, { name: '关联人物' }],
          label: {
            show: true,
            position: 'bottom',
            fontSize: 12,
          },
          edgeSymbol: ['circle', 'arrow'],
          edgeSymbolSize: [4, 10],
          lineStyle: {
            color: '#999',
            width: 2,
            curveness: 0.2,
          },
        },
      ],
    }
  }

  if (loading && !currentCharacter) {
    return <Loading tip="加载人物详情..." />
  }

  if (!currentCharacter) {
    return <EmptyState description="人物不存在" />
  }

  const relationColumns = [
    {
      title: '关联角色',
      dataIndex: 'character_b_id',
      key: 'character_b_id',
      render: (id: string) => charNameMap[id] || id.slice(0, 8),
    },
    {
      title: '关系类型（本角色→对方）',
      dataIndex: 'relation_type_a_to_b',
      key: 'relation_type_a_to_b',
    },
    {
      title: '关系类型（对方→本角色）',
      dataIndex: 'relation_type_b_to_a',
      key: 'relation_type_b_to_a',
      render: (val: string) => val || '-',
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
      render: (val?: string) => val || '-',
    },
  ]

  const outfitColumns = [
    {
      title: '服装名称',
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: '类型',
      dataIndex: 'outfit_type',
      key: 'outfit_type',
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
    },
    {
      title: '色系',
      dataIndex: 'color_scheme',
      key: 'color_scheme',
      render: (colors?: string[]) =>
        colors?.map((c, i) => <Tag key={i}>{c}</Tag>) || '-',
    },
    {
      title: '场景标签',
      dataIndex: 'scene_tags',
      key: 'scene_tags',
      render: (tags?: string[]) =>
        tags?.map((t, i) => <Tag key={i}>{t}</Tag>) || '-',
    },
  ]

  const expressionColumns = [
    {
      title: '表情名称',
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: '类型',
      dataIndex: 'expression_type',
      key: 'expression_type',
      render: (v?: string) => v ? <Tag color="purple">{EXPRESSION_TYPE_MAP[v] || v}</Tag> : '-',
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
      render: (v?: string) => v || '-',
    },
    {
      title: '参考图',
      dataIndex: 'reference_image_url',
      key: 'reference_image_url',
      render: (v?: string) => v ? <Image src={v} alt="表情参考" width={60} height={60} style={{ objectFit: 'cover', borderRadius: 4 }} /> : '-',
    },
    {
      title: '操作',
      key: 'action',
      width: 160,
      render: (_: any, record: CharacterExpression) => (
        <Space>
          <Button size="small" icon={<EditOutlined />} onClick={() => handleEditExpression(record)}>编辑</Button>
          <Button size="small" danger icon={<DeleteOutlined />} onClick={() => handleDeleteExpression(record.id)}>删除</Button>
        </Space>
      ),
    },
  ]

  const tabItems = [
    {
      key: 'info',
      label: '基本信息',
      children: (
        <Card>
          <Descriptions column={2} bordered size="small">
            <Descriptions.Item label="姓名" span={2}>
              <Title level={5} style={{ margin: 0 }}>
                {currentCharacter.name}
              </Title>
            </Descriptions.Item>
            <Descriptions.Item label="状态">
              <Tag>{currentCharacter.status}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="创建时间">
              {formatDate(currentCharacter.created_at)}
            </Descriptions.Item>
            <Descriptions.Item label="更新时间">
              {formatDate(currentCharacter.updated_at)}
            </Descriptions.Item>
          </Descriptions>
          {currentCharacter.states && currentCharacter.states.length > 0 && (
            <>
              <Divider />
              <div>
                <div style={{ fontWeight: 600, marginBottom: 12, fontSize: 14 }}>角色状态（年龄/身份阶段）</div>
                <Space direction="vertical" size={8} style={{ width: '100%' }}>
                  {currentCharacter.states.map((s: CharacterState) => {
                    const stateImgUrl = s.image_url || stateImageMap[s.id]
                    return (
                      <Card key={s.id} size="small" style={{ background: '#fafafa' }}>
                        <Space direction="vertical" size={2} style={{ width: '100%' }}>
                          <Space>
                            <Tag color="blue">{s.name}</Tag>
                            {s.sort_order && <Tag color="default">{s.sort_order}</Tag>}
                          </Space>
                          {stateImgUrl && (
                            <div style={{ marginBottom: 8 }}>
                              <Image
                                src={stateImgUrl}
                                alt={s.name}
                                width={120}
                                height={68}
                                style={{ objectFit: 'cover', borderRadius: 4 }}
                                preview={{ src: stateImgUrl }}
                              />
                            </div>
                          )}
                          {s.description && (
                            <div style={{ fontSize: 13, color: '#666', lineHeight: 1.6, whiteSpace: 'pre-wrap' }}>
                              {s.description}
                            </div>
                          )}
                          <Button
                            size="small"
                            icon={<PictureOutlined />}
                            loading={generatingStateId === s.id}
                            onClick={() => handleGenerateStateImage(s.id)}
                          >
                            生成形象
                          </Button>
                        </Space>
                      </Card>
                    )
                  })}
                </Space>
              </div>
            </>
          )}
        </Card>
      ),
    },
    {
      key: 'config',
      label: '角色配置',
      children: (
        <div>
          <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 16 }}>
            <Button
              type="primary"
              icon={<EditOutlined />}
              onClick={() => setConfigEditModalOpen(true)}
            >
              编辑配置
            </Button>
          </div>
          <Card title="角色配置 JSON">
            <pre style={{ whiteSpace: 'pre-wrap', fontSize: 13, lineHeight: 1.6, maxHeight: 500, overflow: 'auto' }}>
              {JSON.stringify(currentCharacter, null, 2)}
            </pre>
          </Card>
          <Card title="配置详情" style={{ marginTop: 16 }}>
            <Space direction="vertical" size="large" style={{ width: '100%' }}>
              <div>
                <strong>角色姓名：</strong>
                <Text>{currentCharacter.name || '-'}</Text>
              </div>
              <div>
                <strong>别名：</strong>
                <Text>{currentCharacter.aliases || '-'}</Text>
              </div>
              <div>
                <strong>描述：</strong>
                <div style={{ marginTop: 8 }}>
                  <Text style={{ whiteSpace: 'pre-wrap', lineHeight: 1.8 }}>
                    {currentCharacter.description || '-'}
                  </Text>
                </div>
              </div>
            </Space>
          </Card>
        </div>
      ),
    },
    {
      key: 'relations',
      label: '人物关系',
      children: (
        <div>
          <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 16 }}>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => setRelationModalOpen(true)}
            >
              添加关系
            </Button>
          </div>
          <Card title="关系图" style={{ marginBottom: 16 }}>
            {relations.length > 0 ? (
              <ReactEChartsCore
                option={getGraphOption()}
                style={{ height: 400 }}
                notMerge
              />
            ) : (
              <EmptyState description="暂无关系数据" />
            )}
          </Card>
          <Card title="关系列表">
            {relations.length === 0 ? (
              <EmptyState description="暂无关系数据" />
            ) : (
              <Table
                dataSource={relations}
                columns={relationColumns}
                rowKey="id"
                pagination={false}
                size="small"
              />
            )}
          </Card>
        </div>
      ),
    },
    {
      key: 'outfits',
      label: '服装库',
      children: (
        <div>
          <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 16 }}>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => setOutfitModalOpen(true)}
            >
              添加服装
            </Button>
          </div>
          {outfits.length === 0 ? (
            <EmptyState description="暂无服装数据" />
          ) : (
            <Table
              dataSource={outfits}
              columns={outfitColumns}
              rowKey="id"
              pagination={false}
              size="small"
            />
          )}
        </div>
      ),
    },
    {
      key: 'expressions',
      label: '表情库',
      children: (
        <div>
          <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 16 }}>
            <Button
              type="primary"
              icon={<SmileOutlined />}
              onClick={() => { setEditingExpression(null); expressionForm.resetFields(); setExpressionModalOpen(true); }}
            >
              添加表情
            </Button>
          </div>
          {expressions.length === 0 ? (
            <EmptyState description="暂无表情数据" />
          ) : (
            <Table
              dataSource={expressions}
              columns={expressionColumns}
              rowKey="id"
              pagination={false}
              size="small"
            />
          )}
        </div>
      ),
    },
    {
      key: 'references',
      label: '参考图',
      children: (
        <div>
          <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 16 }}>
            <Upload
              action={`/api/v1/projects/${projectId}/characters/${characterId}/references`}
              headers={{
                Authorization: `Bearer ${localStorage.getItem('access_token')}`,
              }}
              showUploadList={{ showPreviewIcon: true }}
            >
              <Button type="primary" icon={<UploadOutlined />}>
                上传参考图
              </Button>
            </Upload>
          </div>
          <Row gutter={[16, 16]}>
            {[1, 2, 3, 4, 5, 6].map((i) => (
              <Col key={i} xs={12} sm={8} md={6} lg={4}>
                <Card
                  size="small"
                  title={['正面', '侧面', '背面', '面部特写', '全身', '动作'][i - 1]}
                >
                  <div
                    style={{
                      height: 160,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      background: '#f5f5f5',
                      borderRadius: 4,
                      color: '#999',
                      fontSize: 12,
                    }}
                  >
                    暂无参考图
                  </div>
                </Card>
              </Col>
            ))}
          </Row>
        </div>
      ),
    },
  ]

  return (
    <div>
      <Space style={{ marginBottom: 16 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(-1)}>
          返回
        </Button>
      </Space>

      <Card style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Space>
            <Avatar
              size={48}
              icon={<TeamOutlined />}
              style={{ backgroundColor: '#1677ff' }}
            />
            <div>
              <Title level={4} style={{ margin: 0 }}>
                {currentCharacter.name}
              </Title>
            </div>
          </Space>
          <Space>
            <Button icon={<EditOutlined />} onClick={() => setEditModalOpen(true)}>
              编辑
            </Button>
            <Button danger icon={<DeleteOutlined />} onClick={handleDelete}>
              删除
            </Button>
          </Space>
        </div>
      </Card>

      <Tabs items={tabItems} />

      <Modal
        title="编辑人物信息"
        open={editModalOpen}
        onCancel={() => setEditModalOpen(false)}
        footer={null}
        width={640}
      >
        <CharacterForm
          initialValues={{ name: currentCharacter.name }}
          loading={editLoading}
          onSubmit={handleEdit}
          onCancel={() => setEditModalOpen(false)}
        />
      </Modal>

      <Modal
        title="编辑角色配置"
        open={configEditModalOpen}
        onCancel={() => setConfigEditModalOpen(false)}
        footer={null}
        width={700}
      >
        <Form form={configForm} layout="vertical" onFinish={handleConfigEdit}>
          <Form.Item
            name="name"
            label="角色姓名"
            rules={[{ required: true, message: '请输入角色姓名' }]}
          >
            <Input placeholder="角色姓名" />
          </Form.Item>
          <Form.Item
            name="aliases"
            label="别名"
          >
            <Input placeholder="多个别名用逗号分隔，如：南星,小姜,姜小姐" />
          </Form.Item>
          <Form.Item
            name="description"
            label="描述"
          >
            <TextArea rows={10} placeholder="详细描述角色的外观特征、气质等" />
          </Form.Item>
          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit">
                保存配置
              </Button>
              <Button onClick={() => setConfigEditModalOpen(false)}>取消</Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="添加人物关系"
        open={relationModalOpen}
        onCancel={() => setRelationModalOpen(false)}
        footer={null}
      >
        <Form form={relationForm} layout="vertical" onFinish={handleCreateRelation}>
          <Form.Item
            name="character_b_id"
            label="目标角色"
            rules={[{ required: true, message: '请选择目标角色' }]}
          >
            <Select
              placeholder="选择关联的角色"
              showSearch
              optionFilterProp="label"
              options={allCharacters
                .filter((c) => c.id !== characterId)
                .map((c) => ({ label: c.name, value: c.id }))}
            />
          </Form.Item>
          <Form.Item
            name="relation_type_a_to_b"
            label="本角色对对方的关系"
            rules={[{ required: true, message: '请输入关系类型' }]}
          >
            <Input placeholder="如：朋友、敌人" />
          </Form.Item>
          <Form.Item
            name="relation_type_b_to_a"
            label="对方对本角色的关系"
            rules={[{ required: true, message: '请输入关系类型' }]}
          >
            <Input placeholder="如：朋友、敌人" />
          </Form.Item>
          <Form.Item name="description" label="关系描述">
            <Input.TextArea rows={2} placeholder="可选" />
          </Form.Item>
          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit">
                创建
              </Button>
              <Button onClick={() => setRelationModalOpen(false)}>取消</Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="添加服装"
        open={outfitModalOpen}
        onCancel={() => setOutfitModalOpen(false)}
        footer={null}
      >
        <Form form={outfitForm} layout="vertical" onFinish={handleCreateOutfit}>
          <Form.Item
            name="name"
            label="服装名称"
            rules={[{ required: true, message: '请输入服装名称' }]}
          >
            <Input placeholder="如：日常装、战斗服" />
          </Form.Item>
          <Form.Item
            name="outfit_type"
            label="服装类型"
            rules={[{ required: true, message: '请选择服装类型' }]}
          >
            <Select
              placeholder="选择类型"
              options={[
                { label: '日常装', value: '日常装' },
                { label: '战斗服', value: '战斗服' },
                { label: '礼服', value: '礼服' },
                { label: '校服', value: '校服' },
                { label: '泳装', value: '泳装' },
                { label: '古装', value: '古装' },
                { label: '其他', value: '其他' },
              ]}
            />
          </Form.Item>
          <Form.Item
            name="description"
            label="服装描述"
            rules={[{ required: true, message: '请输入服装描述' }]}
          >
            <Input.TextArea rows={2} placeholder="描述服装的样式、材质等" />
          </Form.Item>
          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit">
                添加
              </Button>
              <Button onClick={() => setOutfitModalOpen(false)}>取消</Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={editingExpression ? '编辑表情' : '添加表情'}
        open={expressionModalOpen}
        onCancel={() => { setExpressionModalOpen(false); setEditingExpression(null); }}
        footer={null}
        destroyOnClose
      >
        <Form form={expressionForm} layout="vertical" onFinish={handleCreateExpression}>
          <Form.Item
            name="name"
            label="表情名称"
            rules={[{ required: true, message: '请输入表情名称' }]}
          >
            <Input placeholder="如：开心笑脸、愤怒表情" />
          </Form.Item>
          <Form.Item
            name="expression_type"
            label="表情类型"
          >
            <Select
              placeholder="选择表情类型"
              allowClear
              options={Object.entries(EXPRESSION_TYPE_MAP).map(([value, label]) => ({
                label,
                value,
              }))}
            />
          </Form.Item>
          <Form.Item
            name="description"
            label="表情描述"
          >
            <Input.TextArea rows={2} placeholder="描述表情的细节特征" />
          </Form.Item>
          <Form.Item
            name="reference_image_url"
            label="参考图URL"
          >
            <Input placeholder="表情参考图片URL地址" />
          </Form.Item>
          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit">
                {editingExpression ? '保存' : '添加'}
              </Button>
              <Button onClick={() => { setExpressionModalOpen(false); setEditingExpression(null); }}>取消</Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
