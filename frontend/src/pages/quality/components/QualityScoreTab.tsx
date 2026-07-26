import {
  Card,
  Row,
  Col,
  Table,
  Tag,
  Select,
  Typography,
  Space,
  Badge,
  List,
} from 'antd'
import ReactEChartsCore from 'echarts-for-react'
import Loading from '../../../components/common/Loading'
import EmptyState from '../../../components/common/EmptyState'
import { DIMENSION_LABELS, RECOMMENDATION_MAP } from './types'
import type { QualityReport, PanelOption } from './types'

const { Text, Title } = Typography

export interface QualityScoreTabProps {
  loading: boolean
  scoredPanels: PanelOption[]
  selectedScoredPanel: string
  onSelectScoredPanel: (id: string) => void
  qualityReport: QualityReport | null
}

const getRadarOption = (report: QualityReport) => ({
  radar: {
    indicator: report.scores.map((s) => ({
      name: DIMENSION_LABELS[s.dimension] || s.dimension,
      max: 100,
    })),
    shape: 'circle' as const,
    splitNumber: 4,
    axisName: {
      color: '#333',
      fontSize: 12,
    },
    splitArea: {
      areaStyle: {
        color: ['rgba(22, 119, 255, 0.02)', 'rgba(22, 119, 255, 0.04)'],
      },
    },
  },
  series: [
    {
      type: 'radar',
      data: [
        {
          value: report.scores.map((s) => s.score),
          name: '质量评分',
          areaStyle: {
            color: 'rgba(22, 119, 255, 0.2)',
          },
          lineStyle: {
            color: '#1677ff',
            width: 2,
          },
          itemStyle: {
            color: '#1677ff',
          },
        },
      ],
    },
  ],
  tooltip: {
    trigger: 'item' as const,
  },
})

export default function QualityScoreTab({
  loading,
  scoredPanels,
  selectedScoredPanel,
  onSelectScoredPanel,
  qualityReport,
}: QualityScoreTabProps) {
  return (
    <div>
      <Card size="small" style={{ marginBottom: 16 }}>
        <Space wrap>
          <span style={{ fontWeight: 500 }}>选择已评分 Panel：</span>
          <Select
            style={{ width: 200 }}
            value={selectedScoredPanel}
            onChange={onSelectScoredPanel}
            options={scoredPanels.map((p) => ({
              label: `Panel #${p.panel_number}`,
              value: p.id,
            }))}
          />
        </Space>
      </Card>

      {loading ? (
        <Loading tip="加载质量评分..." />
      ) : qualityReport ? (
        <Row gutter={[16, 16]}>
          <Col xs={24} md={12}>
            <Card title="各维度评分雷达图">
              <ReactEChartsCore option={getRadarOption(qualityReport)} style={{ height: 320 }} />
            </Card>
          </Col>
          <Col xs={24} md={12}>
            <Card title="评分概览" style={{ marginBottom: 16 }}>
              <div style={{ textAlign: 'center', marginBottom: 16 }}>
                <Title level={2} style={{ color: qualityReport.overall_score >= 80 ? '#52c41a' : qualityReport.overall_score >= 60 ? '#faad14' : '#ff4d4f', margin: 0 }}>
                  {qualityReport.overall_score}
                </Title>
                <Text type="secondary">总体评分</Text>
              </div>
              <div style={{ textAlign: 'center', marginBottom: 16 }}>
                <Tag
                  color={RECOMMENDATION_MAP[qualityReport.recommendation]?.color || 'default'}
                  style={{ fontSize: 14, padding: '4px 12px' }}
                >
                  {RECOMMENDATION_MAP[qualityReport.recommendation]?.text || qualityReport.recommendation}
                </Tag>
                <div style={{ marginTop: 8 }}>
                  <Text type="secondary">推荐建议</Text>
                </div>
              </div>
              <Table
                dataSource={qualityReport.scores}
                columns={[
                  {
                    title: '维度',
                    dataIndex: 'dimension',
                    key: 'dimension',
                    render: (dim: string) => DIMENSION_LABELS[dim] || dim,
                  },
                  {
                    title: '评分',
                    dataIndex: 'score',
                    key: 'score',
                    render: (score: number) => (
                      <span style={{ color: score >= 80 ? '#52c41a' : score >= 60 ? '#faad14' : '#ff4d4f', fontWeight: 600 }}>
                        {score}
                      </span>
                    ),
                  },
                  {
                    title: '评价',
                    dataIndex: 'comment',
                    key: 'comment',
                  },
                ]}
                rowKey="dimension"
                pagination={false}
                size="small"
              />
            </Card>

            {qualityReport.defects.length > 0 && (
              <Card title="问题列表">
                <List
                  dataSource={qualityReport.defects}
                  renderItem={(defect, idx) => (
                    <List.Item>
                      <Space>
                        <Badge count={idx + 1} style={{ backgroundColor: '#ff4d4f' }} />
                        <Text>{defect}</Text>
                      </Space>
                    </List.Item>
                  )}
                />
              </Card>
            )}
          </Col>
        </Row>
      ) : (
        <EmptyState description="请选择一个已评分的 Panel" />
      )}
    </div>
  )
}
