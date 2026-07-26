import { Empty, Button } from 'antd'

interface EmptyStateProps {
  description?: string
  actionText?: string
  onAction?: () => void
}

export default function EmptyState({
  description = '暂无数据',
  actionText,
  onAction,
}: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-20">
      <Empty description={description}>
        {actionText && onAction && (
          <Button type="primary" onClick={onAction}>
            {actionText}
          </Button>
        )}
      </Empty>
    </div>
  )
}
