import {
  Card,
  Table,
  Tag,
  Select,
  Typography,
  Space,
} from 'antd'
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
} from '@ant-design/icons'
import Loading from '../../../components/common/Loading'
import EmptyState from '../../../components/common/EmptyState'
import { DIMENSION_LABELS } from './types'
import type { ConsistencyReport, PanelOption } from './types'

const { Text } = Typography

export interface ConsistencyTabProps {
  loading: boolean
  checkedPanels: PanelOption[]
  selectedCheckedPanel: string
  onSelectCheckedPanel: (id: string) => void
  consistencyReport: ConsistencyReport | null
}

export default function ConsistencyTab({
  loading,
  checkedPanels,
  selectedCheckedPanel,
  onSelectCheckedPanel,
  consistencyReport,
}: ConsistencyTabProps) {
  return (
    <div>
      <Card size="small" style={{ marginBottom: 16 }}>
        <Space wrap>
          <span style={{ fontWeight: 500 }}>选择已检测 Panel：</span>
          <Select
            style={{ width: 200 }}
            value={selectedCheckedPanel}
            onChange={onSelectCheckedPanel}
            options={checkedPanels.map((p) => ({
              label: `Panel #${p.panel_number}`,
              value: p.id,
            }))}
          />
        </Space>
      </Card>

      {loading ? (
        <Loading tip="加载检测报告..." />
      ) : consistencyReport ? (
        <div>
          <Card
            title="一致性检测结果"
            extra={
              consistencyReport.passed ? (
                <Tag icon={<CheckCircleOutlined />} color="success">
                  全部通过
                </Tag>
              ) : (
                <Tag icon={<CloseCircleOutlined />} color="error">
                  存在不一致
                </Tag>
              )
            }
            style={{ marginBottom: 16 }}
          >
            <div style={{ marginBottom: 16 }}>
              <Text>综合评分：</Text>
              <Text strong style={{ fontSize: 18, color: consistencyReport.overall_score >= 0.8 ? '#52c41a' : '#faad14' }}>
                {(consistencyReport.overall_score * 100).toFixed(0)}%
              </Text>
            </div>
          </Card>

          {consistencyReport.checks.map((check) => (
            <Card
              key={check.character_name}
              size="small"
              title={
                <Space>
                  <Text strong>{check.character_name}</Text>
                  {check.overall_match ? (
                    <Tag color="success" icon={<CheckCircleOutlined />}>
                      通过
                    </Tag>
                  ) : (
                    <Tag color="error" icon={<CloseCircleOutlined />}>
                      不通过
                    </Tag>
                  )}
                </Space>
              }
              style={{ marginBottom: 12 }}
            >
              <Table
                dataSource={check.dimensions}
                columns={[
                  {
                    title: '维度',
                    dataIndex: 'dimension',
                    key: 'dimension',
                    render: (dim: string) => DIMENSION_LABELS[dim] || dim,
                  },
                  {
                    title: '期望值',
                    dataIndex: 'expected',
                    key: 'expected',
                  },
                  {
                    title: '检测值',
                    dataIndex: 'detected',
                    key: 'detected',
                  },
                  {
                    title: '结果',
                    dataIndex: 'match',
                    key: 'match',
                    width: 100,
                    render: (match: boolean) =>
                      match ? (
                        <Tag color="success" icon={<CheckCircleOutlined />}>
                          通过
                        </Tag>
                      ) : (
                        <Tag color="error" icon={<CloseCircleOutlined />}>
                          不通过
                        </Tag>
                      ),
                  },
                  {
                    title: '置信度',
                    dataIndex: 'confidence',
                    key: 'confidence',
                    width: 100,
                    render: (conf: number) => `${conf}%`,
                  },
                ]}
                rowKey="dimension"
                pagination={false}
                size="small"
              />
            </Card>
          ))}
        </div>
      ) : (
        <EmptyState description="请选择一个已检测的 Panel" />
      )}
    </div>
  )
}
