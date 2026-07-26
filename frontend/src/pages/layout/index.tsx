import { useEffect, useState, useCallback } from 'react'
import { useParams } from 'react-router-dom'
import {
  Card, Select, Tag, Button, Space, Typography,
  message, Spin, Table, Modal, Form, Radio, InputNumber,
  Tooltip,
} from 'antd'
import {
  LayoutOutlined, DeleteOutlined,
  ThunderboltOutlined, ArrowUpOutlined, ArrowDownOutlined,
} from '@ant-design/icons'
import apiClient from '../../api/client'
import { formatDate } from '../../utils/format'
import ProjectFilter from '../../components/common/ProjectFilter'
import EmptyState from '../../components/common/EmptyState'

const { Title, Text } = Typography

interface PageItem {
  id: string
  chapter_id: string
  page_number: number
  layout_template?: string
  panel_layout?: any
  status: string
  created_at: string
  updated_at: string
}

interface Chapter {
  id: string
  chapter_number: number
  title?: string
}

// Webtoon 模板定义
const LAYOUT_TEMPLATES = [
  { value: 'single', label: '单格', panels: 1, icon: '▢' },
  { value: 'double', label: '双格', panels: 2, icon: '▢▢' },
  { value: 'triple', label: '三格', panels: 3, icon: '▢▢▢' },
  { value: 'quad', label: '四格', panels: 4, icon: '⊞' },
  { value: 'fullpage', label: '整页', panels: 1, icon: '⬜' },
  { value: 'cross', label: '跨格', panels: 2, icon: '▣' },
]

const PAGE_STATUS_MAP: Record<string, string> = {
  draft: '草稿',
  planned: '已规划',
  editing: '编辑中',
  completed: '已完成',
}

const PAGE_STATUS_COLOR: Record<string, string> = {
  draft: 'default',
  planned: 'processing',
  editing: 'warning',
  completed: 'success',
}

