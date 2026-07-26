import {
  Card,
  Form,
  Input,
  InputNumber,
  Button,
  Tag,
  Space,
  Row,
  Col,
  Popconfirm,
  Modal,
} from 'antd'
import type { FormInstance } from 'antd'
import { PlusOutlined, DeleteOutlined, EditOutlined, FileTextOutlined } from '@ant-design/icons'
import type { ModelPreset } from './types'

interface Props {
  presets: ModelPreset[]
  modalOpen: boolean
  editingPreset: ModelPreset | null
  loading: boolean
  form: FormInstance
  onOpen: (preset?: ModelPreset) => void
  onSave: (values: any) => void
  onDelete: (id: string) => void
  onSetDefault: (id: string) => void
  onCloseModal: () => void
}

export default function ModelPresetTab({
  presets,
  modalOpen,
  editingPreset,
  loading,
  form,
  onOpen,
  onSave,
  onDelete,
  onSetDefault,
  onCloseModal,
}: Props) {
  return (
    <Card
      title="模型参数预设"
      extra={
        <Button
          type="primary"
          size="small"
          icon={<PlusOutlined />}
          onClick={() => onOpen()}
        >
          新建预设
        </Button>
      }
    >
      <Row gutter={[16, 16]}>
        {presets.map((preset) => (
          <Col key={preset.id} xs={24} sm={12} md={8} lg={6}>
            <Card
              size="small"
              hoverable
              style={{
                borderColor: preset.is_default ? '#1677ff' : undefined,
                position: 'relative',
              }}
              actions={[
                !preset.is_default ? (
                  <Button
                    type="link"
                    size="small"
                    onClick={() => onSetDefault(preset.id)}
                  >
                    设为默认
                  </Button>
                ) : (
                  <Tag color="blue" style={{ margin: 0 }}>
                    默认
                  </Tag>
                ),
                <Button
                  type="link"
                  size="small"
                  icon={<EditOutlined />}
                  onClick={() => onOpen(preset)}
                />,
                <Popconfirm
                  title="确定删除此预设？"
                  onConfirm={() => onDelete(preset.id)}
                >
                  <Button
                    type="link"
                    size="small"
                    danger
                    icon={<DeleteOutlined />}
                  />
                </Popconfirm>,
              ]}
            >
              {preset.is_default && (
                <Tag
                  color="blue"
                  style={{ position: 'absolute', top: 4, right: 4, fontSize: 11 }}
                >
                  默认
                </Tag>
              )}
              <div style={{ textAlign: 'center', marginBottom: 8 }}>
                <FileTextOutlined style={{ fontSize: 24, color: '#1677ff' }} />
              </div>
              <div style={{ fontWeight: 600, textAlign: 'center', marginBottom: 8 }}>
                {preset.name}
              </div>
              <div style={{ fontSize: 12, color: '#666' }}>
                <div>Steps: {preset.steps}</div>
                <div>CFG: {preset.cfg_scale}</div>
                <div>
                  尺寸: {preset.width}×{preset.height}
                </div>
              </div>
            </Card>
          </Col>
        ))}
      </Row>

      <Modal
        title={editingPreset ? '编辑预设' : '新建预设'}
        open={modalOpen}
        onCancel={onCloseModal}
        footer={null}
        width={500}
      >
        <Form form={form} layout="vertical" onFinish={onSave}>
          <Form.Item
            name="name"
            label="预设名称"
            rules={[{ required: true, message: '请输入预设名称' }]}
          >
            <Input placeholder="如：高质量预设、快速出图" />
          </Form.Item>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="steps"
                label="采样步数 (Steps)"
                rules={[{ required: true, message: '请输入步数' }]}
              >
                <InputNumber min={1} max={150} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="cfg_scale"
                label="CFG 引导尺度"
                rules={[{ required: true, message: '请输入 CFG' }]}
              >
                <InputNumber min={1} max={30} step={0.5} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="width"
                label="宽度"
                rules={[{ required: true, message: '请输入宽度' }]}
              >
                <InputNumber min={256} max={2048} step={64} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="height"
                label="高度"
                rules={[{ required: true, message: '请输入高度' }]}
              >
                <InputNumber min={256} max={2048} step={64} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit" loading={loading}>
                {editingPreset ? '保存修改' : '创建'}
              </Button>
              <Button onClick={onCloseModal}>取消</Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  )
}
