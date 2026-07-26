import { useEffect, useState, useMemo, useCallback } from 'react'
import {
  Table,
  Button,
  Space,
  Modal,
  Form,
  Input,
  Select,
  Tag,
  message,
  Card,
  Row,
  Col,
  Radio,
  Typography,
  Tooltip,
  Popconfirm,
  Empty,
} from 'antd'
import {
  PlusOutlined,
  AppstoreOutlined,
  UnorderedListOutlined,
  BarsOutlined,
  CopyOutlined,
  InboxOutlined,
  DeleteOutlined,
  EyeOutlined,
} from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { useProjectStore } from '../../stores/projectStore'
import { projectApi } from '../../api/projectApi'
import { PROJECT_STATUS_COLOR } from '../../utils/constants'
import { PROJECT_STATUS_MAP, PROJECT_TYPE_MAP } from '../../types'
import { formatDate } from '../../utils/format'
import type { ProjectStatus, ProjectType } from '../../types'
import type { Project } from '../../types/project'
import Loading from '../../components/common/Loading'

const { Text, Title } = Typography

type ViewMode = 'grid' | 'list' | 'compact'

const STATUS_FILTER_OPTIONS = [
  { value: 'all', label: '全部' },
  { value: 'in_progress', label: '制作中' },
  { value: 'completed', label: '已完成' },
  { value: 'archived', label: '已归档' },
]

const TYPE_OPTIONS = Object.entries(PROJECT_TYPE_MAP).map(([value, label]) => ({
  value,
  label,
}))

const SORT_OPTIONS = [
  { value: 'updated_at', label: '更新时间' },
  { value: 'created_at', label: '创建时间' },
  { value: 'name', label: '项目名称' },
  { value: 'completion_percentage', label: '完成度' },
]

const IN_PROGRESS_STATUSES: string[] = ['draft', 'planning', 'generating', 'editing']

