import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Card, Row, Col, Spin, Typography, Tag, Input, Space, Empty,
} from 'antd'
import { SearchOutlined, FileTextOutlined, RightOutlined } from '@ant-design/icons'
import apiClient from '../../api/client'

const { Title, Text } = Typography

interface Project {
  id: string
  name: string
  description?: string
  status: string
  created_at: string
}

interface Novel {
  id: string
  title: string
  word_count: number
  format: string
  created_at: string
}

export default function StoryBreakdownLanding() {
  const navigate = useNavigate()
  const [projects, setProjects] = useState<Project[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedProject, setSelectedProject] = useState<string | null>(null)
  const [novels, setNovels] = useState<Novel[]>([])
  const [novelsLoading, setNovelsLoading] = useState(false)
  const [searchText, setSearchText] = useState('')

  // 加载项目列表
  useEffect(() => {
    setLoading(true)
    apiClient.get('/projects?limit=50').then((res: any) => {
      setProjects(res.data?.items || [])
      if (res.data?.items?.length > 0) {
        setSelectedProject(res.data.items[0].id)
      }
    }).catch(() => {}).finally(() => setLoading(false))
  }, [])

  // 选中项目时加载小说
  useEffect(() => {
    if (!selectedProject) {
      setNovels([])
      return
    }
    setNovelsLoading(true)
    apiClient.get(`/projects/${selectedProject}/novels`).then((res: any) => {
      setNovels(res.data?.items || [])
    }).catch(() => {
      setNovels([])
    }).finally(() => setNovelsLoading(false))
  }, [selectedProject])

  const filteredNovels = novels.filter((n) =>
    !searchText || n.title.toLowerCase().includes(searchText.toLowerCase())
  )

  const handleEnterBreakdown = (projectId: string, novelId: string) => {
    navigate(`/projects/${projectId}/novels/${novelId}/story-breakdown`)
  }

  return (
    <div>
      <div style={{ marginBottom: 24 }}>
        <Title level={4} style={{ margin: 0 }}>剧情拆解</Title>
        <Text type="secondary">选择一个项目和小说，进入剧情拆解页面</Text>
      </div>

      {loading ? (
        <Spin style={{ display: 'block', margin: '60px auto' }} tip="加载项目列表..." />
      ) : projects.length === 0 ? (
        <Empty description="暂无项目，请先创建项目并导入小说" />
      ) : (
        <Row gutter={[16, 16]}>
          {/* 左侧：项目列表 */}
          <Col span={6}>
            <Card title="项目列表" size="small">
              <div style={{ maxHeight: 500, overflow: 'auto' }}>
                {projects.map((p) => (
                  <div
                    key={p.id}
                    onClick={() => setSelectedProject(p.id)}
                    style={{
                      padding: '10px 12px',
                      marginBottom: 4,
                      borderRadius: 6,
                      cursor: 'pointer',
                      background: selectedProject === p.id ? '#e6f4ff' : 'transparent',
                      border: selectedProject === p.id ? '1px solid #91caff' : '1px solid transparent',
                      transition: 'all 0.2s',
                    }}
                    onMouseEnter={(e) => {
                      if (selectedProject !== p.id) e.currentTarget.style.background = '#f5f5f5'
                    }}
                    onMouseLeave={(e) => {
                      if (selectedProject !== p.id) e.currentTarget.style.background = 'transparent'
                    }}
                  >
                    <div style={{ fontWeight: 500, fontSize: 13 }}>{p.name}</div>
                    <div style={{ fontSize: 12, color: '#999', marginTop: 2 }}>
                      <Tag color="default" style={{ fontSize: 10 }}>{p.status}</Tag>
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          </Col>

          {/* 右侧：小说列表 */}
          <Col span={18}>
            <Card
              title={
                selectedProject
                  ? `小说列表（${projects.find((p) => p.id === selectedProject)?.name || ''}）`
                  : '请选择项目'
              }
              size="small"
              extra={
                <Input
                  size="small"
                  placeholder="搜索小说..."
                  prefix={<SearchOutlined />}
                  value={searchText}
                  onChange={(e) => setSearchText(e.target.value)}
                  style={{ width: 200 }}
                  allowClear
                />
              }
            >
              {novelsLoading ? (
                <Spin style={{ display: 'block', margin: '40px auto' }} tip="加载小说..." />
              ) : !selectedProject ? (
                <Empty description="请从左侧选择一个项目" />
              ) : filteredNovels.length === 0 ? (
                <Empty description={searchText ? '未找到匹配的小说' : '该项目暂无小说，请先导入'} />
              ) : (
                <Row gutter={[12, 12]}>
                  {filteredNovels.map((novel) => (
                    <Col span={12} key={novel.id}>
                      <Card
                        size="small"
                        hoverable
                        onClick={() => handleEnterBreakdown(selectedProject!, novel.id)}
                        styles={{ body: { padding: '14px 16px' } }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                          <Space>
                            <FileTextOutlined style={{ fontSize: 18, color: '#1677ff' }} />
                            <div>
                              <Text strong style={{ fontSize: 14 }}>{novel.title}</Text>
                              <div>
                                <Text type="secondary" style={{ fontSize: 12 }}>
                                  {novel.word_count} 字 · {novel.format}
                                </Text>
                              </div>
                            </div>
                          </Space>
                          <RightOutlined style={{ color: '#bbb' }} />
                        </div>
                      </Card>
                    </Col>
                  ))}
                </Row>
              )}
            </Card>
          </Col>
        </Row>
      )}
    </div>
  )
}
