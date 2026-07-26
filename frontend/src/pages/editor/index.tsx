import { useEffect, useState } from 'react'
import { Card, Row, Col, Select, Badge } from 'antd'
import { EditOutlined, PictureOutlined } from '@ant-design/icons'
import { useNavigate, useParams } from 'react-router-dom'
import { useProjectStore } from '../../stores/projectStore'
import { useEditorStore } from '../../stores/editorStore'
import type { PageInfo } from '../../stores/editorStore'
import apiClient from '../../api/client'
import EmptyState from '../../components/common/EmptyState'
import Loading from '../../components/common/Loading'
import { PROJECT_STATUS_MAP } from '../../types'

export default function EditorList() {
  const navigate = useNavigate()
  const { id: projectId } = useParams<{ id: string }>()
  const { projects, fetchProjects } = useProjectStore()
  const { pages, setPages, loading, setLoading } = useEditorStore()
  const [selectedProjectId, setSelectedProjectId] = useState<string | undefined>(projectId)

  useEffect(() => {
    fetchProjects()
  }, [fetchProjects])

  useEffect(() => {
    if (selectedProjectId) {
      loadPages(selectedProjectId)
    }
  }, [selectedProjectId])

  const loadPages = async (pid: string) => {
    setLoading(true)
    try {
      const res: any = await apiClient.get(`/projects/${pid}/pages`)
      const data = (res as { data?: PageInfo[] }).data || []
      setPages(data)
    } catch {
      // 模拟数据
      const mockPages: PageInfo[] = Array.from({ length: 6 }, (_, i) => ({
        id: `page-${i + 1}`,
        page_number: i + 1,
        panel_count: 3 + (i % 2),
        status: i < 4 ? 'completed' : 'draft',
      }))
      setPages(mockPages)
    } finally {
      setLoading(false)
    }
  }

  const handleProjectChange = (value: string) => {
    setSelectedProjectId(value)
    navigate(`/projects/${value}/editor`, { replace: true })
  }

  const handlePageClick = (page: PageInfo) => {
    if (selectedProjectId) {
      navigate(`/projects/${selectedProjectId}/editor/${page.id}`)
    }
  }

  const currentProject = projects.find((p) => p.id === selectedProjectId)

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <h2 style={{ margin: 0, fontSize: 20, fontWeight: 600 }}>漫画编辑器</h2>
      </div>

      <Card style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ fontWeight: 500, whiteSpace: 'nowrap' }}>选择项目：</span>
          <Select
            placeholder="请选择项目"
            style={{ width: 300 }}
            value={selectedProjectId}
            onChange={handleProjectChange}
            options={projects.map((p) => ({
              label: p.name,
              value: p.id,
            }))}
          />
          {currentProject && (
            <Badge
              status={
                currentProject.status === 'completed'
                  ? 'success'
                  : currentProject.status === 'editing'
                    ? 'warning'
                    : 'processing'
              }
              text={PROJECT_STATUS_MAP[currentProject.status as keyof typeof PROJECT_STATUS_MAP] || currentProject.status}
            />
          )}
        </div>
      </Card>

      {!selectedProjectId ? (
        <EmptyState description="请先选择一个项目开始编辑" />
      ) : loading ? (
        <Loading tip="加载页面列表..." />
      ) : pages.length === 0 ? (
        <EmptyState description="该项目暂无页面，请先生成漫画内容" />
      ) : (
        <>
          <div style={{ marginBottom: 12, color: '#666', fontSize: 13 }}>
            共 {pages.length} 页
          </div>
          <Row gutter={[16, 16]}>
            {pages.map((page) => (
              <Col key={page.id} xs={12} sm={8} md={6} lg={4}>
                <Card
                  hoverable
                  onClick={() => handlePageClick(page)}
                  style={{ height: '100%' }}
                  cover={
                    <div
                      style={{
                        height: 180,
                        background: '#1a1a2e',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        color: '#666',
                        fontSize: 13,
                      }}
                    >
                      {page.thumbnail_url ? (
                        <img
                          src={page.thumbnail_url}
                          alt={`第 ${page.page_number} 页`}
                          style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                        />
                      ) : (
                        <PictureOutlined style={{ fontSize: 32, opacity: 0.3 }} />
                      )}
                    </div>
                  }
                >
                  <Card.Meta
                    title={
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span>第 {page.page_number} 页</span>
                        <Badge
                          status={page.status === 'completed' ? 'success' : 'default'}
                        />
                      </div>
                    }
                    description={
                      <div style={{ fontSize: 12, color: '#999' }}>
                        <EditOutlined style={{ marginRight: 4 }} />
                        {page.panel_count} 个分镜
                      </div>
                    }
                  />
                </Card>
              </Col>
            ))}
          </Row>
        </>
      )}
    </div>
  )
}