export default function ProjectList() {
  const navigate = useNavigate()
  const { projects, loading, total, fetchProjects } = useProjectStore()
  const [createModalOpen, setCreateModalOpen] = useState(false)
  const [createLoading, setCreateLoading] = useState(false)
  const [form] = Form.useForm()

  // 视图、筛选、排序状态
  const [viewMode, setViewMode] = useState<ViewMode>('grid')
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [typeFilter, setTypeFilter] = useState<string>('all')
  const [sortKey, setSortKey] = useState<string>('updated_at')
  const [nameChecking, setNameChecking] = useState(false)

  // 获取所有项目（不传递筛选参数，由前端进行客户端筛选）
  useEffect(() => {
    fetchProjects({ page_size: 999 })
  }, [fetchProjects])

  const handleCreate = async (values: { name: string; description?: string; project_type?: string }) => {
    setCreateLoading(true)
    try {
      await projectApi.create(values)
      message.success('项目创建成功')
      setCreateModalOpen(false)
      form.resetFields()
      fetchProjects({ page_size: 999 })
    } catch {
      message.error('创建失败')
    } finally {
      setCreateLoading(false)
    }
  }

  // 复制项目
  const handleDuplicate = useCallback(async (project: Project) => {
    try {
      await projectApi.duplicate(project.id)
      message.success('项目复制成功')
      fetchProjects({ page_size: 999 })
    } catch {
      message.error('复制失败')
    }
  }, [fetchProjects])

  // 归档项目
  const handleArchive = useCallback(async (project: Project) => {
    try {
      await projectApi.update(project.id, { status: 'archived' })
      message.success('项目已归档')
      fetchProjects({ page_size: 999 })
    } catch {
      message.error('归档失败')
    }
  }, [fetchProjects])

  // 删除项目
  const handleDelete = useCallback(async (project: Project) => {
    try {
      await projectApi.delete(project.id)
      message.success('项目已删除')
      fetchProjects({ page_size: 999 })
    } catch {
      message.error('删除失败')
    }
  }, [fetchProjects])

  // 客户端筛选与排序
  const filteredAndSorted = useMemo(() => {
    let result = [...projects]

    // 状态筛选
    if (statusFilter !== 'all') {
      if (statusFilter === 'in_progress') {
        result = result.filter((p) => IN_PROGRESS_STATUSES.includes(p.status))
      } else {
        result = result.filter((p) => p.status === statusFilter)
      }
    }

    // 类型筛选
    if (typeFilter !== 'all') {
      result = result.filter((p) => p.project_type === typeFilter)
    }

    // 排序
    result.sort((a, b) => {
      let cmp = 0
      switch (sortKey) {
        case 'name':
          cmp = a.name.localeCompare(b.name)
          break
        case 'created_at':
          cmp = new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
          break
        case 'completion_percentage':
          cmp = (b.completion_percentage || 0) - (a.completion_percentage || 0)
          break
        case 'updated_at':
        default:
          cmp = new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
          break
      }
      return cmp
    })

    return result
  }, [projects, statusFilter, typeFilter, sortKey])

  // 重名校验
  const checkNameExists = useCallback(async (name: string): Promise<boolean> => {
    if (!name.trim()) return false
    setNameChecking(true)
    try {
      const res: any = await projectApi.checkName(name)
      return res.data?.exists === true
    } catch {
      // 本地兜底：检查已加载的项目列表
      return projects.some(
        (p) => p.name.toLowerCase() === name.trim().toLowerCase()
      )
    } finally {
      setNameChecking(false)
    }
  }, [projects])

  // 表格列定义（列表视图）
  const columns = [
    {
      title: '项目名称',
      dataIndex: 'name',
      key: 'name',
      render: (name: string, record: Project) => (
        <Button
          type="link"
          onClick={() => navigate(`/projects/${record.id}`)}
          style={{ padding: 0 }}
        >
          {name}
        </Button>
      ),
    },
    {
      title: '类型',
      dataIndex: 'project_type',
      key: 'project_type',
      width: 100,
      render: (type?: string) =>
        type ? (
          <Tag>{PROJECT_TYPE_MAP[type as ProjectType] || type}</Tag>
        ) : (
          <Text type="secondary">-</Text>
        ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: string) => (
        <Tag color={PROJECT_STATUS_COLOR[status] || 'default'}>
          {PROJECT_STATUS_MAP[status as ProjectStatus] || status}
        </Tag>
      ),
    },
    {
      title: '完成度',
      dataIndex: 'completion_percentage',
      key: 'completion_percentage',
      width: 100,
      render: (value?: number) =>
        value !== undefined ? `${value}%` : '-',
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 170,
      render: (date: string) => formatDate(date),
    },
    {
      title: '操作',
      key: 'actions',
      width: 180,
      render: (_: unknown, record: Project) => (
        <ActionButtons project={record} onDuplicate={handleDuplicate} onArchive={handleArchive} onDelete={handleDelete} />
      ),
    },
  ]

  if (loading && projects.length === 0) {
    return <Loading />
  }

  return (
    <div>
      {/* 标题栏 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>项目管理</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateModalOpen(true)}>
          新建项目
        </Button>
      </div>

      {/* 视图切换 + 筛选 + 排序 */}
      <Card size="small" style={{ marginBottom: 16 }} styles={{ body: { padding: '12px 16px' } }}>
        <Row gutter={[16, 12]} align="middle">
          <Col>
            <Radio.Group
              value={viewMode}
              onChange={(e) => setViewMode(e.target.value)}
              optionType="button"
              buttonStyle="solid"
              size="small"
            >
              <Radio.Button value="grid"><AppstoreOutlined /> 网格</Radio.Button>
              <Radio.Button value="list"><UnorderedListOutlined /> 列表</Radio.Button>
              <Radio.Button value="compact"><BarsOutlined /> 紧凑</Radio.Button>
            </Radio.Group>
          </Col>
          <Col>
            <Text type="secondary" style={{ marginRight: 8, fontSize: 13 }}>状态</Text>
            <Select
              value={statusFilter}
              onChange={(v) => setStatusFilter(v)}
              options={STATUS_FILTER_OPTIONS}
              style={{ width: 110 }}
              size="small"
            />
          </Col>
          <Col>
            <Text type="secondary" style={{ marginRight: 8, fontSize: 13 }}>类型</Text>
            <Select
              value={typeFilter}
              onChange={(v) => setTypeFilter(v)}
              options={[{ value: 'all', label: '全部' }, ...TYPE_OPTIONS]}
              style={{ width: 110 }}
              size="small"
            />
          </Col>
          <Col>
            <Text type="secondary" style={{ marginRight: 8, fontSize: 13 }}>排序</Text>
            <Select
              value={sortKey}
              onChange={(v) => setSortKey(v)}
              options={SORT_OPTIONS}
              style={{ width: 130 }}
              size="small"
            />
          </Col>
        </Row>
      </Card>

      {/* 项目展示 */}
      {filteredAndSorted.length === 0 && !loading ? (
        <Card>
          <Empty description="暂无匹配的项目" />
        </Card>
      ) : viewMode === 'grid' ? (
        <GridProjects
          projects={filteredAndSorted}
          onDuplicate={handleDuplicate}
          onArchive={handleArchive}
          onDelete={handleDelete}
        />
      ) : viewMode === 'compact' ? (
        <CompactProjects
          projects={filteredAndSorted}
          onDuplicate={handleDuplicate}
          onArchive={handleArchive}
          onDelete={handleDelete}
        />
      ) : (
        <Table
          dataSource={filteredAndSorted}
          columns={columns}
          rowKey="id"
          loading={loading}
          size="middle"
          pagination={{
            total,
            showSizeChanger: true,
            showTotal: (t) => `共 ${t} 条`,
          }}
        />
      )}

      {/* 创建项目对话框 */}
      <Modal
        title="新建项目"
        open={createModalOpen}
        onCancel={() => {
          setCreateModalOpen(false)
          form.resetFields()
        }}
        footer={null}
        width={480}
        destroyOnClose
      >
        <Form form={form} layout="vertical" onFinish={handleCreate}>
          <Form.Item
            name="name"
            label="项目名称"
            rules={[
              { required: true, message: '请输入项目名称' },
              { min: 1, max: 50, message: '项目名称长度在 1-50 个字符' },
              {
                validator: async (_, value) => {
                  if (!value) return
                  const exists = await checkNameExists(value)
                  if (exists) {
                    throw new Error('该项目名称已存在，请换一个名称')
                  }
                },
              },
            ]}
            validateTrigger="onBlur"
          >
            <Input
              placeholder="请输入项目名称"
              suffix={nameChecking ? <Text type="secondary" style={{ fontSize: 12 }}>检查中...</Text> : null}
            />
          </Form.Item>
          <Form.Item name="project_type" label="项目类型">
            <Select
              placeholder="请选择项目类型（可选）"
              allowClear
              options={TYPE_OPTIONS}
            />
          </Form.Item>
          <Form.Item name="description" label="项目描述">
            <Input.TextArea rows={3} placeholder="请输入项目描述（可选）" />
          </Form.Item>
          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit" loading={createLoading}>
                创建
              </Button>
              <Button onClick={() => { setCreateModalOpen(false); form.resetFields() }}>
                取消
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}

// ---- 子组件 ----

/** 操作按钮组 */
function ActionButtons({
  project,
  onDuplicate,
  onArchive,
  onDelete,
}: {
  project: Project
  onDuplicate: (p: Project) => void
  onArchive: (p: Project) => void
  onDelete: (p: Project) => void
}) {
  const navigate = useNavigate()
  return (
    <Space size="small">
      <Tooltip title="查看详情">
        <Button
          type="link"
          size="small"
          icon={<EyeOutlined />}
          onClick={() => navigate(`/projects/${project.id}`)}
        />
      </Tooltip>
      <Tooltip title="复制项目">
        <Button
          type="link"
          size="small"
          icon={<CopyOutlined />}
          onClick={() => onDuplicate(project)}
        />
      </Tooltip>
      {project.status !== 'archived' && (
        <Tooltip title="归档">
          <Button
            type="link"
            size="small"
            icon={<InboxOutlined />}
            onClick={() => onArchive(project)}
          />
        </Tooltip>
      )}
      <Popconfirm
        title="确认删除"
        description="确定要删除该项目吗？此操作不可撤销。"
        onConfirm={() => onDelete(project)}
        okText="确认删除"
        cancelText="取消"
        okButtonProps={{ danger: true }}
      >
        <Tooltip title="删除">
          <Button type="link" size="small" danger icon={<DeleteOutlined />} />
        </Tooltip>
      </Popconfirm>
    </Space>
  )
}

/** 网格视图 */
function GridProjects({
  projects,
  onDuplicate,
  onArchive,
  onDelete,
}: {
  projects: Project[]
  onDuplicate: (p: Project) => void
  onArchive: (p: Project) => void
  onDelete: (p: Project) => void
}) {
  const navigate = useNavigate()
  return (
    <Row gutter={[16, 16]}>
      {projects.map((project) => (
        <Col xs={24} sm={12} md={8} lg={6} key={project.id}>
          <Card
            hoverable
            size="small"
            actions={[
              <Tooltip title="查看详情" key="view">
                <EyeOutlined onClick={() => navigate(`/projects/${project.id}`)} />
              </Tooltip>,
              <Tooltip title="复制" key="copy">
                <CopyOutlined onClick={(e) => { e.stopPropagation(); onDuplicate(project) }} />
              </Tooltip>,
              project.status !== 'archived' ? (
                <Tooltip title="归档" key="archive">
                  <InboxOutlined onClick={(e) => { e.stopPropagation(); onArchive(project) }} />
                </Tooltip>
              ) : null,
              <Popconfirm
                title="确认删除"
                description="此操作不可撤销"
                onConfirm={(e) => { e?.stopPropagation?.(); onDelete(project); }}
                onCancel={(e) => { e?.stopPropagation?.(); }}
                okText="确认"
                cancelText="取消"
                key="delete"
              >
                <Tooltip title="删除">
                  <DeleteOutlined style={{ color: '#ff4d4f' }} onClick={(e) => e.stopPropagation()} />
                </Tooltip>
              </Popconfirm>,
            ].filter(Boolean)}
            onClick={() => navigate(`/projects/${project.id}`)}
          >
            <Card.Meta
              title={
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Text ellipsis style={{ maxWidth: 120 }}>{project.name}</Text>
                  <Tag color={PROJECT_STATUS_COLOR[project.status] || 'default'} style={{ flexShrink: 0 }}>
                    {PROJECT_STATUS_MAP[project.status as ProjectStatus] || project.status}
                  </Tag>
                </div>
              }
              description={
                <div>
                  {project.project_type && (
                    <Tag style={{ marginBottom: 4 }}>
                      {PROJECT_TYPE_MAP[project.project_type as ProjectType] || project.project_type}
                    </Tag>
                  )}
                  {project.completion_percentage !== undefined && (
                    <div style={{ marginBottom: 4 }}>
                      <Text type="secondary" style={{ fontSize: 12 }}>完成度: {project.completion_percentage}%</Text>
                    </div>
                  )}
                  <Text type="secondary" style={{ fontSize: 12 }} ellipsis>
                    {project.description || '暂无描述'}
                  </Text>
                  <div style={{ marginTop: 4 }}>
                    <Text type="secondary" style={{ fontSize: 11 }}>
                      {formatDate(project.updated_at)}
                    </Text>
                  </div>
                </div>
              }
            />
          </Card>
        </Col>
      ))}
    </Row>
  )
}

/** 紧凑视图 */
function CompactProjects({
  projects,
  onDuplicate,
  onArchive,
  onDelete,
}: {
  projects: Project[]
  onDuplicate: (p: Project) => void
  onArchive: (p: Project) => void
  onDelete: (p: Project) => void
}) {
  const navigate = useNavigate()
  return (
    <Card>
      {projects.map((project, index) => (
        <div
          key={project.id}
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '8px 0',
            borderBottom: index < projects.length - 1 ? '1px solid #f0f0f0' : 'none',
          }}
        >
          <div
            style={{ display: 'flex', alignItems: 'center', gap: 12, cursor: 'pointer', flex: 1 }}
            onClick={() => navigate(`/projects/${project.id}`)}
          >
            <Text strong style={{ fontSize: 14 }}>{project.name}</Text>
            <Tag color={PROJECT_STATUS_COLOR[project.status] || 'default'}>
              {PROJECT_STATUS_MAP[project.status as ProjectStatus] || project.status}
            </Tag>
            {project.project_type && (
              <Tag>{PROJECT_TYPE_MAP[project.project_type as ProjectType] || project.project_type}</Tag>
            )}
            <Text type="secondary" style={{ fontSize: 12 }}>
              {formatDate(project.updated_at)}
            </Text>
          </div>
          <ActionButtons project={project} onDuplicate={onDuplicate} onArchive={onArchive} onDelete={onDelete} />
        </div>
      ))}
    </Card>
  )
}
