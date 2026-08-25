import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Row, Col, Card, Tag, Spin, Space, Typography, Progress, Button, List } from 'antd'
import {
  ProjectOutlined,
  ClockCircleOutlined,
  FileTextOutlined,
  EyeOutlined,
  ThunderboltOutlined,
  RightOutlined,
  PlusOutlined,
  CheckCircleOutlined,
  LoadingOutlined,
  ExportOutlined,
  FileSearchOutlined,
  WarningOutlined,
} from '@ant-design/icons'
import apiClient from '../../api/client'
import { formatRelativeTime } from '../../utils/format'

const { Text } = Typography

/* ========== 类型定义 ========== */

interface ProductionStage {
  stage: string
  name: string
  status: 'pending' | 'in_progress' | 'completed'
  progress: number
}

interface PendingTask {
  id: string
  task_type: string
  title: string
  description: string
  priority: 'low' | 'medium' | 'high'
  related_project_id?: string
  created_at: string
}

interface DashboardStats {
  total_projects: number
  active_projects: number
  monthly_chapters: number
  pending_review_images: number
  total_generated_images: number
  recent_projects: Array<{
    id: string
    name: string
    status: string
    updated_at: string
  }>
  production_progress: {
    project_id: string
    project_name: string
    stages: ProductionStage[]
    overall_progress: number
  }
  pending_tasks: PendingTask[]
}

/* ========== 常量 ========== */

const PROJECT_STATUS_COLORS: Record<string, string> = {
  draft: 'default',
  planning: 'processing',
  generating: 'processing',
  editing: 'warning',
  completed: 'success',
  archived: 'default',
}

const PROJECT_STATUS_LABELS: Record<string, string> = {
  draft: '草稿',
  planning: '规划中',
  generating: '生成中',
  editing: '编辑中',
  completed: '已完成',
  archived: '已归档',
}

const PROGRESS_STATUS_LABELS: Record<string, string> = {
  pending: '待开始',
  in_progress: '进行中',
  completed: '已完成',
}

const TASK_TYPE_CONFIG: Record<string, { label: string; icon: React.ReactNode; color: string }> = {
  review: { label: '图片审核', icon: <EyeOutlined />, color: '#faad14' },
  generation: { label: '漫画生成', icon: <ThunderboltOutlined />, color: '#1890ff' },
  export: { label: '导出任务', icon: <ExportOutlined />, color: '#52c41a' },
  analysis: { label: '内容分析', icon: <FileSearchOutlined />, color: '#722ed1' },
}

const PRIORITY_TAG_COLORS: Record<string, string> = {
  high: 'red',
  medium: 'orange',
  low: 'default',
}

const PRIORITY_LABELS: Record<string, string> = {
  high: '高',
  medium: '中',
  low: '低',
}

/* ========== 统计卡片配置 ========== */

interface StatCardConfig {
  title: string
  dataKey: keyof DashboardStats
  icon: React.ReactNode
  bgColor: string
  borderColor: string
  link: string
}

const STAT_CARD_CONFIGS: StatCardConfig[] = [
  {
    title: '总项目数',
    dataKey: 'total_projects',
    icon: <ProjectOutlined style={{ fontSize: 28, color: '#1890ff' }} />,
    bgColor: '#e6f7ff',
    borderColor: '#1890ff',
    link: '/projects',
  },
  {
    title: '进行中的项目',
    dataKey: 'active_projects',
    icon: <ClockCircleOutlined style={{ fontSize: 28, color: '#52c41a' }} />,
    bgColor: '#f6ffed',
    borderColor: '#52c41a',
    link: '/projects',
  },
  {
    title: '月完成章节数',
    dataKey: 'monthly_chapters',
    icon: <FileTextOutlined style={{ fontSize: 28, color: '#faad14' }} />,
    bgColor: '#fffbe6',
    borderColor: '#faad14',
    link: '/projects',
  },
  {
    title: '累计生图数',
    dataKey: 'total_generated_images',
    icon: <ThunderboltOutlined style={{ fontSize: 28, color: '#13c2c2' }} />,
    bgColor: '#e6fffb',
    borderColor: '#13c2c2',
    link: '/generation',
  },
]

/* ========== 快速入口配置 ========== */

const QUICK_ACTIONS = [
  { title: '新建项目', description: '创建一个新的漫画项目', icon: <PlusOutlined />, link: '/projects' },
  { title: '导入小说', description: '导入小说进行漫画化', icon: <FileTextOutlined />, link: '/projects' },
  { title: '开始生成', description: '从已有项目生成漫画', icon: <ThunderboltOutlined />, link: '/generation' },
  { title: '导出中心', description: '导出已完成的漫画作品', icon: <ExportOutlined />, link: '/projects' },
]

/* ========== 微动效 CSS ========== */

