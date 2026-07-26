import { useEffect, useState, useRef, useCallback } from 'react'
import { Outlet, useLocation, matchPath, useNavigate } from 'react-router-dom'
import { Layout, Breadcrumb, Avatar, Dropdown, theme, Badge, Button, List, Typography, Space, Spin, Empty } from 'antd'
import { UserOutlined, LogoutOutlined, BellOutlined, CheckOutlined, RightOutlined } from '@ant-design/icons'
import Sidebar from './Sidebar'
import SearchBar from '../SearchBar'
import { useAuthStore } from '../../stores/authStore'
import { notificationApi } from '../../api/notificationApi'
import type { NotificationItem } from '../../api/notificationApi'

const { Header, Content } = Layout
const { Text } = Typography

const breadcrumbMap: Record<string, string> = {
  '/': '工作台',
  '/tasks': '任务中心',
  '/projects': '项目管理',
  '/novels': '小说管理',
  '/characters': '人物IP',
  '/story-breakdown': '剧情拆解',
  '/storyboard': '分镜中心',
  '/layout': 'AI排版',
  '/text-center': '文本中心',
  '/prompts': 'Prompt中心',
  '/generation': '生图中心',
  '/quality': '质量控制',
  '/editor': '漫画编辑器',
  '/export': '导出中心',
  '/models': '模型配置',
  '/resources': '资源中心',
  '/plugins': '插件中心',
  '/system': '系统管理',
  '/help': '帮助中心',
  '/notifications': '通知中心',
}

