import { useEffect, useState } from 'react'
import {
  Card,
  Row,
  Col,
  Select,
  Button,
  Progress,
  Table,
  Tag,
  Slider,
  Switch,
  Input,
  message,
  Typography,
  Badge,
  Space,
  Tooltip,
} from 'antd'
import {
  DownloadOutlined,
  PictureOutlined,
  FileImageOutlined,
  FileJpgOutlined,
  HistoryOutlined,
  CloseCircleOutlined,
  DeleteOutlined,
  RedoOutlined,
  FontSizeOutlined,
} from '@ant-design/icons'
import { useNavigate, useParams } from 'react-router-dom'
import { useProjectStore } from '../../stores/projectStore'
import { exportApi } from '../../api/exportApi'
import type { ExportTask } from '../../api/exportApi'
import { PROJECT_STATUS_MAP } from '../../types'
import Loading from '../../components/common/Loading'
import EmptyState from '../../components/common/EmptyState'
import { formatDate, formatFileSize } from '../../utils/format'

const { Text } = Typography

const EXPORT_FORMATS = [
  {
    key: 'long_image',
    label: '长图导出',
    description: '导出为 1080px 宽无限高的长条漫画图片',
    icon: <PictureOutlined style={{ fontSize: 28 }} />,
    color: '#6C5CE7',
  },
  {
    key: 'png_sequence',
    label: 'PNG 序列',
    description: '每页导出为独立的 PNG 图片，保持透明背景',
    icon: <FileImageOutlined style={{ fontSize: 28 }} />,
    color: '#00b894',
  },
  {
    key: 'jpg',
    label: 'JPG 导出',
    description: '每页导出为高压缩比的 JPG 图片',
    icon: <FileJpgOutlined style={{ fontSize: 28 }} />,
    color: '#e17055',
  },
]

const FORMAT_STATUS_MAP: Record<string, { color: string; text: string }> = {
  pending: { color: 'default', text: '等待中' },
  processing: { color: 'processing', text: '处理中' },
  completed: { color: 'success', text: '已完成' },
  failed: { color: 'error', text: '失败' },
}

