import { useEffect, useState, useCallback } from 'react'
import { Tabs, Form, Space, Typography, message } from 'antd'
import { ApiOutlined, PictureOutlined, FileTextOutlined } from '@ant-design/icons'
import { modelApi } from '../../api/modelApi'
import LLMConfigTab from './components/LLMConfigTab'
import ImageModelTab from './components/ImageModelTab'
import ModelPresetTab from './components/ModelPresetTab'
import ModelLogsTab from './components/ModelLogsTab'
import type { LLMConfig, ImageModelConfig, ModelPreset, ModelLog } from './components/types'

const { Title } = Typography

export default function ModelCenter() {
  // LLM state
  const [llmConfig, setLlmConfig] = useState<LLMConfig | null>(null)
  const [llmLoading, setLlmLoading] = useState(false)
  const [llmSaveLoading, setLlmSaveLoading] = useState(false)
  const [llmTestLoading, setLlmTestLoading] = useState(false)
  const [llmForm] = Form.useForm()
  const [editingLlm, setEditingLlm] = useState(false)

  // Image model state
  const [imgConfig, setImgConfig] = useState<ImageModelConfig | null>(null)
  const [imgLoading, setImgLoading] = useState(false)
  const [imgSaveLoading, setImgSaveLoading] = useState(false)
  const [imgTestLoading, setImgTestLoading] = useState(false)
  const [imgForm] = Form.useForm()
  const [editingImg, setEditingImg] = useState(false)

  // Preset state
  const [presets, setPresets] = useState<ModelPreset[]>([])
  const [presetModalOpen, setPresetModalOpen] = useState(false)
  const [editingPreset, setEditingPreset] = useState<ModelPreset | null>(null)
  const [presetLoading, setPresetLoading] = useState(false)
  const [presetForm] = Form.useForm()

  // Log state
  const [logs, setLogs] = useState<ModelLog[]>([])
  const [logsLoading, setLogsLoading] = useState(false)
  const [logTypeFilter, setLogTypeFilter] = useState('')
  const [logStatusFilter, setLogStatusFilter] = useState('')
  const [logSearch, setLogSearch] = useState('')

  // ---------- LLM ----------

  const fetchLLMConfig = useCallback(async () => {
    setLlmLoading(true)
    try {
      const res: any = await modelApi.getLLMConfig()
      const config = res?.data || res
      setLlmConfig(config)
      if (config) {
        llmForm.setFieldsValue({
          api_base: config.api_base || '',
          api_key: config.api_key || '',
          model_name: config.model_name || '',
        })
      }
    } catch {
      // Not configured yet — fine
    } finally {
      setLlmLoading(false)
    }
  }, [llmForm])

  const handleSaveLLM = async (values: LLMConfig) => {
    setLlmSaveLoading(true)
    try {
      await modelApi.updateLLMConfig(values)
      message.success('LLM 配置已保存')
      setEditingLlm(false)
      fetchLLMConfig()
    } catch {
      message.error('保存 LLM 配置失败')
    } finally {
      setLlmSaveLoading(false)
    }
  }

  const handleTestLLM = async () => {
    setLlmTestLoading(true)
    try {
      await modelApi.testLLM()
      message.success('LLM 连接测试成功')
    } catch {
      message.error('LLM 连接测试失败，请检查配置')
    } finally {
      setLlmTestLoading(false)
    }
  }

  // ---------- Image Model ----------

  const fetchImageModelConfig = useCallback(async () => {
    setImgLoading(true)
    try {
      const res: any = await modelApi.getImageModelConfig()
      const config = res?.data || res
      setImgConfig(config)
      if (config) {
        imgForm.setFieldsValue({
          api_base: config.api_base || '',
          api_key: config.api_key || '',
          model_name: config.model_name || '',
        })
      }
    } catch {
      // Not configured yet
    } finally {
      setImgLoading(false)
    }
  }, [imgForm])

  const handleSaveImageModel = async (values: ImageModelConfig) => {
    setImgSaveLoading(true)
    try {
      await modelApi.updateImageModelConfig(values)
      message.success('生图模型配置已保存')
      setEditingImg(false)
      fetchImageModelConfig()
    } catch {
      message.error('保存生图模型配置失败')
    } finally {
      setImgSaveLoading(false)
    }
  }

  const handleTestImageModel = async () => {
    setImgTestLoading(true)
    try {
      await modelApi.testImageModel()
      message.success('生图模型测试成功')
    } catch {
      message.error('生图模型测试失败，请检查配置')
    } finally {
      setImgTestLoading(false)
    }
  }

  // ---------- Presets ----------

  const loadPresets = () => {
    const saved = localStorage.getItem('model_presets')
    if (saved) {
      try {
        setPresets(JSON.parse(saved))
      } catch {
        setPresets([])
      }
    } else {
      setPresets([
        {
          id: 'preset-1',
          name: '默认预设',
          steps: 30,
          cfg_scale: 7.5,
          width: 768,
          height: 1024,
          is_default: true,
        },
      ])
    }
  }

  const savePresets = (newPresets: ModelPreset[]) => {
    setPresets(newPresets)
    localStorage.setItem('model_presets', JSON.stringify(newPresets))
  }

  const handleOpenPreset = (preset?: ModelPreset) => {
    setEditingPreset(preset || null)
    presetForm.resetFields()
    if (preset) {
      presetForm.setFieldsValue(preset)
    }
    setPresetModalOpen(true)
  }

  const handleSavePreset = (values: any) => {
    setPresetLoading(true)
    const newPreset: ModelPreset = {
      id: editingPreset?.id || `preset-${Date.now()}`,
      ...values,
      is_default: editingPreset?.is_default || false,
    }
    let newPresets: ModelPreset[]
    if (editingPreset) {
      newPresets = presets.map((p) => (p.id === editingPreset.id ? newPreset : p))
    } else {
      newPresets = [...presets, newPreset]
    }
    savePresets(newPresets)
    message.success(editingPreset ? '预设已更新' : '预设已创建')
    setPresetModalOpen(false)
    setPresetLoading(false)
  }

  const handleDeletePreset = (id: string) => {
    const newPresets = presets.filter((p) => p.id !== id)
    savePresets(newPresets)
    message.success('预设已删除')
  }

  const handleSetDefaultPreset = (id: string) => {
    const newPresets = presets.map((p) => ({ ...p, is_default: p.id === id }))
    savePresets(newPresets)
    message.success('已设为默认预设')
  }

  // ---------- Logs ----------

  const fetchLogs = useCallback(async () => {
    setLogsLoading(true)
    try {
      const params: any = {}
      if (logTypeFilter) params.call_type = logTypeFilter
      if (logStatusFilter) params.status = logStatusFilter
      if (logSearch) params.search = logSearch

      const res: any = await modelApi.getModelLogs(params)
      const items = res?.data?.items || res?.items || res?.data || res || []
      setLogs(Array.isArray(items) ? items : [])
    } catch {
      setLogs([])
    } finally {
      setLogsLoading(false)
    }
  }, [logTypeFilter, logStatusFilter, logSearch])

  useEffect(() => {
    fetchLLMConfig()
    fetchImageModelConfig()
    loadPresets()
  }, [fetchLLMConfig, fetchImageModelConfig])

  useEffect(() => {
    fetchLogs()
  }, [fetchLogs])

  // ---------- Render ----------

  return (
    <div>
      <Title level={4} style={{ marginTop: 0, marginBottom: 24 }}>
        模型配置中心
      </Title>

      <Tabs
        defaultActiveKey="llm"
        items={[
          // ====== Tab 1: LLM ======
          {
            key: 'llm',
            label: (
              <span>
                <ApiOutlined /> LLM 模型配置
              </span>
            ),
            children: (
              <LLMConfigTab
                config={llmConfig}
                loading={llmLoading}
                editing={editingLlm}
                saveLoading={llmSaveLoading}
                testLoading={llmTestLoading}
                form={llmForm}
                onEdit={() => setEditingLlm(true)}
                onCancelEdit={() => setEditingLlm(false)}
                onSave={handleSaveLLM}
                onTest={handleTestLLM}
              />
            ),
          },

          // ====== Tab 2: Image Model ======
          {
            key: 'image',
            label: (
              <span>
                <PictureOutlined /> 生图模型配置
              </span>
            ),
            children: (
              <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                <ImageModelTab
                  config={imgConfig}
                  loading={imgLoading}
                  editing={editingImg}
                  saveLoading={imgSaveLoading}
                  testLoading={imgTestLoading}
                  form={imgForm}
                  onEdit={() => setEditingImg(true)}
                  onCancelEdit={() => setEditingImg(false)}
                  onSave={handleSaveImageModel}
                  onTest={handleTestImageModel}
                />
                <ModelPresetTab
                  presets={presets}
                  modalOpen={presetModalOpen}
                  editingPreset={editingPreset}
                  loading={presetLoading}
                  form={presetForm}
                  onOpen={handleOpenPreset}
                  onSave={handleSavePreset}
                  onDelete={handleDeletePreset}
                  onSetDefault={handleSetDefaultPreset}
                  onCloseModal={() => setPresetModalOpen(false)}
                />
              </Space>
            ),
          },

          // ====== Tab 3: Logs ======
          {
            key: 'logs',
            label: (
              <span>
                <FileTextOutlined /> 调用日志
              </span>
            ),
            children: (
              <ModelLogsTab
                logs={logs}
                loading={logsLoading}
                typeFilter={logTypeFilter}
                statusFilter={logStatusFilter}
                search={logSearch}
                onTypeFilterChange={setLogTypeFilter}
                onStatusFilterChange={setLogStatusFilter}
                onSearchChange={setLogSearch}
                onSearch={fetchLogs}
                onRefresh={fetchLogs}
              />
            ),
          },
        ]}
      />
    </div>
  )
}
