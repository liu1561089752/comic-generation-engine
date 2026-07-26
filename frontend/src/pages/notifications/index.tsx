import { useEffect, useState, useCallback } from 'react'
import {
  Card, List, Tag, Button, Typography, Spin, Empty, Space, Badge,
} from 'antd'
import {
  CheckCircleOutlined, CloseCircleOutlined, InfoCircleOutlined,
  WarningOutlined, BellOutlined, CheckOutlined,
} from '@ant-design/icons'
import { notificationApi } from '../../api/notificationApi'
import type { NotificationItem, NotificationsMeta } from '../../api/notificationApi'

const { Text } = Typography

const typeConfig: Record<string, { color: string; icon: React.ReactNode }> = {
  task_complete: { color: 'success', icon: <CheckCircleOutlined /> },
  task_failed: { color: 'error', icon: <CloseCircleOutlined /> },
  system: { color: 'processing', icon: <InfoCircleOutlined /> },
  info: { color: 'processing', icon: <InfoCircleOutlined /> },
  warning: { color: 'warning', icon: <WarningOutlined /> },
}

function getTypeConfig(type: string) {
  return typeConfig[type] || { color: 'default', icon: <BellOutlined /> }
}

function formatTime(timeStr: string) {
  const date = new Date(timeStr)
  const now = new Date()
  const diff = now.getTime() - date.getTime()
  const minutes = Math.floor(diff / 60000)
  const hours = Math.floor(diff / 3600000)
  const days = Math.floor(diff / 86400000)

  if (minutes < 1) return '刚刚'
  if (minutes < 60) return `${minutes}分钟前`
  if (hours < 24) return `${hours}小时前`
  if (days < 7) return `${days}天前`
  return date.toLocaleDateString('zh-CN')
}

export default function NotificationsPage() {
  const [loading, setLoading] = useState(true)
  const [list, setList] = useState<NotificationItem[]>([])
  const [meta, setMeta] = useState<NotificationsMeta | null>(null)
  const [page, setPage] = useState(1)

  const fetchData = useCallback(async (p: number) => {
    setLoading(true)
    try {
      const res: any = await notificationApi.list({ page: p, page_size: 20 })
      setList(res.data.items)
      setMeta(res.data.meta)
    } catch (e) {
      console.error('获取通知失败:', e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchData(page) }, [page, fetchData])

  const handleMarkAsRead = async (id: string) => {
    try {
      await notificationApi.markAsRead(id)
      setList((prev) => prev.map((n) => (n.id === id ? { ...n, is_read: true } : n)))
    } catch (e) {
      console.error('标记已读失败:', e)
    }
  }

  const handleMarkAllAsRead = async () => {
    try {
      await notificationApi.markAllAsRead()
      setList((prev) => prev.map((n) => ({ ...n, is_read: true })))
      if (meta) setMeta({ ...meta, unread_count: 0 })
    } catch (e) {
      console.error('全部标记失败:', e)
    }
  }

  return (
    <Card
      title={
        <Space>
          <BellOutlined />
          <span>通知中心</span>
          {meta && meta.unread_count > 0 && (
            <Badge count={meta.unread_count} style={{ backgroundColor: '#ff4d4f' }} />
          )}
        </Space>
      }
      extra={
        meta && meta.unread_count > 0 ? (
          <Button type="link" icon={<CheckOutlined />} onClick={handleMarkAllAsRead}>
            全部标为已读
          </Button>
        ) : null
      }
    >
      {loading ? (
        <div style={{ textAlign: 'center', padding: 48 }}><Spin size="large" /></div>
      ) : list.length === 0 ? (
        <Empty description="暂无通知" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      ) : (
        <>
          <List
            dataSource={list}
            renderItem={(item) => {
              const cfg = getTypeConfig(item.type)
              return (
                <List.Item
                  style={{
                    cursor: 'pointer',
                    padding: '12px 16px',
                    background: item.is_read ? 'transparent' : '#f6f8ff',
                    borderRadius: 6,
                    marginBottom: 4,
                    transition: 'background 0.2s',
                  }}
                  actions={
                    !item.is_read
                      ? [
                          <Button
                            type="link"
                            size="small"
                            icon={<CheckOutlined />}
                            onClick={() => handleMarkAsRead(item.id)}
                          >
                            标为已读
                          </Button>,
                        ]
                      : undefined
                  }
                >
                  <List.Item.Meta
                    avatar={
                      <Tag color={cfg.color} style={{ fontSize: 16, padding: '4px 6px' }}>
                        {cfg.icon}
                      </Tag>
                    }
                    title={
                      <Space size={8}>
                        <Text strong={!item.is_read} style={{ color: item.is_read ? '#666' : undefined }}>
                          {item.title}
                        </Text>
                        {!item.is_read && (
                          <Badge dot color="#1890ff" />
                        )}
                        {item.priority === 'high' && (
                          <Tag color="red" style={{ fontSize: 10, lineHeight: '16px' }}>重要</Tag>
                        )}
                      </Space>
                    }
                    description={
                      <Space direction="vertical" size={2}>
                        {item.description && (
                          <Text type="secondary" style={{ fontSize: 13 }}>
                            {item.description}
                          </Text>
                        )}
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          {formatTime(item.created_at)}
                        </Text>
                      </Space>
                    }
                  />
                </List.Item>
              )
            }}
          />
          {meta && (
            <div style={{ textAlign: 'center', padding: '12px 0 0' }}>
              <Text type="secondary" style={{ fontSize: 13 }}>
                共 {meta.total} 条通知，当前第 {meta.page} 页
              </Text>
              <Space style={{ marginLeft: 16 }}>
                <Button
                  size="small"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                >
                  上一页
                </Button>
                <Button
                  size="small"
                  disabled={page * (meta?.page_size || 20) >= (meta?.total || 0)}
                  onClick={() => setPage((p) => p + 1)}
                >
                  下一页
                </Button>
              </Space>
            </div>
          )}
        </>
      )}
    </Card>
  )
}
