import { useEffect, useState } from 'react'
import { useParams, useNavigate, Outlet, useLocation } from 'react-router-dom'
import { Card, Row, Col, Statistic, Spin, Tag, Button, Space, Typography, Tooltip, Progress } from 'antd'
import { CheckCircleOutlined, ClockCircleOutlined, LoadingOutlined } from '@ant-design/icons'
import { useProjectStore } from '../../stores/projectStore'
import { novelApi } from '../../api/novelApi'
import { characterApi } from '../../api/characterApi'
import { formatDate } from '../../utils/format'
import { PROJECT_STATUS_MAP, PROJECT_TYPE_MAP } from '../../types'
import { PROJECT_STATUS_COLOR } from '../../utils/constants'
import type { ProjectStatus, ProjectType } from '../../types'
import type { ProductionStage } from '../../types/project'

const { Title, Text } = Typography

/** 8 工序 stage key → 功能模块路径映射（后端返回的 stage 字段 → 前端跳转路径） */
const STAGE_PATH_MAP: Record<string, string> = {
  novel_import: 'novels',
  character_design: 'characters',
  world_building: 'worlds',
  script_generation: 'story-breakdown',
  storyboard: 'storyboard',
  layout: 'layout',
  image_generation: 'generation',
  export: 'export',
}

/** 默认生产阶段定义（当 API 未返回 production_progress 时使用） */
const DEFAULT_STAGES: ProductionStage[] = [
  { key: 'novel_import', label: '小说导入', status: 'pending', path: 'novels' },
  { key: 'character_design', label: '角色设计', status: 'pending', path: 'characters' },
  { key: 'world_building', label: '世界观构建', status: 'pending', path: 'worlds' },
  { key: 'script_generation', label: '脚本生成', status: 'pending', path: 'story-breakdown' },
  { key: 'storyboard', label: '分镜设计', status: 'pending', path: 'storyboard' },
  { key: 'layout', label: 'AI排版', status: 'pending', path: 'layout' },
  { key: 'illustration_generation', label: '画面生成', status: 'pending', path: 'generation' },
  { key: 'export', label: '导出', status: 'pending', path: 'export' },
]

/** 根据项目状态推导各阶段状态 */
function deriveStageStatuses(projectStatus: string): ProductionStage[] {
  const statusOrder = ['draft', 'planning', 'generating', 'editing', 'completed', 'archived']
  const currentIdx = statusOrder.indexOf(projectStatus)

  return DEFAULT_STAGES.map((stage, idx) => {
    const totalStages = DEFAULT_STAGES.length
    const stageRatio = idx / totalStages
    let stageStatus: 'pending' | 'in_progress' | 'completed'

    if (projectStatus === 'archived') {
      stageStatus = 'completed'
    } else if (projectStatus === 'draft' || currentIdx < 0) {
      stageStatus = 'pending'
    } else {
      const threshold = (currentIdx + 1) / statusOrder.length
      if (stageRatio < threshold) {
        stageStatus = 'completed'
      } else if (stageRatio < threshold + 0.15) {
        stageStatus = 'in_progress'
      } else {
        stageStatus = 'pending'
      }
    }

    return { ...stage, status: stageStatus }
  })
}

/** 计算整体进度百分比 */
function calcOverallProgress(stages: ProductionStage[]): number {
  if (stages.length === 0) return 0
  const completed = stages.filter((s) => s.status === 'completed').length
  const inProgress = stages.filter((s) => s.status === 'in_progress').length
  return Math.round(((completed + inProgress * 0.5) / stages.length) * 100)
}

/** 生产进度阶段卡片子组件 */
function StageCard({ stage, projectId }: { stage: ProductionStage; projectId: string }) {
  const navigate = useNavigate()

  const statusConfig = {
    completed: { icon: <CheckCircleOutlined style={{ color: '#52c41a' }} />, color: '#52c41a', label: '已完成' },
    in_progress: { icon: <LoadingOutlined style={{ color: '#1677ff' }} />, color: '#1677ff', label: '进行中' },
    pending: { icon: <ClockCircleOutlined style={{ color: '#d9d9d9' }} />, color: '#d9d9d9', label: '待开始' },
  }

  const config = statusConfig[stage.status]

  return (
    <Tooltip title={config.label}>
      <Card
        size="small"
        hoverable={!!stage.path}
        onClick={() => {
          if (stage.path) {
            navigate(`/projects/${projectId}/${stage.path}`)
          }
        }}
        style={{
          borderLeft: `3px solid ${config.color}`,
          opacity: stage.status === 'pending' ? 0.6 : 1,
          cursor: stage.path ? 'pointer' : 'default',
          height: '100%',
        }}
        styles={{ body: { padding: '10px 12px' } }}
      >
        <Space>
          {config.icon}
          <Text style={{ fontSize: 13 }}>{stage.label}</Text>
        </Space>
      </Card>
    </Tooltip>
  )
}

