import { useEffect, useState, useCallback } from 'react'
import { Card, Row, Col, Avatar, message } from 'antd'
import { TeamOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { characterApi } from '../../api/characterApi'
import type { Character } from '../../types/character'
import ProjectFilter from '../../components/common/ProjectFilter'
import EmptyState from '../../components/common/EmptyState'
import Loading from '../../components/common/Loading'
import { formatDate } from '../../utils/format'

export default function CharacterGlobalList() {
  const navigate = useNavigate()
  const [characters, setCharacters] = useState<Character[]>([])
  const [loading, setLoading] = useState(false)
  const [projectId, setProjectId] = useState<string | undefined>(undefined)
  const [searchText, setSearchText] = useState('')

  const fetchAllCharacters = useCallback(async () => {
    setLoading(true)
    try {
      const params: { search?: string } = {}
      if (searchText) params.search = searchText

      let list: Character[] = []
      if (projectId) {
        const res: any = await characterApi.list(projectId, params)
        list = res.data?.items || res.data || []
      } else {
        const res: any = await characterApi.listAll(params)
        list = res.data?.items || res.data || []
      }
      setCharacters(Array.isArray(list) ? list : [])
    } catch {
      message.error('获取角色列表失败')
      setCharacters([])
    } finally {
      setLoading(false)
    }
  }, [projectId, searchText])

  useEffect(() => {
    fetchAllCharacters()
  }, [fetchAllCharacters])

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <h2 style={{ margin: 0, fontSize: 20, fontWeight: 600 }}>人物IP</h2>
      </div>

      <Card style={{ marginBottom: 16 }}>
        <ProjectFilter
          projectId={projectId}
          onProjectChange={setProjectId}
          searchPlaceholder="搜索角色名称"
          searchValue={searchText}
          onSearchChange={setSearchText}
        />
      </Card>

      {loading ? (
        <Loading tip="加载人物列表..." />
      ) : characters.length === 0 ? (
        <EmptyState description="暂无人物数据" />
      ) : (
        <>
          <div style={{ marginBottom: 12, color: '#666', fontSize: 13 }}>
            共 {characters.length} 个角色
          </div>
          <Row gutter={[16, 16]}>
            {characters.map((character) => (
              <Col key={character.id} xs={24} sm={12} md={8} lg={6} xl={4}>
                <Card
                  hoverable
                  onClick={() => {
                    if (projectId) {
                      navigate(`/projects/${projectId}/characters/${character.id}`)
                    } else {
                      navigate(`/characters/${character.id}?projectId=${character.project_id}`)
                    }
                  }}
                  style={{ height: '100%', cursor: 'pointer' }}
                  styles={{ body: { padding: '16px 12px' } }}
                >
                  <div style={{ textAlign: 'center' }}>
                    <Avatar
                      size={56}
                      icon={<TeamOutlined />}
                      style={{ backgroundColor: '#1677ff', marginBottom: 8 }}
                    />
                    <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 4, textAlign: 'center' }}>
                      {character.name}
                    </div>
                    <div style={{ fontSize: 11, color: '#999' }}>
                      {character.aliases || '暂无别名'}
                    </div>
                    <div style={{ marginTop: 4, fontSize: 12, color: '#999' }}>
                      创建于 {formatDate(character.created_at, 'YYYY-MM-DD')}
                    </div>
                  </div>
                </Card>
              </Col>
            ))}
          </Row>
        </>
      )}
    </div>
  )
}