const ANIMATION_STYLE = `
@keyframes statPop {
  0% { opacity: 0.6; transform: scale(0.9); }
  60% { opacity: 1; transform: scale(1.06); }
  100% { opacity: 1; transform: scale(1); }
}
.stat-card-value {
  animation: statPop 0.5s ease-out;
}
`

/* ========== 组件 ========== */

export default function Dashboard() {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(true)
  const [stats, setStats] = useState<DashboardStats | null>(null)

  useEffect(() => {
    fetchStats()
  }, [])

  const fetchStats = async () => {
    setLoading(true)
    try {
      const res: any = await apiClient.get('/dashboard/stats')
      setStats(res?.data || null)
    } catch (e) {
      console.error('获取 Dashboard 数据失败:', e)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return <Spin size="large" style={{ display: 'flex', justifyContent: 'center', marginTop: 120 }} />
  }

  /* ---------- 生产进度计算 ---------- */
  const progressStages = stats?.production_progress?.stages || []
  const completedCount = progressStages.filter((s: any) => s.status === 'completed').length
  const overallPercent = progressStages.length > 0
    ? Math.round((completedCount / progressStages.length) * 100)
    : stats?.production_progress?.overall_progress ?? 0

  /* ---------- 待处理任务（最多10条） ---------- */
  const pendingTasks = (stats?.pending_tasks || []).slice(0, 10)

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <style>{ANIMATION_STYLE}</style>

      {/* ====== 8.2 统计指标卡片 ====== */}
      <Row gutter={[16, 16]}>
        {STAT_CARD_CONFIGS.map((cfg) => {
          const value = (stats?.[cfg.dataKey] as number) ?? 0
          return (
            <Col xs={24} sm={12} lg={4} key={cfg.title}>
              <Card
                hoverable
                onClick={() => cfg.link !== '#' && navigate(cfg.link)}
                style={{ borderLeft: `4px solid ${cfg.borderColor}`, height: '100%' }}
              >
                <Space align="start" style={{ width: '100%', justifyContent: 'space-between' }}>
                  <div>
                    <div className="stat-card-value">
                      <span
                        style={{
                          fontSize: 28,
                          fontWeight: 700,
                          color: 'rgba(0,0,0,0.85)',
                          fontVariantNumeric: 'tabular-nums',
                        }}
                      >
                        {typeof value === 'number' ? value.toLocaleString() : value}
                      </span>
                    </div>
                    <Text type="secondary" style={{ fontSize: 13 }}>
                      {cfg.title}
                    </Text>
                  </div>
                  <div
                    style={{
                      background: cfg.bgColor,
                      borderRadius: 12,
                      padding: 8,
                      lineHeight: 1,
                    }}
                  >
                    {cfg.icon}
                  </div>
                </Space>
              </Card>
            </Col>
          )
        })}
      </Row>

      {/* ====== 快速入口 ====== */}
      <Card title="快速入口" styles={{ body: { padding: '16px 24px' } }}>
        <Row gutter={[16, 16]}>
          {QUICK_ACTIONS.map((action) => (
            <Col xs={12} sm={6} key={action.title}>
              <Card
                hoverable
                size="small"
                onClick={() => navigate(action.link)}
                bodyStyle={{ padding: '16px 20px' }}
              >
                <Space>
                  <span style={{ fontSize: 20, color: '#1890ff' }}>{action.icon}</span>
                  <div>
                    <div style={{ fontWeight: 500 }}>{action.title}</div>
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      {action.description}
                    </Text>
                  </div>
                </Space>
              </Card>
            </Col>
          ))}
        </Row>
      </Card>

      {/* ====== 8.4 生产进度概览 ====== */}
      <Card title="生产进度概览">
        <Space direction="vertical" style={{ width: '100%' }} size="middle">
          {/* 整体百分比 */}
          <div style={{ textAlign: 'center', marginBottom: 4 }}>
            <span style={{ fontSize: 32, fontWeight: 700, color: '#1890ff' }}>
              {overallPercent}%
            </span>
            <Text type="secondary" style={{ marginLeft: 8, fontSize: 14 }}>
              整体完成度
            </Text>
          </div>

          {/* 各阶段进度条 */}
          <Row gutter={[16, 12]}>
            {progressStages.map((stage) => {
              const statusIcon =
                stage.status === 'completed' ? (
                  <CheckCircleOutlined style={{ color: '#52c41a', fontSize: 16 }} />
                ) : stage.status === 'in_progress' ? (
                  <LoadingOutlined style={{ color: '#1890ff', fontSize: 16 }} />
                ) : (
                  <ClockCircleOutlined style={{ color: '#d9d9d9', fontSize: 16 }} />
                )

              const tagColor =
                stage.status === 'completed'
                  ? 'success'
                  : stage.status === 'in_progress'
                    ? 'processing'
                    : 'default'

              return (
                <Col xs={24} sm={12} key={stage.stage}>
                  <Space style={{ width: '100%' }} direction="vertical" size={4}>
                    <Space style={{ width: '100%', justifyContent: 'space-between' }}>
                      <Space size={8}>
                        {statusIcon}
                        <Text strong>{stage.name}</Text>
                      </Space>
                      <Tag color={tagColor}>
                        {PROGRESS_STATUS_LABELS[stage.status] || stage.status}
                      </Tag>
                    </Space>
                    <Progress
                      percent={stage.progress}
                      size="small"
                      status={stage.status === 'completed' ? 'success' : 'active'}
                      style={{ margin: 0 }}
                    />
                  </Space>
                </Col>
              )
            })}
          </Row>

          {progressStages.length === 0 && (
            <Text type="secondary" style={{ textAlign: 'center', display: 'block', padding: '12px 0' }}>
              暂无生产进度数据
            </Text>
          )}
        </Space>
      </Card>

      {/* ====== 8.3 最近项目 + 8.5 待处理任务提醒 ====== */}
      <Row gutter={[16, 16]}>
        {/* 最近项目 - 网格布局 */}
        <Col xs={24} lg={16}>
          <Card
            title="最近项目"
            extra={
              <a onClick={() => navigate('/projects')}>
                查看全部 <RightOutlined />
              </a>
            }
          >
            {(stats?.recent_projects || []).length > 0 ? (
              <Row gutter={[16, 16]}>
                {(stats?.recent_projects || []).slice(0, 6).map((project) => (
                  <Col xs={24} sm={12} md={8} key={project.id}>
                    <Card
                      hoverable
                      size="small"
                      onClick={() => navigate(`/projects/${project.id}`)}
                      bodyStyle={{ padding: '16px' }}
                    >
                      <Space direction="vertical" style={{ width: '100%' }} size={4}>
                        <Space style={{ width: '100%', justifyContent: 'space-between' }}>
                          <Text strong ellipsis style={{ maxWidth: 120 }}>
                            {project.name}
                          </Text>
                          <Tag color={PROJECT_STATUS_COLORS[project.status] || 'default'}>
                            {PROJECT_STATUS_LABELS[project.status] || project.status}
                          </Tag>
                        </Space>
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          更新于 {formatRelativeTime(project.updated_at)}
                        </Text>
                      </Space>
                    </Card>
                  </Col>
                ))}
              </Row>
            ) : (
              <div style={{ textAlign: 'center', padding: '40px 0' }}>
                <Text type="secondary" style={{ display: 'block', marginBottom: 12 }}>
                  暂无项目
                </Text>
                <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate('/projects')}>
                  创建一个新项目
                </Button>
              </div>
            )}
          </Card>
        </Col>

        {/* 待处理任务提醒 */}
        <Col xs={24} lg={8}>
          <Card title="待处理任务提醒">
            {pendingTasks.length > 0 ? (
              <List
                dataSource={pendingTasks}
                renderItem={(task) => {
                  const taskCfg = TASK_TYPE_CONFIG[task.task_type] || {
                    label: task.task_type,
                    icon: <WarningOutlined />,
                    color: '#999',
                  }
                  return (
                    <List.Item
                      style={{
                        cursor: task.related_project_id ? 'pointer' : 'default',
                      }}
                      onClick={() => {
                        if (task.related_project_id) {
                          navigate(`/projects/${task.related_project_id}`)
                        }
                      }}
                    >
                      <List.Item.Meta
                        avatar={
                          <span
                            style={{
                              fontSize: 20,
                              color: taskCfg.color,
                              display: 'inline-flex',
                              alignItems: 'center',
                            }}
                          >
                            {taskCfg.icon}
                          </span>
                        }
                        title={
                          <Space size={4}>
                            <Text strong style={{ fontSize: 13 }}>
                              {task.title}
                            </Text>
                            {task.priority === 'high' && (
                              <Tag
                                color={PRIORITY_TAG_COLORS[task.priority]}
                                style={{ fontSize: 10, lineHeight: '16px' }}
                              >
                                {PRIORITY_LABELS[task.priority]}
                              </Tag>
                            )}
                          </Space>
                        }
                        description={
                          <Space direction="vertical" size={2}>
                            <Text type="secondary" style={{ fontSize: 12 }}>
                              {task.description}
                            </Text>
                            <Text type="secondary" style={{ fontSize: 11 }}>
                              {formatRelativeTime(task.created_at)}
                            </Text>
                          </Space>
                        }
                      />
                    </List.Item>
                  )
                }}
              />
            ) : (
              <div style={{ textAlign: 'center', padding: '40px 0' }}>
                <CheckCircleOutlined style={{ fontSize: 40, color: '#52c41a', marginBottom: 8 }} />
                <br />
                <Text type="secondary">一切正常，暂无待处理任务</Text>
              </div>
            )}
          </Card>
        </Col>
      </Row>
    </Space>
  )
}
