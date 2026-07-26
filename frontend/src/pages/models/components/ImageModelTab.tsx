import { Card, Form, Input, Button, Descriptions, Tag, Space, Typography } from 'antd'
import type { FormInstance } from 'antd'
import { EditOutlined, CheckCircleOutlined } from '@ant-design/icons'
import type { ImageModelConfig } from './types'

const { Text, Title } = Typography

interface Props {
  config: ImageModelConfig | null
  loading: boolean
  editing: boolean
  saveLoading: boolean
  testLoading: boolean
  form: FormInstance
  onEdit: () => void
  onCancelEdit: () => void
  onSave: (values: ImageModelConfig) => void
  onTest: () => void
}

export default function ImageModelTab({
  config,
  loading,
  editing,
  saveLoading,
  testLoading,
  form,
  onEdit,
  onCancelEdit,
  onSave,
  onTest,
}: Props) {
  return (
    <Card loading={loading}>
      {!editing ? (
        <Descriptions
          title="当前生图模型配置"
          bordered
          size="small"
          column={1}
          extra={
            <Space>
              <Button icon={<EditOutlined />} onClick={onEdit}>
                编辑
              </Button>
              <Button
                icon={<CheckCircleOutlined />}
                loading={testLoading}
                onClick={onTest}
              >
                测试生图
              </Button>
            </Space>
          }
        >
          <Descriptions.Item label="API Base URL">
            {config?.api_base ? (
              <Text code>{config.api_base}</Text>
            ) : (
              <Text type="secondary">未配置</Text>
            )}
          </Descriptions.Item>
          <Descriptions.Item label="Model Name">
            {config?.model_name ? (
              <Tag color="blue">{config.model_name}</Tag>
            ) : (
              <Text type="secondary">未配置</Text>
            )}
          </Descriptions.Item>
          <Descriptions.Item label="API Key">
            {config?.api_key ? (
              <Text>••••••••{config.api_key.slice(-4)}</Text>
            ) : (
              <Text type="secondary">未配置</Text>
            )}
          </Descriptions.Item>
          <Descriptions.Item label="激活状态">
            <Tag color={config?.is_active ? 'success' : 'default'}>
              {config?.is_active ? '已激活' : '未激活'}
            </Tag>
          </Descriptions.Item>
        </Descriptions>
      ) : (
        <>
          <Title level={5}>编辑生图模型配置</Title>
          <Form
            form={form}
            layout="vertical"
            onFinish={onSave}
            style={{ maxWidth: 600 }}
          >
            <Form.Item
              name="model_name"
              label="模型名称"
              rules={[{ required: true, message: '请输入模型名称' }]}
            >
              <Input placeholder="gpt-image-2 或 gpt-image-2-vip" style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item
              name="api_base"
              label="API Base URL"
              rules={[{ required: true, message: '请输入 API Base URL' }]}
            >
              <Input placeholder="https://api.example.com/v1" />
            </Form.Item>
            <Form.Item
              name="api_key"
              label="API Key"
              rules={[{ required: true, message: '请输入 API Key' }]}
            >
              <Input.Password
                placeholder="输入 API Key"
                autoComplete="off"
              />
            </Form.Item>
            <Form.Item>
              <Space>
                <Button type="primary" htmlType="submit" loading={saveLoading}>
                  保存
                </Button>
                <Button onClick={onCancelEdit}>取消</Button>
              </Space>
            </Form.Item>
          </Form>
        </>
      )}
    </Card>
  )
}
