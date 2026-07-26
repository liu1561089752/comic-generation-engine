import { useEffect, useState } from 'react'
import { Card, Row, Col, Button, Modal, Form, Input, Select, message, Space, Tag } from 'antd'
import { PlusOutlined, FileTextOutlined, CheckCircleOutlined } from '@ant-design/icons'
import { useParams } from 'react-router-dom'
import { useWorldStore } from '../../stores/worldStore'
import type { StyleTemplate } from '../../types/world'
import EmptyState from '../../components/common/EmptyState'
import Loading from '../../components/common/Loading'
import { formatDate } from '../../utils/format'

export default function StyleTemplateList() {
  const { id: projectId } = useParams<{ id: string }>()
  const { templates, loading, fetchTemplates, createTemplate, updateTemplate, deleteTemplate, setDefaultTemplate } =
    useWorldStore()

  const [modalOpen, setModalOpen] = useState(false)
  const [editingTemplate, setEditingTemplate] = useState<StyleTemplate | null>(null)
  const [form] = Form.useForm()
  const [submitLoading, setSubmitLoading] = useState(false)

  useEffect(() => {
    if (projectId) {
      fetchTemplates(projectId)
    }
  }, [projectId, fetchTemplates])

  const handleOpenCreate = () => {
    setEditingTemplate(null)
    form.resetFields()
    setModalOpen(true)
  }

  const handleOpenEdit = (template: StyleTemplate) => {
    setEditingTemplate(template)
    form.setFieldsValue(template)
    setModalOpen(true)
  }

  const handleSubmit = async (values: any) => {
    if (!projectId) return
    setSubmitLoading(true)
    try {
      if (editingTemplate) {
        await updateTemplate(projectId, editingTemplate.id, values)
        message.success('模板更新成功')
      } else {
        await createTemplate(projectId, values)
        message.success('模板创建成功')
      }
      setModalOpen(false)
      form.resetFields()
      fetchTemplates(projectId)
    } catch {
      message.error('操作失败')
    } finally {
      setSubmitLoading(false)
    }
  }

  const handleDelete = (templateId: string) => {
    if (!projectId) return
    Modal.confirm({
      title: '确认删除',
      content: '确定要删除该风格模板吗？',
      okType: 'danger',
      onOk: async () => {
        try {
          await deleteTemplate(projectId, templateId)
          message.success('删除成功')
          fetchTemplates(projectId)
        } catch {
          message.error('删除失败')
        }
      },
    })
  }

  const handleSetDefault = async (templateId: string) => {
    if (!projectId) return
    try {
      await setDefaultTemplate(projectId, templateId)
      message.success('已设为默认模板')
      fetchTemplates(projectId)
    } catch {
      message.error('操作失败')
    }
  }

  if (!projectId) {
    return <EmptyState description="请先选择一个项目" />
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <h2 style={{ margin: 0, fontSize: 20, fontWeight: 600 }}>风格模板管理</h2>
        <Button type="primary" icon={<PlusOutlined />} onClick={handleOpenCreate}>
          创建模板
        </Button>
      </div>

      {loading && templates.length === 0 ? (
        <Loading tip="加载风格模板..." />
      ) : templates.length === 0 ? (
        <EmptyState
          description="暂无风格模板，点击按钮创建第一个模板"
          actionText="创建模板"
          onAction={handleOpenCreate}
        />
      ) : (
        <Row gutter={[16, 16]}>
          {templates.map((template: StyleTemplate) => (
            <Col key={template.id} xs={24} sm={12} md={8}>
              <Card
                style={{
                  height: '100%',
                  position: 'relative',
                  borderColor: template.is_default ? '#1677ff' : undefined,
                }}
                actions={[
                  !template.is_default ? (
                    <Button type="link" icon={<CheckCircleOutlined />} onClick={() => handleSetDefault(template.id)}>
                      设为默认
                    </Button>
                  ) : (
                    <Tag color="blue" style={{ margin: 0 }}>
                      当前默认
                    </Tag>
                  ),
                  <Button type="link" onClick={() => handleOpenEdit(template)}>
                    编辑
                  </Button>,
                  <Button type="link" danger onClick={() => handleDelete(template.id)}>
                    删除
                  </Button>,
                ]}
              >
                {template.is_default && (
                  <Tag color="blue" style={{ position: 'absolute', top: 8, right: 8 }}>
                    默认
                  </Tag>
                )}
                <div style={{ textAlign: 'center', marginBottom: 12 }}>
                  <FileTextOutlined style={{ fontSize: 40, color: '#1677ff' }} />
                </div>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 8 }}>{template.name}</div>
                  <Space wrap>
                    <Tag>{template.aspect_ratio || '未设置比例'}</Tag>
                    {template.width && <Tag>{template.width}px</Tag>}
                  </Space>
                  <div style={{ marginTop: 8, fontSize: 13, color: '#666', textAlign: 'left' }}>
                    {template.art_style && (
                      <div>
                        <strong>画风：</strong>
                        {template.art_style}
                      </div>
                    )}
                    {template.coloring_style && (
                      <div>
                        <strong>上色：</strong>
                        {template.coloring_style}
                      </div>
                    )}
                    {template.lighting_style && (
                      <div>
                        <strong>光照：</strong>
                        {template.lighting_style}
                      </div>
                    )}
                  </div>
                  <div style={{ marginTop: 8, fontSize: 12, color: '#999' }}>
                    创建于 {formatDate(template.created_at, 'YYYY-MM-DD')}
                  </div>
                </div>
              </Card>
            </Col>
          ))}
        </Row>
      )}

      <Modal
        title={editingTemplate ? '编辑风格模板' : '创建风格模板'}
        open={modalOpen}
        onCancel={() => {
          setModalOpen(false)
          setEditingTemplate(null)
        }}
        footer={null}
        width={640}
      >
        <Form form={form} layout="vertical" onFinish={handleSubmit}>
          <Form.Item name="name" label="模板名称" rules={[{ required: true, message: '请输入模板名称' }]}>
            <Input placeholder="如：漫画风格、写实风格" />
          </Form.Item>
          <Form.Item name="aspect_ratio" label="画面比例">
            <Select
              allowClear
              options={[
                { label: '1:1.34 (默认竖屏)', value: '1:1.34' },
                { label: '16:9', value: '16:9' },
                { label: '4:3', value: '4:3' },
                { label: '1:1', value: '1:1' },
              ]}
            />
          </Form.Item>
          <Form.Item name="width" label="宽度(px)">
            <Input type="number" placeholder="1080" />
          </Form.Item>
          <Form.Item name="art_style" label="画风">
            <Input.TextArea rows={2} placeholder="如：日式漫画、美式卡通风格、写实风格" />
          </Form.Item>
          <Form.Item name="coloring_style" label="上色风格">
            <Input.TextArea rows={2} placeholder="如：平涂、厚涂、赛璐璐" />
          </Form.Item>
          <Form.Item name="lineart_style" label="线稿风格">
            <Input.TextArea rows={2} placeholder="如：细线、粗线、无描边" />
          </Form.Item>
          <Form.Item name="lighting_style" label="光照风格">
            <Input.TextArea rows={2} placeholder="如：自然光、戏剧光、背光" />
          </Form.Item>
          <Form.Item name="negative_prompt" label="负面提示词">
            <Input.TextArea rows={2} placeholder="不希望出现在画面中的元素" />
          </Form.Item>
          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit" loading={submitLoading}>
                {editingTemplate ? '保存修改' : '创建'}
              </Button>
              <Button
                onClick={() => {
                  setModalOpen(false)
                  setEditingTemplate(null)
                }}
              >
                取消
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