export default function ExportCenter() {
  const navigate = useNavigate()
  const { id: projectId } = useParams<{ id: string }>()
  const { projects, fetchProjects } = useProjectStore()

  const [selectedProjectId, setSelectedProjectId] = useState<string | undefined>(projectId)
  const [selectedFormat, setSelectedFormat] = useState<string>('long_image')
  const [quality, setQuality] = useState(90)
  const [addAlias, setAddAlias] = useState(false)
  const [aliasName, setAliasName] = useState('')
  const [exporting, setExporting] = useState(false)
  const [exportProgress, setExportProgress] = useState(0)
  const [exportTasks, setExportTasks] = useState<ExportTask[]>([])
  const [tasksLoading, setTasksLoading] = useState(false)
  const [currentTaskId, setCurrentTaskId] = useState<string | null>(null)

  useEffect(() => {
    fetchProjects()
  }, [fetchProjects])

  useEffect(() => {
    if (selectedProjectId) {
      loadExportTasks(selectedProjectId)
    }
  }, [selectedProjectId])

  const loadExportTasks = async (pid: string) => {
    setTasksLoading(true)
    try {
      const res: any = await exportApi.list(pid)
      const data = (res as { data?: ExportTask[] }).data || []
      setExportTasks(data)
    } catch {
      setExportTasks([])
    } finally {
      setTasksLoading(false)
    }
  }

  const handleProjectChange = (value: string) => {
    setSelectedProjectId(value)
    navigate(`/projects/${value}/export`, { replace: true })
  }

  const handleExport = async () => {
    if (!selectedProjectId) return
    setExporting(true)
    setExportProgress(0)
    try {
      const res: any = await exportApi.create(selectedProjectId, {
        format: selectedFormat as 'long_image' | 'png_sequence' | 'jpg',
        quality,
        add_alias: addAlias,
        alias_name: aliasName,
      })
      const task = (res as { data?: ExportTask }).data
      if (task) {
        setCurrentTaskId(task.id)
        // 如果任务已经完成，立即结束导出状态
        if (task.status === 'completed') {
          setExporting(false)
          setExportProgress(100)
          loadExportTasks(selectedProjectId)
          const exportDir = task.export_dir || task.folder_name
          message.success(exportDir ? `导出完成，文件已保存到: ${exportDir}` : '导出完成')
          return
        } else if (task.status === 'failed') {
          setExporting(false)
          message.error('导出失败')
          return
        }
        message.success('导出任务已创建')
      }
    } catch {
      message.error('创建导出任务失败')
      setExporting(false)
    }
  }

  // 轮询导出进度
  useEffect(() => {
    if (!currentTaskId || !selectedProjectId) return
    const interval = setInterval(async () => {
      try {
        const res: any = await exportApi.get(selectedProjectId, currentTaskId)
        const taskData = res?.data || res
        if (taskData?.status === 'completed') {
          clearInterval(interval)
          setExporting(false)
          setExportProgress(100)
          setCurrentTaskId(null)
          loadExportTasks(selectedProjectId)
          const exportDir = taskData?.export_dir || taskData?.folder_name
          message.success(exportDir ? `导出完成，文件已保存到: ${exportDir}` : '导出完成')
        } else if (taskData?.status === 'failed') {
          clearInterval(interval)
          setExporting(false)
          setCurrentTaskId(null)
          message.error('导出失败')
        } else {
          setExportProgress(taskData?.progress || 0)
        }
      } catch {
        clearInterval(interval)
        setExporting(false)
        setCurrentTaskId(null)
      }
    }, 2000)
    return () => clearInterval(interval)
  }, [currentTaskId, selectedProjectId])

  const handleCancelExport = async () => {
    if (!selectedProjectId || !currentTaskId) return
    try {
      await exportApi.cancel(selectedProjectId, currentTaskId)
      message.success('已取消导出')
      setExporting(false)
      setCurrentTaskId(null)
      setExportProgress(0)
    } catch {
      message.error('取消失败')
    }
  }

  const handleDeleteExport = async (taskId: string) => {
    if (!selectedProjectId) return
    try {
      await exportApi.cancel(selectedProjectId, taskId)
      setExportTasks((prev) => prev.filter((t) => t.id !== taskId))
      message.success('导出记录已删除')
    } catch {
      message.error('删除失败')
    }
  }

  const handleReExport = async (task: ExportTask) => {
    if (!selectedProjectId) return
    try {
      const res: any = await exportApi.create(selectedProjectId, {
        format: (task.format || 'long_image') as 'long_image' | 'png_sequence' | 'jpg',
        quality,
        add_alias: addAlias,
        alias_name: aliasName,
      })
      const newTask = (res as { data?: ExportTask }).data
      if (newTask) {
        setCurrentTaskId(newTask.id)
        setExporting(true)
        setExportProgress(0)
        message.success('重新导出任务已创建')
      }
    } catch {
      message.error('重新导出失败')
    }
  }

  const currentProject = projects.find((p) => p.id === selectedProjectId)

  const exportColumns = [
    {
      title: '格式',
      dataIndex: 'format',
      key: 'format',
      width: 90,
      render: (format: string) => {
        const fmt = EXPORT_FORMATS.find((f) => f.key === format)
        return fmt?.label || format
      },
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 80,
      render: (status: string) => {
        const s = FORMAT_STATUS_MAP[status] || { color: 'default', text: status }
        return <Tag color={s.color}>{s.text}</Tag>
      },
    },
    {
      title: '进度',
      dataIndex: 'progress',
      key: 'progress',
      width: 150,
      render: (progress: number, record: ExportTask) =>
        record.status === 'processing' ? (
          <Progress percent={progress} size="small" style={{ margin: 0 }} />
        ) : record.status === 'completed' ? (
          <span style={{ color: '#52c41a' }}>已完成</span>
        ) : record.status === 'failed' ? (
          <span style={{ color: '#ff4d4f' }}>失败</span>
        ) : (
          <span style={{ color: '#999' }}>-</span>
        ),
    },
    {
      title: '文件大小',
      dataIndex: 'file_size',
      key: 'file_size',
      width: 90,
      render: (size: number) => (size ? formatFileSize(size) : '-'),
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 150,
      render: (date: string) => formatDate(date),
    },
    {
      title: '导出路径',
      key: 'export_dir',
      width: 200,
      render: (_: any, record: ExportTask) =>
        record.export_dir ? (
          <Tooltip title={record.export_dir}>
            <Text type="secondary" ellipsis style={{ maxWidth: 180, display: 'inline-block' }}>
              {record.export_dir}
            </Text>
          </Tooltip>
        ) : (
          <Text type="secondary">-</Text>
        ),
    },
    {
      title: '操作',
      key: 'action',
      width: 120,
      render: (_: any, record: ExportTask) => (
        <Space size="small">
          <Tooltip title="重新导出">
            <Button
              type="link"
              size="small"
              icon={<RedoOutlined />}
              disabled={record.status === 'processing'}
              onClick={() => handleReExport(record)}
            />
          </Tooltip>
          <Tooltip title="删除记录">
            <Button
              type="link"
              size="small"
              danger
              icon={<DeleteOutlined />}
              onClick={() => handleDeleteExport(record.id)}
            />
          </Tooltip>
        </Space>
      ),
    },
  ]

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <h2 style={{ margin: 0, fontSize: 20, fontWeight: 600 }}>导出中心</h2>
      </div>

      {/* 项目选择 */}
      <Card style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ fontWeight: 500, whiteSpace: 'nowrap' }}>选择项目：</span>
          <Select
            placeholder="请选择项目"
            style={{ width: 300 }}
            value={selectedProjectId}
            onChange={handleProjectChange}
            options={projects.map((p) => ({
              label: p.name,
              value: p.id,
            }))}
          />
          {currentProject && (
            <Badge
              status={
                currentProject.status === 'completed'
                  ? 'success'
                  : currentProject.status === 'editing'
                    ? 'warning'
                    : 'processing'
              }
              text={PROJECT_STATUS_MAP[currentProject.status as keyof typeof PROJECT_STATUS_MAP] || currentProject.status}
            />
          )}
        </div>
      </Card>

      {!selectedProjectId ? (
        <EmptyState description="请先选择一个项目开始导出" />
      ) : (
        <>
          {/* 导出格式选择 */}
          <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
            {EXPORT_FORMATS.map((fmt) => (
              <Col key={fmt.key} xs={24} sm={12} md={8}>
                <Card
                  hoverable
                  style={{
                    border: selectedFormat === fmt.key ? `2px solid ${fmt.color}` : '1px solid #f0f0f0',
                    cursor: 'pointer',
                  }}
                  onClick={() => setSelectedFormat(fmt.key)}
                >
                  <div style={{ textAlign: 'center', marginBottom: 12 }}>
                    <div style={{ color: fmt.color }}>{fmt.icon}</div>
                  </div>
                  <div style={{ textAlign: 'center' }}>
                    <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 4 }}>
                      {fmt.label}
                    </div>
                    <div style={{ fontSize: 12, color: '#999' }}>{fmt.description}</div>
                  </div>
                </Card>
              </Col>
            ))}
          </Row>

          <Row gutter={[16, 16]}>
            {/* 导出参数 */}
            <Col xs={24} lg={12}>
              <Card title="导出参数">
                <div style={{ marginBottom: 20 }}>
                  <div style={{ marginBottom: 8 }}>
                    <Text strong>图片质量</Text>
                    <Text type="secondary" style={{ marginLeft: 8, fontSize: 12 }}>
                      ({quality}%)
                    </Text>
                  </div>
                  <Slider
                    min={10}
                    max={100}
                    value={quality}
                    onChange={(v) => setQuality(v)}
                    marks={{ 10: '10%', 50: '50%', 100: '100%' }}
                  />
                </div>

                <div style={{ marginBottom: 16 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                    <Text strong><FontSizeOutlined style={{ marginRight: 6 }} />加别名页码</Text>
                    <Switch checked={addAlias} onChange={setAddAlias} />
                  </div>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    在导出的每张图片底部中间添加页码标识
                  </Text>
                  {addAlias && (
                    <div style={{ marginTop: 8 }}>
                      <Input
                        placeholder="请输入漫画别名（如：果熊派对）"
                        value={aliasName}
                        onChange={(e) => setAliasName(e.target.value)}
                        allowClear
                      />
                    </div>
                  )}
                </div>

                <div style={{ marginTop: 24 }}>
                  {exporting ? (
                    <div>
                      <Progress percent={exportProgress} status="active" />
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 8 }}>
                        <Text type="secondary">正在导出，请稍候...</Text>
                        <Button
                          size="small"
                          icon={<CloseCircleOutlined />}
                          onClick={handleCancelExport}
                          danger
                        >
                          取消
                        </Button>
                      </div>
                    </div>
                  ) : (
                    <Button
                      type="primary"
                      icon={<DownloadOutlined />}
                      onClick={handleExport}
                      size="large"
                      block
                    >
                      开始导出
                    </Button>
                  )}
                </div>
              </Card>
            </Col>

            {/* 导出历史 */}
            <Col xs={24} lg={12}>
              <Card
                title={
                  <span>
                    <HistoryOutlined style={{ marginRight: 8 }} />
                    导出历史
                  </span>
                }
              >
                {tasksLoading ? (
                  <Loading tip="加载导出历史..." />
                ) : exportTasks.length === 0 ? (
                  <EmptyState description="暂无导出记录" />
                ) : (
                  <Table
                    dataSource={exportTasks}
                    columns={exportColumns}
                    rowKey="id"
                    pagination={{ pageSize: 5, showSizeChanger: false }}
                    size="small"
                  />
                )}
              </Card>
            </Col>
          </Row>
        </>
      )}
    </div>
  )
}
