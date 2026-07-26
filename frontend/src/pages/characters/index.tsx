import { useEffect, useState } from 'react'
import { Card, Button, Input, Modal, message, Space, Table, Image, Input as AntInput } from 'antd'
import { PlusOutlined, SearchOutlined, TeamOutlined, UserAddOutlined, SaveOutlined, EditOutlined } from '@ant-design/icons'
import { useNavigate, useParams } from 'react-router-dom'
import { useCharacterStore } from '../../stores/characterStore'
import { characterApi } from '../../api/characterApi'
import { novelApi } from '../../api/novelApi'
import type { Character } from '../../types/character'
import CharacterForm from '../../components/CharacterForm'
import EmptyState from '../../components/common/EmptyState'
import Loading from '../../components/common/Loading'

const { TextArea } = AntInput

interface EditingDescription {
  id: string
  description: string
}

export default function CharacterList() {
  const navigate = useNavigate()
  const { id } = useParams<{ id: string }>()
  const projectId = id
  const {
    characters,
    loading,
    fetchCharacters,
    createCharacter,
  } = useCharacterStore()

  const [searchText, setSearchText] = useState('')
  const [modalOpen, setModalOpen] = useState(false)
  const [createLoading, setCreateLoading] = useState(false)
  const [extractLoading, setExtractLoading] = useState(false)
  const [editingDescription, setEditingDescription] = useState<EditingDescription | null>(null)
  const [generatingImage, setGeneratingImage] = useState<string | null>(null)

  useEffect(() => {
    if (projectId) {
      fetchCharacters(projectId, { search: searchText })
    }
  }, [projectId, searchText, fetchCharacters])

  const handleSearch = (value: string) => {
    setSearchText(value)
  }

  const handleCreate = async (values: any) => {
    if (!projectId) return
    setCreateLoading(true)
    try {
      await createCharacter(projectId, values)
      message.success('人物创建成功')
      setModalOpen(false)
      fetchCharacters(projectId, { search: searchText })
    } catch (e: any) {
      message.error(e.response?.data?.detail || '创建失败')
    } finally {
      setCreateLoading(false)
    }
  }

  const handleExtract = async () => {
    if (!projectId) return
    setExtractLoading(true)
    try {
      const novelRes: any = await novelApi.list(projectId)
      const novels = novelRes.data?.items || novelRes.data || []
      if (novels.length === 0) {
        message.warning('当前项目没有小说，请先上传小说')
        return
      }

      const firstNovel = novels[0]
      let novelText = firstNovel.cleaned_text || firstNovel.raw_text || ''

      if (!novelText.trim()) {
        const novelDetailRes: any = await novelApi.getById(projectId, firstNovel.id)
        const novel = novelDetailRes.data
        novelText = novel.cleaned_text || novel.raw_text || ''
      }

      if (!novelText.trim()) {
        message.warning('小说内容为空')
        return
      }

      const res: any = await characterApi.extract(projectId, novelText)
      const createdCount = res.data?.total || 0
      message.success(`成功提取 ${createdCount} 个角色`)
      fetchCharacters(projectId, { search: searchText })
    } catch (e: any) {
      message.error(e.response?.data?.detail || '提取失败')
    } finally {
      setExtractLoading(false)
    }
  }

  const handleSaveDescription = async (record: Character) => {
    if (!editingDescription || !projectId) return
    try {
      await characterApi.update(projectId, record.id, { description: editingDescription.description })
      message.success('描述更新成功')
      setEditingDescription(null)
      fetchCharacters(projectId, { search: searchText })
    } catch (e: any) {
      message.error(e.response?.data?.detail || '更新失败')
    }
  }

  const handleGenerateImage = async (record: Character) => {
    if (!projectId) return
    setGeneratingImage(record.id)
    try {
      const res: any = await characterApi.generateImage(projectId, record.id)
      message.success(`角色「${res.data?.character_name}」形象生成成功`)
      fetchCharacters(projectId, { search: searchText })
    } catch (e: any) {
      message.error(e.response?.data?.detail || '生成失败')
    } finally {
      setGeneratingImage(null)
    }
  }

  const columns = [
    {
      title: '角色形象',
      key: 'image',
      width: 120,
      render: (_: any, record: Character) => {
        const imageUrl = record.image_url || (record.description
          ? `https://trae-api-cn.mchost.guru/api/ide/v1/text_to_image?prompt=${encodeURIComponent(record.description)}&image_size=landscape_16_9`
          : null)
        
        return (
          <div>
            {imageUrl ? (
              <Image
                src={imageUrl}
                alt={record.name}
                width={100}
                height={56}
                style={{ objectFit: 'cover', borderRadius: 4 }}
                preview={{ src: imageUrl }}
              />
            ) : (
              <div style={{ width: 100, height: 56, background: '#f5f5f5', borderRadius: 4, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#999', fontSize: 12 }}>
                <TeamOutlined />
              </div>
            )}
          </div>
        )
      },
    },
    {
      title: '角色信息',
      key: 'info',
      width: 180,
      render: (_: any, record: Character) => (
        <div>
          <div style={{ fontSize: 14, fontWeight: 600 }}>{record.name}</div>
          <div style={{ fontSize: 12, color: '#666', marginTop: 4 }}>
            {record.aliases || '暂无别名'}
          </div>
        </div>
      ),
    },
    {
      title: '角色描述',
      key: 'description',
      render: (_: any, record: Character) => {
        const isEditing = editingDescription?.id === record.id
        if (isEditing) {
          return (
            <div>
              <TextArea
                rows={3}
                value={editingDescription.description}
                onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setEditingDescription({ ...editingDescription, description: e.target.value })}
                style={{ marginBottom: 8 }}
              />
              <Space>
                <Button size="small" icon={<SaveOutlined />} onClick={() => handleSaveDescription(record)}>
                  保存
                </Button>
                <Button size="small" onClick={() => setEditingDescription(null)}>
                  取消
                </Button>
              </Space>
            </div>
          )
        }
        return (
          <div>
            <div style={{ fontSize: 12, color: '#666', lineHeight: 1.6, maxHeight: 80, overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {record.description || '暂无描述'}
            </div>
            {record.description && (
              <Button
                size="small"
                icon={<EditOutlined />}
                onClick={() => setEditingDescription({ id: record.id, description: record.description })}
                style={{ marginTop: 8 }}
              >
                编辑描述
              </Button>
            )}
          </div>
        )
      },
    },
    {
      title: '操作',
      key: 'action',
      width: 120,
      render: (_: any, record: Character) => (
        <Button
          size="small"
          loading={generatingImage === record.id}
          onClick={() => handleGenerateImage(record)}
        >
          生成形象
        </Button>
      ),
    },
  ]

  if (!projectId) {
    return <EmptyState description="请先选择一个项目" />
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <h2 style={{ margin: 0, fontSize: 20, fontWeight: 600 }}>人物IP管理</h2>
        <Space>
          <Button onClick={() => navigate(`/projects/${projectId}/characters/relations`)}>
            关系图
          </Button>
          <Button
            type="primary"
            icon={<UserAddOutlined />}
            loading={extractLoading}
            onClick={handleExtract}
          >
            一键提取角色
          </Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>
            新建人物
          </Button>
        </Space>
      </div>

      <Card style={{ marginBottom: 16 }}>
        <Input.Search
          placeholder="搜索角色姓名"
          allowClear
          onSearch={handleSearch}
          onChange={(e) => !e.target.value && handleSearch('')}
          style={{ width: 250 }}
          prefix={<SearchOutlined />}
        />
      </Card>

      {loading && characters.length === 0 ? (
        <Loading tip="加载人物列表..." />
      ) : characters.length === 0 ? (
        <EmptyState
          description="暂无人物，点击按钮创建第一个角色"
          actionText="新建人物"
          onAction={() => setModalOpen(true)}
        />
      ) : (
        <Card>
          <Table
            dataSource={characters}
            columns={columns}
            rowKey="id"
            pagination={{ pageSize: 10 }}
            scroll={{ x: 800 }}
          />
        </Card>
      )}

      <Modal
        title="新建人物"
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        footer={null}
        width={640}
      >
        <CharacterForm
          loading={createLoading}
          onSubmit={handleCreate}
          onCancel={() => setModalOpen(false)}
        />
      </Modal>
    </div>
  )
}