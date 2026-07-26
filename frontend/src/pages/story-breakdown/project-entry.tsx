import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Card, Row, Col, Spin, Typography, Input, Space, Empty,
} from 'antd'
import { SearchOutlined, FileTextOutlined, RightOutlined } from '@ant-design/icons'
import { novelApi } from '../../api/novelApi'
import type { Novel } from '../../types/novel'

const { Title, Text } = Typography

export default function ProjectStoryBreakdown() {
  const { id: projectId } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [novels, setNovels] = useState<Novel[]>([])
  const [loading, setLoading] = useState(true)
  const [searchText, setSearchText] = useState('')

  useEffect(() => {
    if (!projectId) return
    setLoading(true)
    novelApi.list(projectId).then((res: any) => {
      setNovels(res.data?.items || [])
    }).catch(() => {
      setNovels([])
    }).finally(() => setLoading(false))
  }, [projectId])

  const filteredNovels = novels.filter((n) =>
    !searchText || n.title.toLowerCase().includes(searchText.toLowerCase())
  )

  const handleEnterBreakdown = (novelId: string) => {
    navigate(`/projects/${projectId}/novels/${novelId}/story-breakdown`)
  }

  return (
    <div>
      <div style={{ marginBottom: 24 }}>
        <Title level={4} style={{ margin: 0 }}>脚本生成</Title>
        <Text type="secondary">选择一个小说，进入剧情拆解页面</Text>
      </div>

      {loading ? (
        <Spin style={{ display: 'block', margin: '60px auto' }} tip="加载小说列表..." />
      ) : filteredNovels.length === 0 ? (
        <Empty description={searchText ? '未找到匹配的小说' : '该项目暂无小说，请先导入'} />
      ) : (
        <Card
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
          <Row gutter={[12, 12]}>
            {filteredNovels.map((novel) => (
              <Col span={12} key={novel.id}>
                <Card
                  size="small"
                  hoverable
                  onClick={() => handleEnterBreakdown(novel.id)}
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
        </Card>
      )}
    </div>
  )
}
