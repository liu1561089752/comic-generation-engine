import { useEffect, useState, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Button, Space, Card, Select, Typography, message, Modal, Table, Image, Popover, Input } from 'antd'
import { ArrowLeftOutlined, DownloadOutlined, UserAddOutlined } from '@ant-design/icons'
import ReactEChartsCore from 'echarts-for-react'
import { useCharacterStore } from '../../stores/characterStore'
import { useProjectStore } from '../../stores/projectStore'
import { characterApi } from '../../api/characterApi'
import { novelApi } from '../../api/novelApi'
import Loading from '../../components/common/Loading'
import type { Character } from '../../types/character'

const { Title } = Typography
const { TextArea } = Input

interface GraphNode {
  id: string
  name: string
  symbolSize: number
  itemStyle: { color: string }
}

interface GraphLink {
  source: string
  target: string
  label: { show: boolean; formatter: string }
}

interface NovelOption {
  id: string
  title: string
}

export default function CharacterRelations() {
  const { id: projectId } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const chartRef = useRef<any>(null)
  const { characters, fetchCharacters } = useCharacterStore()
  const { projects, fetchProjects, loading: projectLoading } = useProjectStore()

  const [selectedProjectId, setSelectedProjectId] = useState<string | undefined>(projectId)
  const [graphData, setGraphData] = useState<{ nodes: GraphNode[]; links: GraphLink[] }>({
    nodes: [],
    links: [],
  })
  const [extractModalOpen, setExtractModalOpen] = useState(false)
  const [extractLoading, setExtractLoading] = useState(false)
  const [novelOptions, setNovelOptions] = useState<NovelOption[]>([])
  const [selectedNovelId, setSelectedNovelId] = useState<string | undefined>(undefined)
  const [novelText, setNovelText] = useState('')
  const [previewImage, setPreviewImage] = useState<string | undefined>(undefined)
  const [previewModalOpen, setPreviewModalOpen] = useState(false)
  const [editingDescription, setEditingDescription] = useState<{ characterId: string; description: string } | null>(null)

  useEffect(() => {
    fetchProjects()
  }, [])

  useEffect(() => {
    if (selectedProjectId) {
      fetchCharacters(selectedProjectId)
      loadNovels(selectedProjectId)
    }
  }, [selectedProjectId])

  useEffect(() => {
    const nodes: GraphNode[] = characters.map((c) => ({
      id: c.id,
      name: c.name,
      symbolSize: 50,
      itemStyle: { color: '#1677ff' },
    }))

    const links: GraphLink[] = []
    if (nodes.length > 0) {
      const firstNode = nodes[0]
      nodes.forEach((node) => {
        if (node.id !== firstNode.id) {
          links.push({
            source: firstNode.id,
            target: node.id,
            label: { show: true, formatter: '关联' },
          })
        }
      })
    }

    setGraphData({ nodes, links })
  }, [characters])

  const loadNovels = async (projId: string) => {
    try {
      const res: any = await novelApi.list(projId)
      const novels = res.data?.items || res.data || []
      setNovelOptions(novels.map((n: any) => ({ id: n.id, title: n.title })))
    } catch (e) {
      console.error('加载小说列表失败:', e)
    }
  }

  const handleProjectChange = (value: string) => {
    setSelectedProjectId(value)
    navigate(`/projects/${value}/characters/relations`, { replace: true })
  }

  const handleExportPNG = () => {
    if (chartRef.current) {
      try {
        const chart = chartRef.current.getEchartsInstance()
        const dataUrl = chart.getDataURL({
          type: 'png',
          pixelRatio: 2,
          backgroundColor: '#fff',
        })
        const link = document.createElement('a')
        link.href = dataUrl
        link.download = `人物关系图_${new Date().toISOString().slice(0, 10)}.png`
        link.click()
        message.success('关系图已导出')
      } catch {
        message.error('导出失败')
      }
    }
  }

  const handleNovelChange = async (value: string) => {
    setSelectedNovelId(value)
    try {
      const res: any = await novelApi.getById(selectedProjectId!, value)
      const novel = res.data
      const chapters: any[] = novel.chapters || []
      const text = chapters.map((c: any) => c.content || '').join('\n\n')
      setNovelText(text)
    } catch (e) {
      console.error('加载小说内容失败:', e)
    }
  }

  const handleExtract = async () => {
    if (!selectedProjectId || !novelText.trim()) {
      message.warning('请先选择小说并确保内容不为空')
      return
    }
    setExtractLoading(true)
    try {
      const res: any = await characterApi.extract(selectedProjectId, novelText)
      const createdCount = res.data?.total || 0
      message.success(`成功提取 ${createdCount} 个角色`)
      setExtractModalOpen(false)
      setNovelText('')
      setSelectedNovelId(undefined)
      fetchCharacters(selectedProjectId)
    } catch (e: any) {
      message.error(e.response?.data?.detail || '提取失败')
    } finally {
      setExtractLoading(false)
    }
  }

  const handlePreviewImage = (imageUrl?: string) => {
    if (imageUrl) {
      setPreviewImage(imageUrl)
      setPreviewModalOpen(true)
    }
  }

  const handleSaveDescription = async (characterId: string, description: string) => {
    if (!selectedProjectId) return
    try {
      await characterApi.update(selectedProjectId, characterId, {
        name: characters.find((c) => c.id === characterId)?.name || '',
        aliases: characters.find((c) => c.id === characterId)?.aliases || '',
        description,
      })
      message.success('描述已更新')
      setEditingDescription(null)
      fetchCharacters(selectedProjectId)
    } catch {
      message.error('更新失败')
    }
  }

  const getGraphOption = () => {
    return {
      title: {
        text: '人物关系图',
        left: 'center',
      },
      tooltip: {
        show: true,
        formatter: (params: any) => {
          if (params.dataType === 'node') {
            const node = params.data as GraphNode
            return `<strong>${node.name}</strong>`
          }
          if (params.dataType === 'edge') {
            return `关系: ${params.data.label?.formatter || '关联'}`
          }
          return ''
        },
      },
      series: [
        {
          type: 'graph',
          layout: 'force',
          force: {
            repulsion: 400,
            edgeLength: [100, 200],
            gravity: 0.1,
          },
          roam: true,
          draggable: true,
          data: graphData.nodes,
          links: graphData.links,
          categories: [{ name: '人物' }],
          label: {
            show: true,
            position: 'bottom',
            fontSize: 13,
            fontWeight: 'bold' as const,
            color: '#333',
          },
          edgeSymbol: ['circle', 'arrow'],
          edgeSymbolSize: [4, 10],
          lineStyle: {
            color: 'source',
            width: 2,
            curveness: 0.3,
            opacity: 0.6,
          },
          emphasis: {
            focus: 'adjacency',
            lineStyle: {
              width: 4,
            },
          },
        },
      ],
    }
  }

  const columns = [
    {
      title: '角色形象',
      key: 'image',
      width: 180,
      render: (_: any, record: Character) => (
        <div
          onClick={() => handlePreviewImage(record.description ? `https://trae-api-cn.mchost.guru/api/ide/v1/text_to_image?prompt=${encodeURIComponent(record.description)}&image_size=landscape_16_9` : undefined)}
          style={{ cursor: 'pointer', borderRadius: 8, overflow: 'hidden', border: '1px solid #f0f0f0' }}
        >
          {record.description ? (
            <Image
              src={`https://trae-api-cn.mchost.guru/api/ide/v1/text_to_image?prompt=${encodeURIComponent(record.description)}&image_size=landscape_16_9`}
              alt={record.name}
              width={180}
              height={101}
              style={{ objectFit: 'cover' }}
            />
          ) : (
            <div style={{ width: 180, height: 101, background: '#f5f5f5', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#999', fontSize: 12 }}>暂无图片</div>
          )}
        </div>
      ),
    },
    {
      title: '角色信息',
      key: 'info',
      render: (_: any, record: Character) => (
        <div>
          <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 4 }}>{record.name}</div>
          <div style={{ color: '#666', fontSize: 12 }}>{record.aliases || '暂无别名'}</div>
        </div>
      ),
    },
    {
      title: '角色描述',
      key: 'description',
      render: (_: any, record: Character) => {
        if (editingDescription?.characterId === record.id) {
          return (
            <div>
              <TextArea
                rows={3}
                value={editingDescription.description}
                onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setEditingDescription({ ...editingDescription, description: e.target.value })}
                style={{ marginBottom: 8 }}
              />
              <Space>
                <Button size="small" type="primary" onClick={() => handleSaveDescription(record.id, editingDescription.description)}>保存</Button>
                <Button size="small" onClick={() => setEditingDescription(null)}>取消</Button>
              </Space>
            </div>
          )
        }
        return (
          <Popover
            content={
              <div style={{ maxWidth: 400, whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>
                {record.description || '暂无描述'}
              </div>
            }
            title="完整描述"
            trigger="hover"
          >
            <div>
              <div style={{ color: '#666', fontSize: 12, lineHeight: 1.4, display: '-webkit-box', WebkitLineClamp: 3, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                {record.description || '暂无描述'}
              </div>
              <Button size="small" style={{ marginTop: 8 }} onClick={() => setEditingDescription({ characterId: record.id, description: record.description || '' })}>编辑</Button>
            </div>
          </Popover>
        )
      },
    },
    {
      title: '操作',
      key: 'action',
      width: 120,
      render: () => (
        <Button
          size="small"
          onClick={() => message.info('生成形象功能开发中')}
        >
          生成形象
        </Button>
      ),
    },
  ]

  if (!selectedProjectId && projectLoading) {
    return <Loading tip="加载项目列表..." />
  }

  return (
    <div>
      <Space style={{ marginBottom: 16 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(-1)}>
          返回
        </Button>
      </Space>

      <Card style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Title level={5} style={{ margin: 0 }}>
            人物关系图
          </Title>
          <Space>
            <Button
              type="primary"
              icon={<UserAddOutlined />}
              onClick={() => setExtractModalOpen(true)}
            >
              一键提取角色
            </Button>
            <Button icon={<DownloadOutlined />} onClick={handleExportPNG} disabled={graphData.nodes.length === 0}>
              导出PNG
            </Button>
            <span style={{ fontWeight: 500 }}>选择项目：</span>
            <Select
              style={{ width: 300 }}
              placeholder="请选择项目"
              value={selectedProjectId}
              onChange={handleProjectChange}
              options={projects.map((p) => ({
                label: p.name,
                value: p.id,
              }))}
              allowClear={false}
            />
          </Space>
        </div>
      </Card>

      <div style={{ display: 'flex', gap: 16 }}>
        <Card style={{ flex: 1 }}>
          {graphData.nodes.length > 0 ? (
            <ReactEChartsCore
              ref={chartRef}
              option={getGraphOption()}
              style={{ height: 600 }}
              notMerge
              opts={{ renderer: 'canvas' }}
            />
          ) : (
            <div
              style={{
                height: 400,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#999',
              }}
            >
              {selectedProjectId ? '暂无人物数据，请先创建角色或使用一键提取' : '请先选择一个项目'}
            </div>
          )}
        </Card>

        <Card title="角色列表" style={{ width: 450 }}>
          {characters.length === 0 ? (
            <div style={{ textAlign: 'center', color: '#999', padding: '40px 0' }}>
              暂无角色数据
            </div>
          ) : (
            <Table
              dataSource={characters}
              columns={columns}
              rowKey="id"
              pagination={{ pageSize: 5 }}
              size="small"
              scroll={{ y: 500 }}
            />
          )}
        </Card>
      </div>

      <Modal
        title="一键提取角色"
        open={extractModalOpen}
        onCancel={() => {
          setExtractModalOpen(false)
          setNovelText('')
          setSelectedNovelId(undefined)
        }}
        footer={null}
        width={800}
      >
        <div style={{ marginBottom: 16 }}>
          <label style={{ display: 'block', marginBottom: 8, fontWeight: 500 }}>选择小说：</label>
          <Select
            style={{ width: '100%' }}
            placeholder="请选择小说"
            value={selectedNovelId}
            onChange={handleNovelChange}
            options={novelOptions.map((n) => ({
              label: n.title,
              value: n.id,
            }))}
            allowClear
          />
        </div>
        <div>
          <label style={{ display: 'block', marginBottom: 8, fontWeight: 500 }}>小说文本：</label>
          <TextArea
            rows={15}
            value={novelText}
            onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setNovelText(e.target.value)}
            placeholder="请粘贴小说文本，AI将从中提取角色..."
            style={{ fontFamily: 'monospace' }}
          />
        </div>
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 16 }}>
          <Space>
            <Button onClick={() => { setExtractModalOpen(false); setNovelText(''); setSelectedNovelId(undefined); }}>取消</Button>
            <Button type="primary" loading={extractLoading} onClick={handleExtract}>
              开始提取
            </Button>
          </Space>
        </div>
      </Modal>

      <Modal
        title="角色形象预览"
        open={previewModalOpen}
        onCancel={() => setPreviewModalOpen(false)}
        footer={null}
        width={600}
      >
        {previewImage ? (
          <Image
            src={previewImage}
            alt="角色形象预览"
            width="100%"
            style={{ borderRadius: 8 }}
          />
        ) : (
          <div style={{ textAlign: 'center', color: '#999', padding: '40px 0' }}>
            暂无预览图
          </div>
        )}
      </Modal>
    </div>
  )
}