function getBreadcrumbItems(pathname: string) {
  const items: { title: string; path?: string }[] = [{ title: 'AI Webtoon Factory', path: '/' }]

  // 尝试匹配静态路由
  if (breadcrumbMap[pathname]) {
    items.push({ title: breadcrumbMap[pathname] })
    return items
  }

  // 动态路由定义（按路径从短到长排列，用于构建完整层级）
  const routeHierarchy: { pattern: string; name: string; parentPattern?: string }[] = [
    { pattern: '/projects', name: '项目管理' },
    { pattern: '/projects/:id', name: '项目详情', parentPattern: '/projects' },
    { pattern: '/projects/:id/novels', name: '小说管理', parentPattern: '/projects/:id' },
    { pattern: '/projects/:id/novels/:novelId', name: '小说详情', parentPattern: '/projects/:id/novels' },
    { pattern: '/projects/:id/novels/:novelId/editor', name: '章节编辑', parentPattern: '/projects/:id/novels/:novelId' },
    { pattern: '/projects/:id/characters', name: '人物IP管理', parentPattern: '/projects/:id' },
    { pattern: '/projects/:id/characters/relations', name: '人物关系图', parentPattern: '/projects/:id/characters' },
    { pattern: '/projects/:id/characters/:characterId', name: '人物详情', parentPattern: '/projects/:id/characters' },
    { pattern: '/projects/:id/story-breakdown', name: '脚本生成', parentPattern: '/projects/:id' },
    { pattern: '/projects/:id/novels/:novelId/story-breakdown', name: '剧情拆解', parentPattern: '/projects/:id/story-breakdown' },
    { pattern: '/projects/:id/storyboard', name: '分镜设计', parentPattern: '/projects/:id' },
    { pattern: '/projects/:id/novels/:novelId/storyboard', name: '分镜详情', parentPattern: '/projects/:id/storyboard' },
    { pattern: '/projects/:id/layout', name: 'AI排版', parentPattern: '/projects/:id' },
    { pattern: '/projects/:id/novels/:novelId/layout', name: '排版详情', parentPattern: '/projects/:id/layout' },
    { pattern: '/projects/:id/prompts', name: 'Prompt中心', parentPattern: '/projects/:id' },
    { pattern: '/projects/:id/generation', name: '生图中心', parentPattern: '/projects/:id' },
    { pattern: '/projects/:id/quality', name: '质量控制', parentPattern: '/projects/:id' },
    { pattern: '/projects/:id/worlds', name: '世界观', parentPattern: '/projects/:id' },
    { pattern: '/projects/:id/worlds/:worldId', name: '世界观详情', parentPattern: '/projects/:id/worlds' },
    { pattern: '/projects/:id/style-templates', name: '风格模板', parentPattern: '/projects/:id' },
    { pattern: '/projects/:id/editor', name: '漫画编辑器', parentPattern: '/projects/:id' },
    { pattern: '/projects/:id/editor/:pageId', name: '编辑页面', parentPattern: '/projects/:id/editor' },
    { pattern: '/projects/:id/export', name: '导出中心', parentPattern: '/projects/:id' },
  ]

  // 找到匹配当前路径的 route
  const matchedRoute = routeHierarchy.find((r) => matchPath(r.pattern, pathname))
  if (!matchedRoute) {
    items.push({ title: '未知页面' })
    return items
  }

  // 从当前路径提取所有参数（用于后续替换父级路由的 :param）
  const currentMatch = matchPath(matchedRoute.pattern, pathname)
  const params = currentMatch?.params || {}

  // 构建完整祖先链：从最顶层祖先到当前路由
  const chain: typeof routeHierarchy = []
  let current: typeof matchedRoute | undefined = matchedRoute
  while (current) {
    chain.unshift(current)
    current = current.parentPattern
      ? routeHierarchy.find((r) => r.pattern === current!.parentPattern)
      : undefined
  }

  // 将祖先链逐个加入 breadcrumb
  for (const route of chain) {
    // 当前页面（最后一项）不加 path（不可点击）
    if (route === chain[chain.length - 1]) {
      items.push({ title: route.name })
    } else {
      let resolvedPath = route.pattern
      for (const [key, value] of Object.entries(params)) {
        resolvedPath = resolvedPath.replace(`:${key}`, value as string)
      }
      items.push({ title: route.name, path: resolvedPath })
    }
  }

  return items
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

export default function AppLayout() {
  const location = useLocation()
  const navigate = useNavigate()
  const { token: themeToken } = theme.useToken()
  const logout = useAuthStore((state) => state.logout)
  const user = useAuthStore((state) => state.user)

  const [unreadCount, setUnreadCount] = useState(0)
  const [notifOpen, setNotifOpen] = useState(false)
  const [notifList, setNotifList] = useState<NotificationItem[]>([])
  const [notifLoading, setNotifLoading] = useState(false)
  const notifRef = useRef<HTMLDivElement>(null)

  const breadcrumbItems = getBreadcrumbItems(location.pathname)

  // 获取未读数量
  const fetchUnreadCount = useCallback(async () => {
    try {
      const res: any = await notificationApi.unreadCount()
      setUnreadCount(res.data.unread_count || 0)
    } catch {
      // ignore
    }
  }, [])

  useEffect(() => {
    fetchUnreadCount()
    // 每30秒轮询
    const timer = setInterval(fetchUnreadCount, 30000)
    return () => clearInterval(timer)
  }, [fetchUnreadCount])

  // 打开通知下拉
  const handleNotifOpen = async () => {
    setNotifOpen(true)
    setNotifLoading(true)
    try {
      const res: any = await notificationApi.list({ page: 1, page_size: 10 })
      setNotifList(res.data.items || [])
    } catch {
      setNotifList([])
    } finally {
      setNotifLoading(false)
    }
  }

  // 点击外部关闭通知
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (notifRef.current && !notifRef.current.contains(e.target as Node)) {
        setNotifOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  // 全部标为已读
  const handleMarkAllRead = async () => {
    try {
      await notificationApi.markAllAsRead()
      setUnreadCount(0)
      setNotifList((prev) => prev.map((n) => ({ ...n, is_read: true })))
    } catch {
      // ignore
    }
  }

  // 标记单条已读并跳转
  const handleNotifClick = async (item: NotificationItem) => {
    if (!item.is_read) {
      try {
        await notificationApi.markAsRead(item.id)
        setUnreadCount((prev) => Math.max(0, prev - 1))
        setNotifList((prev) => prev.map((n) => (n.id === item.id ? { ...n, is_read: true } : n)))
      } catch {
        // ignore
      }
    }
    setNotifOpen(false)
    if (item.related_url) {
      navigate(item.related_url)
    }
  }

  const dropdownItems = {
    items: [
      {
        key: 'user',
        icon: <UserOutlined />,
        label: user?.username || '用户',
        disabled: true,
      },
      { type: 'divider' as const },
      {
        key: 'logout',
        icon: <LogoutOutlined />,
        label: '退出登录',
        danger: true,
        onClick: logout,
      },
    ],
  }

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sidebar />
      <Layout style={{ marginLeft: 260 }}>
        <Header
          style={{
            padding: '0 24px',
            background: themeToken.colorBgContainer,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            borderBottom: `1px solid ${themeToken.colorBorderSecondary}`,
            height: 56,
            position: 'sticky',
            top: 0,
            zIndex: 10,
          }}
        >
          <Breadcrumb
            items={breadcrumbItems.map((item) => ({
              title: item.path ? (
                <a onClick={() => navigate(item.path!)} style={{ cursor: 'pointer' }}>
                  {item.title}
                </a>
              ) : (
                item.title
              ),
            }))}
          />
          <Space size={16}>
            <SearchBar />
            {/* 通知铃铛 */}
            <div ref={notifRef} style={{ position: 'relative' }}>
              <Badge count={unreadCount} size="small" offset={[-2, 2]}>
                <BellOutlined
                  style={{ fontSize: 18, cursor: 'pointer', color: '#595959' }}
                  onClick={handleNotifOpen}
                />
              </Badge>
              {notifOpen && (
                <div
                  style={{
                    position: 'absolute',
                    top: '100%',
                    right: 0,
                    marginTop: 8,
                    width: 360,
                    background: '#fff',
                    borderRadius: 8,
                    boxShadow: '0 4px 12px rgba(0,0,0,0.12)',
                    maxHeight: 480,
                    overflow: 'auto',
                    zIndex: 1050,
                  }}
                >
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      padding: '12px 16px',
                      borderBottom: '1px solid #f0f0f0',
                    }}
                  >
                    <Text strong style={{ fontSize: 14 }}>通知</Text>
                    {unreadCount > 0 && (
                      <Button type="link" size="small" icon={<CheckOutlined />} onClick={handleMarkAllRead}>
                        全部已读
                      </Button>
                    )}
                  </div>
                  {notifLoading ? (
                    <div style={{ padding: 24, textAlign: 'center' }}><Spin size="small" /></div>
                  ) : notifList.length === 0 ? (
                    <Empty description="暂无通知" image={Empty.PRESENTED_IMAGE_SIMPLE} style={{ padding: 24 }} />
                  ) : (
                    <List
                      dataSource={notifList.slice(0, 10)}
                      renderItem={(item) => (
                        <List.Item
                          style={{
                            cursor: 'pointer',
                            padding: '10px 16px',
                            background: item.is_read ? 'transparent' : '#f6f8ff',
                            borderBottom: '1px solid #f5f5f5',
                          }}
                          onClick={() => handleNotifClick(item)}
                        >
                          <List.Item.Meta
                            title={
                              <Text
                                strong={!item.is_read}
                                style={{ fontSize: 13, color: item.is_read ? '#666' : undefined }}
                                ellipsis
                              >
                                {item.title}
                              </Text>
                            }
                            description={
                              <Text type="secondary" style={{ fontSize: 12 }}>
                                {formatTime(item.created_at)}
                              </Text>
                            }
                          />
                        </List.Item>
                      )}
                    />
                  )}
                  <div
                    style={{
                      padding: '8px 16px',
                      borderTop: '1px solid #f0f0f0',
                      textAlign: 'center',
                    }}
                  >
                    <Button
                      type="link"
                      size="small"
                      icon={<RightOutlined />}
                      onClick={() => { setNotifOpen(false); navigate('/notifications') }}
                    >
                      查看全部通知
                    </Button>
                  </div>
                </div>
              )}
            </div>
            <Dropdown menu={dropdownItems} placement="bottomRight">
              <Avatar
                style={{ cursor: 'pointer', backgroundColor: themeToken.colorPrimary }}
                icon={<UserOutlined />}
              />
            </Dropdown>
          </Space>
        </Header>
        <Content
          style={{
            margin: 24,
            minHeight: 'calc(100vh - 56px - 48px)',
          }}
        >
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  )
}
