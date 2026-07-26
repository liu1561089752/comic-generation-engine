import { Card, Form, Input, Button, Descriptions, Tag, Space, Typography } from 'antd'
import type { FormInstance } from 'antd'
import { EditOutlined, CheckCircleOutlined } from '@ant-design/icons'
import type { LLMConfig } from './types'

const { Text, Title } = Typography

interface Props {
  config: LLMConfig | null
  loading: boolean
  editing: boolean
  saveLoading: boolean
  testLoading: boolean
  form: FormInstance
  onEdit: () => void
  onCancelEdit: () => void
  onSave: (values: LLMConfig) => void
  onTest: () => void
}

export default function LLMConfigTab({
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
        <>
          <Descriptions
            title="当前 LLM 配置"
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
                  测试连接
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
        </>
      ) : (
        <>
          <Title level={5}>编辑 LLM 配置</Title>
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
              help={
                <>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    中转站用户请在名称前加上 provider 前缀，例如：<Text code>openai/gpt-4o</Text>、<Text code>deepseek/deepseek-chat</Text>、<Text code>qwen/qwen-plus</Text>。
                    直接使用官方 API 则无需前缀（如 <Text code>gpt-4o</Text>）。
                  </Text>
                </>
              }
            >
              <Input placeholder="openai/gpt-4o 或 gpt-4o" style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item
              name="api_base"
              label="API Base URL"
              rules={[{ required: true, message: '请输入 API Base URL' }]}
            >
              <Input placeholder="https://api.openai.com/v1" />
            </Form.Item>
            <Form.Item
              name="api_key"
              label="API Key"
              rules={[{ required: true, message: '请输入 API Key' }]}
            >
              <Input.Password
                placeholder="sk-..."
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
