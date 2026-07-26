import {
  List,
  Tag,
  Button,
  Input,
  Modal,
  Typography,
  Space,
  Radio,
} from 'antd'
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  EditOutlined,
  FileSearchOutlined,
} from '@ant-design/icons'
import Loading from '../../../components/common/Loading'
import EmptyState from '../../../components/common/EmptyState'
import type { PendingPanel } from './types'

const { Text } = Typography
const { TextArea } = Input

export interface PendingPanelsTabProps {
  loading: boolean
  pendingList: PendingPanel[]
  selectedPanel: PendingPanel | null
  onSelectPanel: (panel: PendingPanel | null) => void
  reviewNote: string
  onReviewNoteChange: (note: string) => void
  reviewAction: string
  onReviewActionChange: (action: string) => void
  onSubmitReview: () => void
}

export default function PendingPanelsTab({
  loading,
  pendingList,
  selectedPanel,
  onSelectPanel,
  reviewNote,
  onReviewNoteChange,
  reviewAction,
  onReviewActionChange,
  onSubmitReview,
}: PendingPanelsTabProps) {
  const closeModal = () => {
    onSelectPanel(null)
    onReviewNoteChange('')
    onReviewActionChange('approved')
  }

  return (
    <div>
      {loading ? (
        <Loading tip="加载待审核列表..." />
      ) : pendingList.length === 0 ? (
        <EmptyState description="暂无待审核项" />
      ) : (
        <List
          dataSource={pendingList.filter((p) => p.status === 'pending')}
          renderItem={(item) => (
            <List.Item
              key={item.id}
              actions={[
                <Button
                  type="primary"
                  size="small"
                  icon={<FileSearchOutlined />}
                  onClick={() => onSelectPanel(item)}
                >
                  审核
                </Button>,
              ]}
            >
              <List.Item.Meta
                avatar={
                  <div
                    style={{
                      width: 48,
                      height: 48,
                      background: '#1a1a2e',
                      borderRadius: 6,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: '#666',
                      fontSize: 12,
                    }}
                  >
                    {item.thumbnail_url ? (
                      <img
                        src={item.thumbnail_url}
                        alt={`Panel ${item.panel_number}`}
                        style={{ width: '100%', height: '100%', objectFit: 'cover', borderRadius: 6 }}
                      />
                    ) : (
                      <span>P{item.panel_number}</span>
                    )}
                  </div>
                }
                title={
                  <Space>
                    <Text strong>Panel #{item.panel_number}</Text>
                    <Tag color="warning">待审核</Tag>
                  </Space>
                }
                description={`创建时间: ${item.created_at}`}
              />
            </List.Item>
          )}
        />
      )}

      <Modal
        title={`审核 Panel #${selectedPanel?.panel_number || ''}`}
        open={!!selectedPanel}
        onCancel={closeModal}
        footer={[
          <Button key="cancel" onClick={closeModal}>
            取消
          </Button>,
          <Button key="submit" type="primary" onClick={onSubmitReview}>
            提交审核
          </Button>,
        ]}
        width={480}
      >
        <div style={{ marginBottom: 16 }}>
          <div style={{ marginBottom: 8, fontWeight: 500 }}>审核决定：</div>
          <Radio.Group value={reviewAction} onChange={(e) => onReviewActionChange(e.target.value)}>
            <Radio.Button value="approved" style={{ color: '#52c41a' }}>
              <CheckCircleOutlined /> 通过
            </Radio.Button>
            <Radio.Button value="rejected" style={{ color: '#ff4d4f' }}>
              <CloseCircleOutlined /> 打回
            </Radio.Button>
            <Radio.Button value="needs_modification" style={{ color: '#faad14' }}>
              <EditOutlined /> 需修改
            </Radio.Button>
          </Radio.Group>
        </div>
        <div>
          <div style={{ marginBottom: 8, fontWeight: 500 }}>审核备注：</div>
          <TextArea
            rows={4}
            value={reviewNote}
            onChange={(e) => onReviewNoteChange(e.target.value)}
            placeholder="请输入审核意见..."
          />
        </div>
      </Modal>
    </div>
  )
}
