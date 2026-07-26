import { Badge, Spin, Tag, Typography } from 'antd'
import { LoadingOutlined } from '@ant-design/icons'

const { Text } = Typography

export interface StatusIndicatorProps {
  status: string
}

export default function StatusIndicator({ status }: StatusIndicatorProps) {
  switch (status) {
    case 'queued':
      return <Badge status="default" text={<Text type="secondary">排队中</Text>} />
    case 'running':
      return (
        <span>
          <Spin indicator={<LoadingOutlined style={{ fontSize: 14, color: '#1890ff' }} />} size="small" />
          <Text style={{ marginLeft: 6, color: '#1890ff' }}>处理中</Text>
        </span>
      )
    case 'completed':
      return <Badge status="success" text={<Text type="success">已完成</Text>} />
    case 'failed':
      return <Badge status="error" text={<Text type="danger">失败</Text>} />
    case 'cancelled':
      return <Badge status="warning" text={<Text type="warning">已取消</Text>} />
    default:
      return <Tag>{status}</Tag>
  }
}
