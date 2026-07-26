import { useEffect, useState } from 'react'
import {
  Card,
  Row,
  Col,
  Tabs,
  Button,
  message,
  Statistic,
} from 'antd'
import {
  CheckCircleOutlined,
  EditOutlined,
  WarningOutlined,
  FileSearchOutlined,
  StarOutlined,
  ReloadOutlined,
} from '@ant-design/icons'
import { useParams } from 'react-router-dom'
import { qualityApi } from '../../api/qualityApi'
import { useProjectStore } from '../../stores/projectStore'
import PendingPanelsTab from './components/PendingPanelsTab'
import ConsistencyTab from './components/ConsistencyTab'
import QualityScoreTab from './components/QualityScoreTab'
import ReportsTab from './components/ReportsTab'
import {
  MOCK_PENDING,
  MOCK_CONSISTENCY,
  MOCK_QUALITY,
  MOCK_CHECKED_PANELS,
  MOCK_SCORED_PANELS,
} from './components/mockData'
import type {
  PendingPanel,
  ConsistencyReport,
  QualityReport,
} from './components/types'

export default function QualityCenter() {
  const { id: projectId } = useParams<{ id: string }>()
  const { fetchProjects } = useProjectStore()

  const [activeTab, setActiveTab] = useState('pending')
  const [loading, setLoading] = useState(false)

  // Pending tab
  const [pendingList, setPendingList] = useState<PendingPanel[]>([])
  const [selectedPanel, setSelectedPanel] = useState<PendingPanel | null>(null)
  const [reviewNote, setReviewNote] = useState('')
  const [reviewAction, setReviewAction] = useState<string>('approved')

  // Consistency tab
  const [checkedPanels] = useState(MOCK_CHECKED_PANELS)
  const [selectedCheckedPanel, setSelectedCheckedPanel] = useState<string>('panel-1')
  const [consistencyReport, setConsistencyReport] = useState<ConsistencyReport | null>(null)

  // Quality tab
  const [scoredPanels] = useState(MOCK_SCORED_PANELS)
  const [selectedScoredPanel, setSelectedScoredPanel] = useState<string>('panel-1')
  const [qualityReport, setQualityReport] = useState<QualityReport | null>(null)

  useEffect(() => {
    fetchProjects()
  }, [fetchProjects])

  useEffect(() => {
    if (activeTab === 'pending') {
      loadPending()
    }
  }, [activeTab])

  useEffect(() => {
    if (selectedCheckedPanel) {
      loadConsistencyReport(selectedCheckedPanel)
    }
  }, [selectedCheckedPanel])

  useEffect(() => {
    if (selectedScoredPanel) {
      loadQualityReport(selectedScoredPanel)
    }
  }, [selectedScoredPanel])

  const loadPending = async () => {
    setLoading(true)
    try {
      if (projectId) {
        const res: any = await qualityApi.listPending(projectId)
        setPendingList((res as { items?: PendingPanel[] }).items || [])
      } else {
        setPendingList(MOCK_PENDING)
      }
    } catch {
      setPendingList(MOCK_PENDING)
    } finally {
      setLoading(false)
    }
  }

  const loadConsistencyReport = async (panelId: string) => {
    setLoading(true)
    try {
      if (projectId) {
        const res: any = await qualityApi.getConsistencyReport(projectId, panelId)
        setConsistencyReport((res as { data?: ConsistencyReport }).data || null)
      } else {
        setConsistencyReport(MOCK_CONSISTENCY)
      }
    } catch {
      setConsistencyReport(MOCK_CONSISTENCY)
    } finally {
      setLoading(false)
    }
  }

  const loadQualityReport = async (panelId: string) => {
    setLoading(true)
    try {
      if (projectId) {
        const res: any = await qualityApi.scoreQuality(projectId, panelId)
        setQualityReport((res as { data?: QualityReport }).data || null)
      } else {
        setQualityReport(MOCK_QUALITY)
      }
    } catch {
      setQualityReport(MOCK_QUALITY)
    } finally {
      setLoading(false)
    }
  }

  const handleSubmitReview = async () => {
    if (!selectedPanel || !projectId) return
    try {
      await qualityApi.submitReview(projectId, selectedPanel.id, reviewAction, reviewNote)
      message.success('审核已提交')
      setSelectedPanel(null)
      setReviewNote('')
      setReviewAction('approved')
      loadPending()
    } catch {
      message.error('提交审核失败')
    }
  }

  // -------- 统计卡片 --------
  const stats = {
    total: pendingList.length + 12,
    passRate: pendingList.length > 0 ? Math.round((5 / (pendingList.length + 5)) * 100) : 75,
    warnings: 3,
    pending: pendingList.filter((p) => p.status === 'pending').length,
  }

  const handleRefresh = () => {
    loadPending()
    if (selectedCheckedPanel) loadConsistencyReport(selectedCheckedPanel)
    if (selectedScoredPanel) loadQualityReport(selectedScoredPanel)
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <h2 style={{ margin: 0, fontSize: 20, fontWeight: 600 }}>质量控制中心</h2>
        <Button icon={<ReloadOutlined />} onClick={handleRefresh}>
          刷新
        </Button>
      </div>

      {/* 统计卡片 */}
      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={12} sm={6}>
          <Card hoverable>
            <Statistic title="检测总数" value={stats.total} prefix={<FileSearchOutlined />} />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card hoverable>
            <Statistic
              title="通过率"
              value={stats.passRate}
              suffix="%"
              prefix={<CheckCircleOutlined style={{ color: '#52c41a' }} />}
              valueStyle={{ color: '#52c41a' }}
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card hoverable>
            <Statistic
              title="警告数"
              value={stats.warnings}
              prefix={<WarningOutlined style={{ color: '#faad14' }} />}
              valueStyle={{ color: '#faad14' }}
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card hoverable>
            <Statistic
              title="待审核"
              value={stats.pending}
              prefix={<EditOutlined style={{ color: '#1677ff' }} />}
              valueStyle={{ color: '#1677ff' }}
            />
          </Card>
        </Col>
      </Row>

      {/* Tab 切换 */}
      <Card>
        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          items={[
            {
              key: 'pending',
              label: (
                <span>
                  <EditOutlined style={{ marginRight: 6 }} />
                  待审核列表
                </span>
              ),
              children: (
                <PendingPanelsTab
                  loading={loading}
                  pendingList={pendingList}
                  selectedPanel={selectedPanel}
                  onSelectPanel={setSelectedPanel}
                  reviewNote={reviewNote}
                  onReviewNoteChange={setReviewNote}
                  reviewAction={reviewAction}
                  onReviewActionChange={setReviewAction}
                  onSubmitReview={handleSubmitReview}
                />
              ),
            },
            {
              key: 'consistency',
              label: (
                <span>
                  <CheckCircleOutlined style={{ marginRight: 6 }} />
                  一致性检测报告
                </span>
              ),
              children: (
                <ConsistencyTab
                  loading={loading}
                  checkedPanels={checkedPanels}
                  selectedCheckedPanel={selectedCheckedPanel}
                  onSelectCheckedPanel={setSelectedCheckedPanel}
                  consistencyReport={consistencyReport}
                />
              ),
            },
            {
              key: 'quality',
              label: (
                <span>
                  <StarOutlined style={{ marginRight: 6 }} />
                  质量评分
                </span>
              ),
              children: (
                <QualityScoreTab
                  loading={loading}
                  scoredPanels={scoredPanels}
                  selectedScoredPanel={selectedScoredPanel}
                  onSelectScoredPanel={setSelectedScoredPanel}
                  qualityReport={qualityReport}
                />
              ),
            },
            {
              key: 'reports',
              label: (
                <span>
                  <FileSearchOutlined style={{ marginRight: 6 }} />
                  检测报告
                </span>
              ),
              children: <ReportsTab projectId={projectId} active={activeTab === 'reports'} />,
            },
          ]}
        />
      </Card>
    </div>
  )
}
