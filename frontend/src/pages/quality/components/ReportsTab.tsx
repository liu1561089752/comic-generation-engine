import { useEffect, useState } from 'react'
import {
  Card,
  Table,
  Tag,
  Button,
  Modal,
  message,
  Typography,
  Space,
} from 'antd'
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  ReloadOutlined,
} from '@ant-design/icons'
import { qualityApi } from '../../../api/qualityApi'
import Loading from '../../../components/common/Loading'
import EmptyState from '../../../components/common/EmptyState'
import { DIMENSION_LABELS } from './types'

const { Text, Title } = Typography

export interface ReportsTabProps {
  projectId?: string
  active: boolean
}

export default function ReportsTab({ projectId, active }: ReportsTabProps) {
  const [reports, setReports] = useState<any[]>([])
  const [reportsLoading, setReportsLoading] = useState(false)
  const [selectedReport, setSelectedReport] = useState<any>(null)
  const [reportDetailVisible, setReportDetailVisible] = useState(false)

  const loadReports = async () => {
    if (!projectId) return
    setReportsLoading(true)
    try {
      const res: any = await qualityApi.listReports(projectId, { skip: 0, limit: 50 })
      const data = (res as { data?: { items?: any[] } }).data
      setReports(data?.items || [])
    } catch {
      setReports([])
    } finally {
      setReportsLoading(false)
    }
  }

  const handleViewReport = async (panelId: string) => {
    if (!projectId) return
    try {
      const res: any = await qualityApi.getReportDetail(projectId, panelId)
      const data = (res as { data?: any }).data
      setSelectedReport(data || null)
      setReportDetailVisible(true)
    } catch {
      message.error('加载报告详情失败')
    }
  }

  const handleCreateReport = async () => {
    if (!projectId) return
    try {
      await qualityApi.createReport(projectId, { scope: 'all' })
      message.success('质量检测任务已创建')
      setTimeout(() => loadReports(), 2000)
    } catch {
      message.error('创建检测任务失败')
    }
  }

  useEffect(() => {
    if (active) {
      loadReports()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, projectId])

  return (
    <div>
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'flex-end' }}>
        <Button type="primary" icon={<ReloadOutlined />} onClick={handleCreateReport}>
          触发全面检测
        </Button>
      </div>
      {reportsLoading ? (
        <Loading tip="加载检测报告..." />
      ) : reports.length === 0 ? (
        <EmptyState description="暂无检测报告" />
      ) : (
        <Table
          dataSource={reports}
          rowKey="panel_id"
          columns={[
            {
              title: 'Panel',
              dataIndex: 'panel_number',
              key: 'panel_number',
              width: 80,
              render: (n: number) => `#${n}`,
            },
            {
              title: '综合评分',
              dataIndex: 'overall_score',
              key: 'overall_score',
              width: 120,
              render: (score: number) => (
                <span style={{ color: score >= 80 ? '#52c41a' : score >= 60 ? '#faad14' : '#ff4d4f', fontWeight: 600 }}>
                  {score.toFixed(1)}
                </span>
              ),
            },
            {
              title: '一致性',
              dataIndex: 'consistency_passed',
              key: 'consistency_passed',
              width: 100,
              render: (passed: boolean) =>
                passed ? (
                  <Tag color="success" icon={<CheckCircleOutlined />}>通过</Tag>
                ) : (
                  <Tag color="error" icon={<CloseCircleOutlined />}>异常</Tag>
                ),
            },
            {
              title: '状态',
              dataIndex: 'status',
              key: 'status',
              width: 100,
              render: (s: string) => {
                const map: Record<string, { color: string; text: string }> = {
                  generated: { color: 'blue', text: '待检测' },
                  approved: { color: 'success', text: '已通过' },
                  rejected: { color: 'error', text: '已打回' },
                }
                const m = map[s] || { color: 'default', text: s }
                return <Tag color={m.color}>{m.text}</Tag>
              },
            },
            {
              title: '操作',
              key: 'action',
              width: 100,
              render: (_: any, record: any) => (
                <Button type="link" size="small" onClick={() => handleViewReport(record.panel_id)}>
                  查看详情
                </Button>
              ),
            },
          ]}
          pagination={false}
          size="small"
        />
      )}

      <Modal
        title={`检测报告详情 - Panel #${selectedReport?.panel_number || ''}`}
        open={reportDetailVisible}
        onCancel={() => { setReportDetailVisible(false); setSelectedReport(null) }}
        footer={null}
        width={640}
      >
        {selectedReport ? (
          <div>
            {selectedReport.scores?.scores ? (
              <div style={{ marginBottom: 16 }}>
                <Title level={5}>质量评分</Title>
                <Table
                  dataSource={selectedReport.scores.scores}
                  rowKey="dimension"
                  columns={[
                    { title: '维度', dataIndex: 'dimension', key: 'dimension', render: (d: string) => DIMENSION_LABELS[d] || d },
                    { title: '评分', dataIndex: 'score', key: 'score' },
                    { title: '评价', dataIndex: 'comment', key: 'comment' },
                  ]}
                  pagination={false}
                  size="small"
                />
              </div>
            ) : null}
            {selectedReport.consistency?.checks ? (
              <div>
                <Title level={5}>一致性检测</Title>
                {selectedReport.consistency.checks.map((check: any) => (
                  <Card key={check.character_name} size="small" style={{ marginBottom: 8 }}>
                    <Space>
                      <Text strong>{check.character_name}</Text>
                      {check.overall_match ? (
                        <Tag color="success" icon={<CheckCircleOutlined />}>通过</Tag>
                      ) : (
                        <Tag color="error" icon={<CloseCircleOutlined />}>不通过</Tag>
                      )}
                    </Space>
                  </Card>
                ))}
              </div>
            ) : null}
          </div>
        ) : (
          <EmptyState description="暂无详情" />
        )}
      </Modal>
    </div>
  )
}
