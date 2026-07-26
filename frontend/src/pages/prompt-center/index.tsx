import { useEffect, useState, useCallback } from 'react'
import {
  Card, Row, Col, Button, Modal, Form, Input, message, Space, Tag,
  Spin, Empty, Badge, Drawer, Tooltip, Typography, Popconfirm, Divider,
} from 'antd'
import {
  PlusOutlined, EditOutlined, DeleteOutlined, CheckCircleFilled,
  CopyOutlined, ThunderboltOutlined, SaveOutlined, CloseOutlined,
  FileTextOutlined, SettingOutlined,
} from '@ant-design/icons'
import apiClient from '../../api/client'

const { TextArea } = Input
const { Text, Paragraph } = Typography

// ─── 类型定义 ───
interface PromptModule {
  id: string
  template_id: string
  module_key: string
  module_label: string
  category: string | null
  content: string
  sort_order: number
  updated_at: string
}

interface PromptTemplate {
  id: string
  name: string
  description: string | null
  cover_image_url: string | null
  is_active: boolean
  is_default: boolean
  created_at: string
  updated_at: string
  modules: PromptModule[]
}

// ─── 分类配置 ───
const CATEGORY_CONFIG: Record<string, { label: string; color: string }> = {
  core:        { label: '核心流水线', color: '#1677ff' },
  extraction:  { label: '资产提取',   color: '#52c41a' },
  generation:  { label: '图像生成',   color: '#722ed1' },
  internal:    { label: '内部 Agent', color: '#fa8c16' },
}

// ─── 封面占位色板 ───
const COVER_GRADIENTS = [
  'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
  'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
  'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)',
  'linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)',
  'linear-gradient(135deg, #fa709a 0%, #fee140 100%)',
  'linear-gradient(135deg, #30cfd0 0%, #330867 100%)',
  'linear-gradient(135deg, #a8edea 0%, #fed6e3 100%)',
  'linear-gradient(135deg, #5ee7df 0%, #b490ca 100%)',
]

function getCoverGradient(name: string) {
  let hash = 0
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash)
  }
  return COVER_GRADIENTS[Math.abs(hash) % COVER_GRADIENTS.length]
}