export default function ProjectDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const location = useLocation()
  const { currentProject, fetchProject, loading } = useProjectStore()
  const [stats, setStats] = useState({ novels: 0, characters: 0, scenes: 0 })

  useEffect(() => {
    if (!id) return
    let cancelled = false
    fetchProject(id)
    Promise.all([
      novelApi.list(id).catch((err) => { console.error('获取数据失败:', err); return null; }),
      characterApi.list(id).catch((err) => { console.error('获取数据失败:', err); return null; }),
    ]).then(([novelsRes, charsRes]) => {
      if (cancelled) return
      const novelsData: any = novelsRes
      const charsData: any = charsRes
      setStats({
        novels: novelsData?.data?.items?.length || novelsData?.data?.length || 0,
        characters: charsData?.data?.items?.length || charsData?.data?.length || 0,
        scenes: 0,
      })
    })
    return () => { cancelled = true }
  }, [id])

  if (!id) return null

  // 判断是否在子路由（novels, characters 等）
  const isChildRoute = location.pathname !== `/projects/${id}`

  // 如果在子路由，显示子路由内容
  if (isChildRoute) {
    return <Outlet />
  }

  if (loading && !currentProject) {
    return <Spin style={{ display: 'block', margin: '100px auto' }} />
  }

  const project = currentProject

  // 生产进度阶段：优先从 API 返回的 8 工序数据（后端字段 stage/name/status → 前端 key/label/status/path），
  // 否则根据项目状态本地推导
  const rawStages: any[] = project?.production_progress?.stages || []
  const productionStages: ProductionStage[] =
    rawStages.length > 0
      ? rawStages.map((s) => ({
          key: s.stage,
          label: s.name,
          status: s.status,
          path: STAGE_PATH_MAP[s.stage],
        }))
      : deriveStageStatuses(project?.status || 'draft')

  // 完成度：优先用后端计算的整体进度（与工作台生产进度概览同一套算法：完成的工序数 / 8）
  const overallProgress =
    project?.production_progress?.overall_progress ?? calcOverallProgress(productionStages)

  const menuItems = [
    { key: 'novels', label: '📖 小说管理', desc: '导入和管理小说源文件', path: `/projects/${id}/novels` },
    { key: 'characters', label: '👥 人物IP', desc: '管理角色设定和关系', path: `/projects/${id}/characters` },
    { key: 'worlds', label: '🌍 世界观', desc: '构建世界背景和资产库', path: `/projects/${id}/worlds` },
    { key: 'export', label: '📤 导出中心', desc: '导出为长图/PNG/JPG', path: `/projects/${id}/export` },
  ]

  return (
    <div>
      {/* 项目信息头部 */}
      <div style={{ marginBottom: 24 }}>
        <Space align="center" style={{ marginBottom: 8 }}>
          <Button onClick={() => navigate('/projects')} type="text" size="small">← 返回</Button>
          <Title level={4} style={{ margin: 0 }}>
            {project?.name || '项目详情'}
          </Title>
          <Tag color={PROJECT_STATUS_COLOR[project?.status || ''] || 'default'}>
            {PROJECT_STATUS_MAP[project?.status as ProjectStatus] || project?.status || 'draft'}
          </Tag>
          {project?.project_type && (
            <Tag>
              {PROJECT_TYPE_MAP[project.project_type as ProjectType] || project.project_type}
            </Tag>
          )}
        </Space>
        <Text type="secondary">{project?.description || '暂无描述'}</Text>
        <br />
        <Text type="secondary" style={{ fontSize: 12 }}>
          创建于 {project?.created_at ? formatDate(project.created_at) : '-'}
          {' | '}更新于 {project?.updated_at ? formatDate(project.updated_at) : '-'}
        </Text>
      </div>

      {/* 生产进度概览 */}
      <Card
        title="📊 生产进度"
        size="small"
        style={{ marginBottom: 24 }}
        extra={
          <Space>
            <Text type="secondary" style={{ fontSize: 13 }}>整体进度</Text>
            <Progress
              percent={overallProgress}
              size="small"
              style={{ width: 120, margin: 0 }}
              strokeColor={overallProgress === 100 ? '#52c41a' : '#1677ff'}
            />
          </Space>
        }
      >
        <Row gutter={[12, 12]}>
          {productionStages.map((stage) => (
            <Col xs={12} sm={8} md={6} lg={4} key={stage.key}>
              <StageCard stage={stage} projectId={id} />
            </Col>
          ))}
        </Row>
      </Card>

      {/* 统计卡片 */}
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={6}>
          <Card size="small">
            <Statistic title="小说" value={stats.novels} suffix="本" />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic title="角色" value={stats.characters} suffix="个" />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic title="场景" value={project?.production_progress?.total_scenes ?? stats.scenes} suffix="个" />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic title="完成度" value={overallProgress} suffix="%" />
          </Card>
        </Col>
      </Row>

      {/* 功能模块入口 */}
      <Title level={5} style={{ marginBottom: 16 }}>功能模块</Title>
      <Row gutter={[16, 16]}>
        {menuItems.map((item) => (
          <Col span={8} key={item.key}>
            <Card
              hoverable
              onClick={() => navigate(item.path)}
              size="small"
            >
              <Card.Meta
                title={<span style={{ fontSize: 16 }}>{item.label}</span>}
                description={item.desc}
              />
            </Card>
          </Col>
        ))}
      </Row>
    </div>
  )
}
