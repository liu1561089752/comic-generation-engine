import { useState } from 'react'
import { Button, Space, Table, Tag, Modal, Form, Input, Select, message } from 'antd'
import { EditOutlined, DeleteOutlined, PlusOutlined } from '@ant-design/icons'
import { useWorldStore } from '../../../stores/worldStore'
import EmptyState from '../../../components/common/EmptyState'
import type { StyleTemplate } from '../../../types/world'

interface Props {
  projectId: string
}

export default function StyleTemplateTab({ projectId }: Props) {
  const {
    templates,
    fetchTemplates,
    createTemplate,
    updateTemplate,
    deleteTemplate,
    setDefaultTemplate,
  } = useWorldStore()

  const [templateModalOpen, setTemplateModalOpen] = useState(false)
  const [templateForm] = Form.useForm()
  const [editingTemplate, setEditingTemplate] = useState<StyleTemplate | null>(null)

  const handleCreateTemplate = async (values: any) => {
    try {
      if (editingTemplate) {
        await updateTemplate(projectId, editingTemplate.id, values)
        message.success('模板更新成功')
      } else {
        await createTemplate(projectId, values)
        message.success('模板创建成功')
      }
      setTemplateModalOpen(false)
      setEditingTemplate(null)
      templateForm.resetFields()
      fetchTemplates(projectId)
    } catch {
      message.error('操作失败')
    }
  }

  const handleEditTemplate = (template: StyleTemplate) => {
    setEditingTemplate(template)
    templateForm.setFieldsValue(template)
    setTemplateModalOpen(true)
  }

  const handleDeleteTemplate = (templateId: string) => {
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
    try {
      await setDefaultTemplate(projectId, templateId)
      message.success('已设为默认模板')
      fetchTemplates(projectId)
    } catch {
      message.error('操作失败')
    }
  }

  const templateColumns = [
    { title: '名称', dataIndex: 'name', key: 'name' },
    { title: '比例', dataIndex: 'aspect_ratio', key: 'aspect_ratio', render: (v?: string) => v || '-' },
    { title: '画风', dataIndex: 'art_style', key: 'art_style', ellipsis: true, render: (v?: string) => v || '-' },
    { title: '上色', dataIndex: 'coloring_style', key: 'coloring_style', ellipsis: true, render: (v?: string) => v || '-' },
    {
      title: '默认',
      key: 'is_default',
      width: 80,
      render: (_: any, record: StyleTemplate) => record.is_default ? <Tag color="green">默认</Tag> : null,
    },
    {
      title: '操作',
      key: 'action',
      width: 240,
      render: (_: any, record: StyleTemplate) => (
        <Space>
          {!record.is_default && (
            <Button size="small" type="primary" ghost onClick={() => handleSetDefault(record.id)}>
              设为默认
            </Button>
          )}
          <Button size="small" icon={<EditOutlined />} onClick={() => handleEditTemplate(record)}>
            编辑
          </Button>
          <Button size="small" danger icon={<DeleteOutlined />} onClick={() => handleDeleteTemplate(record.id)}>
            删除
          </Button>
        </Space>
      ),
    },
  ]

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 16 }}>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => { setEditingTemplate(null); templateForm.resetFields(); setTemplateModalOpen(true); }}>
          创建模板
        </Button>
      </div>
      {templates.length === 0 ? (
        <EmptyState description="暂无风格模板" />
      ) : (
        <Table dataSource={templates} columns={templateColumns} rowKey="id" pagination={false} size="small" />
      )}

      <Modal title={editingTemplate ? '编辑风格模板' : '创建风格模板'} open={templateModalOpen} onCancel={() => { setTemplateModalOpen(false); setEditingTemplate(null); }} footer={null} width={640}>
        <Form form={templateForm} layout="vertical" onFinish={handleCreateTemplate}>
          <Form.Item name="name" label="名称" rules={[{ required: true }]}>
            <Input placeholder="如：漫画风格、写实风格" />
          </Form.Item>
          <Form.Item name="aspect_ratio" label="画面比例">
            <Select allowClear options={[
              { label: '1:1.34 (默认竖屏)', value: '1:1.34' },
              { label: '16:9', value: '16:9' },
              { label: '4:3', value: '4:3' },
              { label: '1:1', value: '1:1' },
            ]} />
          </Form.Item>
          <Form.Item name="width" label="宽度(px)">
            <Input type="number" placeholder="1080" />
          </Form.Item>
          <Form.Item name="art_style" label="画风">
            <Input.TextArea rows={2} placeholder="如：日式漫画、美式卡通" />
          </Form.Item>
          <Form.Item name="coloring_style" label="上色风格">
            <Input.TextArea rows={2} placeholder="如：平涂、厚涂" />
          </Form.Item>
          <Form.Item name="lineart_style" label="线稿风格">
            <Input.TextArea rows={2} placeholder="如：细线、粗线" />
          </Form.Item>
          <Form.Item name="lighting_style" label="光照风格">
            <Input.TextArea rows={2} placeholder="如：自然光、戏剧光" />
          </Form.Item>
          <Form.Item name="negative_prompt" label="负面提示词">
            <Input.TextArea rows={2} placeholder="不希望出现的元素" />
          </Form.Item>
          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit">保存</Button>
              <Button onClick={() => { setTemplateModalOpen(false); setEditingTemplate(null); }}>取消</Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