export default function PromptCenter() {
  const [templates, setTemplates] = useState<PromptTemplate[]>([])
  const [loading, setLoading] = useState(false)
  const [createOpen, setCreateOpen] = useState(false)
  const [detailOpen, setDetailOpen] = useState(false)
  const [selectedTemplate, setSelectedTemplate] = useState<PromptTemplate | null>(null)
  const [createForm] = Form.useForm()
  const [createLoading, setCreateLoading] = useState(false)

  // 模块编辑状态
  const [editingModuleKey, setEditingModuleKey] = useState<string | null>(null)
  const [moduleDrafts, setModuleDrafts] = useState<Record<string, string>>({})
  const [savingModuleKey, setSavingModuleKey] = useState<string | null>(null)

  // ─── 加载模板列表 ───
  const fetchTemplates = useCallback(async () => {
    setLoading(true)
    try {
      const res: any = await apiClient.get('/prompt-templates')
      setTemplates(res?.data || [])
    } catch {
      message.error('加载模板失败')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchTemplates() }, [fetchTemplates])

  // ─── 创建模板 ───
  const handleCreate = async (values: any) => {
    setCreateLoading(true)
    try {
      await apiClient.post('/prompt-templates', {
        name: values.name,
        description: values.description || '',
        cover_image_url: values.cover_image_url || null,
      })
      message.success('模板创建成功')
      setCreateOpen(false)
      createForm.resetFields()
      fetchTemplates()
    } catch {
      message.error('创建失败')
    } finally {
      setCreateLoading(false)
    }
  }

  // ─── 删除模板 ───
  const handleDelete = async (template: PromptTemplate) => {
    try {
      await apiClient.delete(`/prompt-templates/${template.id}`)
      message.success('删除成功')
      fetchTemplates()
    } catch {
      message.error('删除失败')
    }
  }

  // ─── 复制模板 ───
  const handleDuplicate = async (template: PromptTemplate) => {
    try {
      const res: any = await apiClient.post('/prompt-templates', {
        name: `${template.name} (副本)`,
        description: template.description,
        cover_image_url: template.cover_image_url,
      })
      const newTemplateId = res?.data?.id
      if (newTemplateId && template.modules) {
        // 逐个复制模块内容
        for (const mod of template.modules) {
          if (mod.content) {
            await apiClient.put(
              `/prompt-templates/${newTemplateId}/modules/${mod.module_key}`,
              { content: mod.content }
            )
          }
        }
      }
      message.success('模板复制成功')
      fetchTemplates()
    } catch {
      message.error('复制失败')
    }
  }

  // ─── 设置生效 ───
  const handleActivate = async (template: PromptTemplate) => {
    try {
      await apiClient.post(`/prompt-templates/${template.id}/activate`)
      message.success(`「${template.name}」已设为生效模板`)
      fetchTemplates()
    } catch {
      message.error('设置失败')
    }
  }

  // ─── 打开详情 ───
  const openDetail = (template: PromptTemplate) => {
    setSelectedTemplate(template)
    setDetailOpen(true)
    setEditingModuleKey(null)
    setModuleDrafts({})
  }

  // ─── 模块编辑 ───
  const startEditModule = (mod: PromptModule) => {
    setEditingModuleKey(mod.module_key)
    setModuleDrafts((prev) => ({ ...prev, [mod.module_key]: mod.content }))
  }

  const cancelEditModule = () => {
    setEditingModuleKey(null)
  }

  const saveModule = async (templateId: string, mod: PromptModule) => {
    const content = moduleDrafts[mod.module_key]
    if (content === undefined) return
    setSavingModuleKey(mod.module_key)
    try {
      const res: any = await apiClient.put(
        `/prompt-templates/${templateId}/modules/${mod.module_key}`,
        { content }
      )
      // 更新本地状态
      if (selectedTemplate && res?.data) {
        const updatedModules = selectedTemplate.modules.map((m) =>
          m.module_key === mod.module_key ? { ...m, content, updated_at: res.data.updated_at } : m
        )
        setSelectedTemplate({ ...selectedTemplate, modules: updatedModules })
      }
      setEditingModuleKey(null)
      message.success(`「${mod.module_label}」已保存`)
      // 同步列表中的模板
      fetchTemplates()
    } catch {
      message.error('保存失败')
    } finally {
      setSavingModuleKey(null)
    }
  }

  // ─── 按分类分组模块 ───
  const groupedModules = (modules: PromptModule[]) => {
    const groups: Record<string, PromptModule[]> = {}
    for (const mod of modules) {
      const cat = mod.category || 'other'
      if (!groups[cat]) groups[cat] = []
      groups[cat].push(mod)
    }
    return groups
  }

  // ─── 渲染模板卡片 ───
  const renderTemplateCard = (template: PromptTemplate) => {
    const gradient = getCoverGradient(template.name)
    const moduleCount = template.modules?.length || 0

    return (
      <Col xs={24} sm={12} md={8} lg={6} key={template.id}>
        <Card
          hoverable
          className="pc-card"
          style={{ overflow: 'hidden', borderRadius: 12 }}
          bodyStyle={{ padding: 0 }}
          onClick={() => openDetail(template)}
        >
          {/* 封面区 */}
          <div
            style={{
              height: 140,
              background: template.cover_image_url
                ? `url(${template.cover_image_url}) center/cover`
                : gradient,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              position: 'relative',
            }}
          >
            {!template.cover_image_url && (
              <span style={{ fontSize: 36, color: 'rgba(255,255,255,0.9)', fontWeight: 700 }}>
                {template.name.slice(0, 4)}
              </span>
            )}
            {/* 生效标记 */}
            {template.is_active && (
              <div style={{
                position: 'absolute', top: 8, right: 8,
                background: 'rgba(22, 119, 255, 0.9)',
                borderRadius: 12, padding: '2px 10px',
                display: 'flex', alignItems: 'center', gap: 4,
              }}>
                <CheckCircleFilled style={{ color: '#fff', fontSize: 12 }} />
                <span style={{ color: '#fff', fontSize: 12 }}>生效中</span>
              </div>
            )}
            {/* 默认标记 */}
            {template.is_default && (
              <div style={{
                position: 'absolute', top: 8, left: 8,
                background: 'rgba(0,0,0,0.5)',
                borderRadius: 12, padding: '2px 10px',
              }}>
                <span style={{ color: '#fff', fontSize: 12 }}>系统默认</span>
              </div>
            )}
          </div>
          {/* 信息区 */}
          <div style={{ padding: '12px 16px' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
              <Text strong ellipsis style={{ maxWidth: 180 }}>{template.name}</Text>
            </div>
            <Paragraph
              type="secondary"
              ellipsis={{ rows: 2 }}
              style={{ fontSize: 12, marginBottom: 8, minHeight: 36, whiteSpace: 'pre-wrap' }}
            >
              {template.description || '暂无简介'}
            </Paragraph>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <Space size={4}>
                <Tag icon={<FileTextOutlined />} style={{ fontSize: 11, margin: 0 }}>
                  {moduleCount} 个模块
                </Tag>
              </Space>
              <Space size={0}>
                {!template.is_active && (
                  <Tooltip title="设为生效">
                    <Button
                      type="text" size="small"
                      icon={<ThunderboltOutlined />}
                      onClick={(e) => { e.stopPropagation(); handleActivate(template) }}
                    />
                  </Tooltip>
                )}
                <Tooltip title="复制">
                  <Button
                    type="text" size="small"
                    icon={<CopyOutlined />}
                    onClick={(e) => { e.stopPropagation(); handleDuplicate(template) }}
                  />
                </Tooltip>
                {!template.is_default && (
                  <Popconfirm
                    title="确认删除此模板？"
                    onConfirm={(e) => { e?.stopPropagation(); handleDelete(template) }}
                    onCancel={(e) => e?.stopPropagation()}
                  >
                    <Button
                      type="text" size="small" danger
                      icon={<DeleteOutlined />}
                      onClick={(e) => e.stopPropagation()}
                    />
                  </Popconfirm>
                )}
              </Space>
            </div>
          </div>
        </Card>
      </Col>
    )
  }

  // ─── 渲染模块编辑卡片 ───
  const renderModuleCard = (template: PromptTemplate, mod: PromptModule) => {
    const isEditing = editingModuleKey === mod.module_key
    const catConfig = CATEGORY_CONFIG[mod.category || ''] || { label: mod.category || '其他', color: '#999' }
    const draftContent = moduleDrafts[mod.module_key]
    const hasChanges = draftContent !== undefined && draftContent !== mod.content
    const charCount = (isEditing ? draftContent : mod.content)?.length || 0

    return (
      <Card
        key={mod.module_key}
        size="small"
        style={{ marginBottom: 12 }}
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Tag color={catConfig.color} style={{ margin: 0 }}>{catConfig.label}</Tag>
            <Text strong style={{ fontSize: 14 }}>{mod.module_label}</Text>
          </div>
        }
        extra={
          <Space size={4}>
            {isEditing ? (
              <>
                <Button
                  type="primary" size="small"
                  icon={<SaveOutlined />}
                  loading={savingModuleKey === mod.module_key}
                  disabled={!hasChanges}
                  onClick={() => saveModule(template.id, mod)}
                >
                  保存
                </Button>
                <Button size="small" icon={<CloseOutlined />} onClick={cancelEditModule} />
              </>
            ) : (
              <Button
                type="text" size="small"
                icon={<EditOutlined />}
                onClick={() => startEditModule(mod)}
              />
            )}
          </Space>
        }
      >
        {isEditing ? (
          <TextArea
            value={draftContent}
            onChange={(e) => setModuleDrafts((prev) => ({ ...prev, [mod.module_key]: e.target.value }))}
            autoSize={{ minRows: 6, maxRows: 30 }}
            style={{ fontFamily: 'monospace', fontSize: 13 }}
          />
        ) : (
          <div
            style={{
              fontFamily: 'monospace', fontSize: 13,
              whiteSpace: 'pre-wrap', wordBreak: 'break-word',
              maxHeight: 300, overflow: 'auto',
              color: mod.content ? 'inherit' : '#bbb',
            }}
          >
            {mod.content || '（空）点击编辑按钮添加提示词'}
          </div>
        )}
        <div style={{ marginTop: 4, textAlign: 'right' }}>
          <Text type="secondary" style={{ fontSize: 11 }}>{charCount} 字</Text>
        </div>
      </Card>
    )
  }

  // ─── 渲染 ───
  return (
    <div style={{ padding: '0 4px' }}>
      {/* 标题栏 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <div>
          <h2 style={{ margin: 0, fontSize: 20, fontWeight: 600 }}>Prompt 中心</h2>
          <Text type="secondary" style={{ fontSize: 13 }}>
            管理提示词模板，选择生效模板后各 AI 模块将使用对应提示词
          </Text>
        </div>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
          新建模板
        </Button>
      </div>

      {/* 模板网格 */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: 60 }}>
          <Spin tip="加载模板..." />
        </div>
      ) : templates.length === 0 ? (
        <Empty description="暂无提示词模板" >
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
            新建模板
          </Button>
        </Empty>
      ) : (
        <Row gutter={[16, 16]}>
          {templates.map(renderTemplateCard)}
        </Row>
      )}

      {/* 创建模板 Modal */}
      <Modal
        title="新建提示词模板"
        open={createOpen}
        onCancel={() => { setCreateOpen(false); createForm.resetFields() }}
        footer={null}
        width={500}
        destroyOnClose
      >
        <Form form={createForm} layout="vertical" onFinish={handleCreate}>
          <Form.Item name="name" label="模板名称" rules={[{ required: true, message: '请输入模板名称' }]}>
            <Input placeholder="如：古言Q版风格模板、现代都市风格模板" />
          </Form.Item>
          <Form.Item name="description" label="简介">
            <TextArea rows={3} placeholder="描述这套模板的适用场景和特点" />
          </Form.Item>
          <Form.Item name="cover_image_url" label="封面图 URL（可选）">
            <Input placeholder="https://..." />
          </Form.Item>
          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit" loading={createLoading}>
                创建
              </Button>
              <Button onClick={() => { setCreateOpen(false); createForm.resetFields() }}>
                取消
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* 模板详情 Drawer */}
      <Drawer
        title={
          selectedTemplate && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span>{selectedTemplate.name}</span>
              {selectedTemplate.is_active && (
                <Badge status="processing" text="生效中" />
              )}
              {selectedTemplate.is_default && (
                <Tag>系统默认</Tag>
              )}
            </div>
          )
        }
        open={detailOpen}
        onClose={() => { setDetailOpen(false); setSelectedTemplate(null) }}
        width={720}
        destroyOnClose
      >
        {selectedTemplate && (
          <div>
            {/* 模板信息 */}
            {selectedTemplate.description && (
              <div style={{ marginBottom: 16, fontSize: 13, color: 'rgba(0,0,0,0.65)', whiteSpace: 'pre-wrap', lineHeight: 1.8 }}>
                {selectedTemplate.description}
              </div>
            )}

            {/* 操作栏 */}
            <div style={{ marginBottom: 16, display: 'flex', gap: 8 }}>
              {!selectedTemplate.is_active && (
                <Button
                  type="primary"
                  icon={<ThunderboltOutlined />}
                  onClick={() => handleActivate(selectedTemplate)}
                >
                  设为生效模板
                </Button>
              )}
              <Button
                icon={<CopyOutlined />}
                onClick={() => handleDuplicate(selectedTemplate)}
              >
                复制模板
              </Button>
            </div>

            <Divider style={{ margin: '12px 0' }} />

            {/* 模块列表 */}
            {(() => {
              const groups = groupedModules(selectedTemplate.modules || [])
              const categoryOrder = ['core', 'extraction', 'generation', 'internal']
              return categoryOrder
                .filter((cat) => groups[cat])
                .map((cat) => (
                  <div key={cat} style={{ marginBottom: 20 }}>
                    <div style={{ marginBottom: 8 }}>
                      <Tag color={CATEGORY_CONFIG[cat]?.color} style={{ fontSize: 13, padding: '2px 12px' }}>
                        {CATEGORY_CONFIG[cat]?.label || cat}
                      </Tag>
                    </div>
                    {groups[cat].map((mod) => renderModuleCard(selectedTemplate, mod))}
                  </div>
                ))
            })()}
          </div>
        )}
      </Drawer>
    </div>
  )
}
