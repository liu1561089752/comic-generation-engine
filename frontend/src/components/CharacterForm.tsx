import { useEffect } from 'react'
import { Form, Input, Space, Button } from 'antd'

interface CharacterFormProps {
  initialValues?: { name?: string }
  loading?: boolean
  onSubmit: (values: any) => void
  onCancel: () => void
}

export default function CharacterForm({ initialValues, loading, onSubmit, onCancel }: CharacterFormProps) {
  const [form] = Form.useForm()

  useEffect(() => {
    if (initialValues) {
      form.setFieldsValue(initialValues)
    } else {
      form.resetFields()
    }
  }, [initialValues, form])

  return (
    <Form
      form={form}
      layout="vertical"
      onFinish={onSubmit}
    >
      <Form.Item
        name="name"
        label="角色昵称"
        rules={[{ required: true, message: '请输入角色昵称' }]}
      >
        <Input placeholder="请输入角色昵称，如：姜南星" />
      </Form.Item>

      <Form.Item>
        <Space>
          <Button type="primary" htmlType="submit" loading={loading}>
            {initialValues ? '更新' : '创建'}
          </Button>
          <Button onClick={onCancel}>取消</Button>
        </Space>
      </Form.Item>
    </Form>
  )
}