export default function LayoutCenter() {
  const { id: urlProjectId } = useParams<{ id: string }>()
  const [projectId, setProjectId] = useState<string | undefined>(urlProjectId)
  const [pages, setPages] = useState<PageItem[]>([])
  const [chapters, setChapters] = useState<Chapter[]>([])
  const [loading, setLoading] = useState(false)
  const [selectedChapterId, setSelectedChapterId] = useState<string | undefined>(undefined)
  const [autoLayoutModalOpen, setAutoLayoutModalOpen] = useState(false)
  const [autoLayoutTemplate, setAutoLayoutTemplate] = useState<string>('triple')
  const [autoLayoutLoading, setAutoLayoutLoading] = useState(false)
  const [editModalOpen, setEditModalOpen] = useState(false)
  const [editPage, setEditPage] = useState<PageItem | null>(null)
  const [editForm] = Form.useForm()

  useEffect(() => {
    setProjectId(urlProjectId)
  }, [urlProjectId])

  const fetchChapters = useCallback(async () => {
    if (!projectId) return
    try {
      const res: any = await apiClient.get(`/projects/${projectId}/novels`)
      const novels = res?.data || []
      for (const novel of novels) {
        try {
          const chaptersRes: any = await apiClient.get(`/projects/${projectId}/novels/${novel.id}/chapters`)
          const chs = chaptersRes?.data || []
          setChapters(chs.map((ch: any) => ({ id: ch.id, chapter_number: ch.chapter_number, title: ch.title })))
          break
        } catch {
          continue
        }
      }
    } catch {
      setChapters([])
    }
  }, [projectId])

  const fetchPages = useCallback(async (chapterId?: string) => {
    if (!projectId) return
    setLoading(true)
    try {
      const url = chapterId
        ? `/projects/${projectId}/pages?chapter_id=${chapterId}`
        : `/projects/${projectId}/pages`
      const res: any = await apiClient.get(url)
      const data = (res as { data?: { items?: PageItem[] } }).data
      setPages(data?.items || [])
    } catch {
      setPages([])
    } finally {
      setLoading(false)
    }
  }, [projectId])

  useEffect(() => {
    if (projectId) {
      fetchChapters()
    }
  }, [fetchChapters])

  useEffect(() => {
    if (projectId) {
      fetchPages(selectedChapterId)
    }
  }, [selectedChapterId, fetchPages, projectId])

  const handleProjectChange = (newProjectId: string | undefined) => {
    if (newProjectId) {
      setProjectId(newProjectId)
      setSelectedChapterId(undefined)
    }
  }

  const handleAutoLayout = async () => {
    if (!projectId) return
    setAutoLayoutLoading(true)
    try {
      const payload: any = { template: autoLayoutTemplate }
      if (selectedChapterId) {
        payload.chapter_id = selectedChapterId
      }
      const res: any = await apiClient.post(`/projects/${projectId}/pages/auto-layout`, payload)
      const data = (res as { data?: { items?: PageItem[] } }).data
      setPages(data?.items || [])
      message.success(`自动版式规划完成，共规划 ${data?.items?.length || 0} 页`)
      setAutoLayoutModalOpen(false)
    } catch {
      message.error('自动版式规划失败')
    } finally {
      setAutoLayoutLoading(false)
    }
  }

  const handleEditPage = (page: PageItem) => {
    setEditPage(page)
    editForm.setFieldsValue({
      layout_template: page.layout_template || 'triple',
      page_number: page.page_number,
      status: page.status,
    })
    setEditModalOpen(true)
  }

  const handleSavePage = async () => {
    if (!projectId || !editPage) return
    try {
      const values = await editForm.validateFields()
      const layoutTemplate = LAYOUT_TEMPLATES.find((t) => t.value === values.layout_template)
      await apiClient.put(`/projects/${projectId}/pages/${editPage.id}`, {
        layout_template: values.layout_template,
        page_number: values.page_number,
        status: values.status || 'editing',
        panel_layout: layoutTemplate ? {
          template: layoutTemplate.value,
          template_name: layoutTemplate.label,
          panel_count: layoutTemplate.panels,
        } : undefined,
      })
      message.success('页面布局已更新')
      setEditModalOpen(false)
      fetchPages(selectedChapterId)
    } catch {
      message.error('保存失败')
    }
  }

  const handleDeletePage = async (pageId: string) => {
    if (!projectId) return
    try {
      await apiClient.delete(`/projects/${projectId}/pages/${pageId}`)
      message.success('页面已删除')
      fetchPages(selectedChapterId)
    } catch {
      message.error('删除失败')
    }
  }

  const handleMovePage = async (pageId: string, direction: 'up' | 'down') => {
    const idx = pages.findIndex((p) => p.id === pageId)
    if (idx === -1) return
    const targetIdx = direction === 'up' ? idx - 1 : idx + 1
    if (targetIdx < 0 || targetIdx >= pages.length) return

    const current = pages[idx]
    const target = pages[targetIdx]
    const tempNum = current.page_number

    try {
      await apiClient.put(`/projects/${projectId}/pages/${current.id}`, { page_number: target.page_number })
      await apiClient.put(`/projects/${projectId}/pages/${target.id}`, { page_number: tempNum })
      message.success('排序已更新')
      fetchPages(selectedChapterId)
    } catch {
      message.error('排序失败')
    }
  }

  const columns = [
    {
      title: '页码',
      dataIndex: 'page_number',
      key: 'page_number',
      width: 70,
    },
    {
      title: '版式模板',
      dataIndex: 'layout_template',
      key: 'layout_template',
      width: 100,
      render: (val: string) => {
        const tpl = LAYOUT_TEMPLATES.find((t) => t.value === val)
        return tpl ? (
          <Tooltip title={`${tpl.label}（${tpl.panels}格）`}>
            <Tag icon={<LayoutOutlined />}>{tpl.icon} {tpl.label}</Tag>
          </Tooltip>
        ) : (val || '-')
      },
    },
    {
      title: '画格数',
      key: 'panel_count',
      width: 70,
      render: (_: any, record: PageItem) => {
        const count = record.panel_layout?.panel_count
        const tpl = LAYOUT_TEMPLATES.find((t) => t.value === record.layout_template)
        return count || tpl?.panels || '-'
      },
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 90,
      render: (status: string) => (
        <Tag color={PAGE_STATUS_COLOR[status] || 'default'}>
          {PAGE_STATUS_MAP[status] || status}
        </Tag>
      ),
    },
    {
      title: '更新时间',
      dataIndex: 'updated_at',
      key: 'updated_at',
      width: 160,
      render: (date: string) => formatDate(date),
    },
    {
      title: '操作',
      key: 'action',
      width: 180,
      render: (_: any, record: PageItem) => (
        <Space>
          <Button
            type="link"
            size="small"
            icon={<ArrowUpOutlined />}
            disabled={pages.indexOf(record) === 0}
            onClick={() => handleMovePage(record.id, 'up')}
          />
          <Button
            type="link"
            size="small"
            icon={<ArrowDownOutlined />}
            disabled={pages.indexOf(record) === pages.length - 1}
            onClick={() => handleMovePage(record.id, 'down')}
          />
          <Button
            type="link"
            size="small"
            onClick={() => handleEditPage(record)}
          >
            编辑
          </Button>
          <Button
            type="link"
            size="small"
            danger
            icon={<DeleteOutlined />}
            onClick={() => handleDeletePage(record.id)}
          />
        </Space>
      ),
    },
  ]

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>Webtoon 版式中心</Title>
        {projectId && (
          <Space>
            <Button
              type="primary"
              icon={<ThunderboltOutlined />}
              onClick={() => setAutoLayoutModalOpen(true)}
            >
              自动版式规划
            </Button>
          </Space>
        )}
      </div>

      <Card style={{ marginBottom: 16 }}>
        <ProjectFilter
          projectId={projectId}
          onProjectChange={handleProjectChange}
          showSearch={false}
        />
      </Card>

      {!projectId ? (
        <EmptyState description="请先在顶部选择一个项目" />
      ) : (
        <>
          <Card style={{ marginBottom: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <Text strong>筛选章节：</Text>
              <Select
                placeholder="全部章节"
                style={{ width: 250 }}
                allowClear
                value={selectedChapterId}
                onChange={(val) => setSelectedChapterId(val)}
                options={chapters.map((ch) => ({
                  label: `第 ${ch.chapter_number} 章${ch.title ? ` - ${ch.title}` : ''}`,
                  value: ch.id,
                }))}
              />
            </div>
          </Card>

          {/* 模板预览 */}
          <Card size="small" style={{ marginBottom: 16 }}>
            <Text strong style={{ marginRight: 12 }}>模板说明：</Text>
            <Space wrap>
              {LAYOUT_TEMPLATES.map((tpl) => (
                <Tooltip key={tpl.value} title={`${tpl.label}：${tpl.panels} 个画格`}>
                  <Tag
                    color="blue"
                    style={{ cursor: 'pointer', fontSize: 14, padding: '4px 8px' }}
                  >
                    {tpl.icon} {tpl.label}
                  </Tag>
                </Tooltip>
              ))}
            </Space>
          </Card>

          {loading ? (
            <Spin style={{ display: 'block', margin: '40px auto' }} />
          ) : pages.length === 0 ? (
            <EmptyState
              description="暂无页面数据"
              actionText="自动版式规划"
              onAction={() => setAutoLayoutModalOpen(true)}
            />
          ) : (
            <div>
              <div style={{ marginBottom: 12, color: '#666', fontSize: 13 }}>
                共 {pages.length} 页
              </div>
              <Table
                dataSource={pages}
                columns={columns}
                rowKey="id"
                pagination={false}
                size="middle"
              />
            </div>
          )}
        </>
      )}

      {/* 自动版式规划 Modal */}
      <Modal
        title={
          <Space>
            <ThunderboltOutlined />
            <span>自动版式规划</span>
          </Space>
        }
        open={autoLayoutModalOpen}
        onCancel={() => setAutoLayoutModalOpen(false)}
        onOk={handleAutoLayout}
        confirmLoading={autoLayoutLoading}
        okText="开始规划"
        cancelText="取消"
      >
        <div style={{ padding: '16px 0' }}>
          <Text>选择所有页面统一应用的版式模板：</Text>
          <div style={{ marginTop: 16 }}>
            <Radio.Group
              value={autoLayoutTemplate}
              onChange={(e) => setAutoLayoutTemplate(e.target.value)}
              optionType="button"
              buttonStyle="solid"
            >
              {LAYOUT_TEMPLATES.map((tpl) => (
                <Radio.Button key={tpl.value} value={tpl.value}>
                  {tpl.icon} {tpl.label} ({tpl.panels}格)
                </Radio.Button>
              ))}
            </Radio.Group>
          </div>
          <div style={{ marginTop: 16, color: '#666', fontSize: 13 }}>
            {selectedChapterId
              ? '将为当前筛选章节下的所有页面应用所选模板'
              : '将为项目中的所有页面应用所选模板'}
          </div>
        </div>
      </Modal>

      {/* 编辑页面 Modal */}
      <Modal
        title={
          <Space>
            <LayoutOutlined />
            <span>编辑页面布局</span>
          </Space>
        }
        open={editModalOpen}
        onCancel={() => setEditModalOpen(false)}
        onOk={handleSavePage}
        okText="保存"
        cancelText="取消"
        width={500}
      >
        <Form
          form={editForm}
          layout="vertical"
          style={{ marginTop: 16 }}
        >
          <Form.Item label="页码" name="page_number">
            <InputNumber min={1} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item label="版式模板" name="layout_template">
            <Radio.Group optionType="button" buttonStyle="solid">
              {LAYOUT_TEMPLATES.map((tpl) => (
                <Radio.Button key={tpl.value} value={tpl.value}>
                  {tpl.icon} {tpl.label}
                </Radio.Button>
              ))}
            </Radio.Group>
          </Form.Item>
          <Form.Item label="状态" name="status">
            <Select
              options={[
                { value: 'draft', label: '草稿' },
                { value: 'planned', label: '已规划' },
                { value: 'editing', label: '编辑中' },
                { value: 'completed', label: '已完成' },
              ]}
            />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
