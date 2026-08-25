import { useNavigate, useLocation } from 'react-router-dom'
import { Layout, Menu } from 'antd'
import {
  DashboardOutlined,
  ProjectOutlined,
  FileTextOutlined,
  TeamOutlined,
  ApartmentOutlined,
  PictureOutlined,
  LayoutOutlined,
  ThunderboltOutlined,
  PictureFilled,
  CheckCircleOutlined,
  ExportOutlined,
  SafetyOutlined,
  ApiOutlined,
  QuestionCircleOutlined,
} from '@ant-design/icons'
import { preloadByPath } from '../../routeComponents'

const { Sider } = Layout

interface MenuItem {
  key: string
  icon: React.ReactNode
  label: string
  path?: string
  children?: MenuItem[]
}

const menuItems: MenuItem[] = [
  { key: 'dashboard', icon: <DashboardOutlined />, label: '工作台', path: '/' },
  { key: 'tasks', icon: <CheckCircleOutlined />, label: '任务中心', path: '/tasks' },
  { key: 'projects', icon: <ProjectOutlined />, label: '项目管理', path: '/projects' },
  { key: 'novels', icon: <FileTextOutlined />, label: '小说管理', path: '/novels' },
  { key: 'characters', icon: <TeamOutlined />, label: '人物IP', path: '/characters' },
  { key: 'story-breakdown', icon: <ApartmentOutlined />, label: '剧情拆解', path: '/story-breakdown' },
  { key: 'storyboard', icon: <PictureOutlined />, label: '分镜中心', path: '/storyboard' },
  { key: 'layout', icon: <LayoutOutlined />, label: 'AI排版', path: '/layout' },
  { key: 'generation', icon: <PictureFilled />, label: '生图中心', path: '/generation' },
  { key: 'prompts', icon: <ThunderboltOutlined />, label: 'Prompt中心', path: '/prompts' },
  { key: 'export', icon: <ExportOutlined />, label: '导出中心', path: '/export' },
  { key: 'models', icon: <ApiOutlined />, label: '模型配置', path: '/models' },
  { key: 'plugins', icon: <ApiOutlined />, label: '插件中心', path: '/plugins' },
  { key: 'system', icon: <SafetyOutlined />, label: '系统管理', path: '/system' },
  { key: 'help', icon: <QuestionCircleOutlined />, label: '帮助中心', path: '/help' },
]

function findSelectedKey(pathname: string): string {
  // 精确匹配：直接检查 pathname 是否等于 item.path
  const exactMatch = menuItems.find((item) => item.path && item.path !== '/' && pathname === item.path)
  if (exactMatch) return exactMatch.key

  // 模糊匹配：按路径长度降序，优先匹配更具体的路径
  const startsWithItems = menuItems
    .filter((item) => item.path && item.path !== '/')
    .sort((a, b) => (b.path?.length || 0) - (a.path?.length || 0))

  const item = startsWithItems.find((item) => item.path && pathname.startsWith(item.path))
  if (item) return item.key
  return pathname === '/' ? 'dashboard' : 'dashboard'
}

export default function Sidebar() {
  const navigate = useNavigate()
  const location = useLocation()
  const selectedKey = findSelectedKey(location.pathname)

  const handleMenuClick = (info: { key: string }) => {
    const item = menuItems.find((m) => m.key === info.key)
    if (item?.path) {
      navigate(item.path)
    }
  }

  return (
    <Sider
      width={260}
      theme="dark"
      style={{
        overflow: 'auto',
        height: '100vh',
        position: 'fixed',
        left: 0,
        top: 0,
        bottom: 0,
      }}
    >
      <div
        style={{
          height: 64,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          borderBottom: '1px solid rgba(255,255,255,0.1)',
        }}
      >
        <h1 style={{ color: '#fff', fontSize: 18, fontWeight: 600, margin: 0 }}>
          🎨 AI Webtoon
        </h1>
      </div>
      <Menu
        theme="dark"
        mode="inline"
        selectedKeys={[selectedKey]}
        items={menuItems.map((item) => ({
          key: item.key,
          icon: item.icon,
          label: (
            <div
              onMouseEnter={() => {
                if (item.path) preloadByPath(item.path)
              }}
            >
              {item.label}
            </div>
          ),
        }))}
        onClick={handleMenuClick}
      />
    </Sider>
  )
}
