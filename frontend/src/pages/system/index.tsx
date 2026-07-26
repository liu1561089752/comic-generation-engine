import { useState, useEffect, useCallback } from 'react'
import {
  Card, Tabs, Form, Input, InputNumber, Switch, Button, Typography, Space, message,
  Table, Tag, Row, Col, Statistic, Progress, Modal, Divider, Select, Tooltip,
} from 'antd'
import {
  BellOutlined, SettingOutlined, UserOutlined,
  DatabaseOutlined, FileTextOutlined, ReloadOutlined,
  DeleteOutlined, DownloadOutlined, UploadOutlined, KeyOutlined, CloudUploadOutlined,
} from '@ant-design/icons'
import apiClient from '../../api/client'
import { formatDate } from '../../utils/format'

const { Text, Title } = Typography

export default function SystemSettings() {
  const [activeTab, setActiveTab] = useState('profile')

  const tabItems = [
    {
      key: 'profile',
      label: <span><UserOutlined /> 用户设置</span>,
      children: <UserSettings />,
    },
    {
      key: 'general',
      label: <span><SettingOutlined /> 系统设置</span>,
      children: <GeneralSettings />,
    },
    {
      key: 'storage',
      label: <span><DatabaseOutlined /> 存储管理</span>,
      children: <StorageManagement />,
    },
    {
      key: 'logs',
      label: <span><FileTextOutlined /> 操作日志</span>,
      children: <ActivityLogs />,
    },
    {
      key: 'backup',
      label: <span><CloudUploadOutlined /> 数据备份</span>,
      children: <BackupManager />,
    },
    {
      key: 'notifications',
      label: <span><BellOutlined /> 通知设置</span>,
      children: <NotificationSettings />,
    },
  ]

  return (
    <div>
      <Title level={4} style={{ marginTop: 0, marginBottom: 24 }}>
        <SettingOutlined /> 系统管理
      </Title>
      <Tabs activeKey={activeTab} onChange={setActiveTab} items={tabItems} />
    </div>
  )
}

// ---------- 用户设置 ----------

function UserSettings() {
  const [form] = Form.useForm()
  const [pwdForm] = Form.useForm()
  const [saving, setSaving] = useState(false)
  const [pwdSaving, setPwdSaving] = useState(false)

  const handleSaveProfile = async () => {
    setSaving(true)
    try {
      await apiClient.put('/auth/profile', form.getFieldsValue())
      message.success('个人信息已更新')
    } catch {
      message.error('保存失败')
    } finally {
      setSaving(false)
    }
  }

  const handleChangePassword = async () => {
    const values = pwdForm.getFieldsValue()
    if (values.new_password !== values.confirm_password) {
      message.error('两次输入的密码不一致')
      return
    }
    setPwdSaving(true)
    try {
      await apiClient.post('/auth/change-password', {
        old_password: values.old_password,
        new_password: values.new_password,
      })
      message.success('密码已修改')
      pwdForm.resetFields()
    } catch {
      message.error('密码修改失败')
    } finally {
      setPwdSaving(false)
    }
  }

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      <Card title="个人信息">
        <Form
          form={form}
          layout="vertical"
          initialValues={{ username: 'admin', email: 'admin@example.com', display_name: '管理员' }}
          style={{ maxWidth: 480 }}
        >
          <Form.Item label="用户名" name="username">
            <Input disabled />
          </Form.Item>
          <Form.Item label="显示名称" name="display_name" rules={[{ required: true, message: '请输入显示名称' }]}>
            <Input placeholder="请输入显示名称" />
          </Form.Item>
          <Form.Item label="邮箱" name="email" rules={[{ type: 'email', message: '请输入有效邮箱' }]}>
            <Input placeholder="email@example.com" />
          </Form.Item>
          <Form.Item label="偏好语言" name="language">
            <Select options={[{ label: '简体中文', value: 'zh-CN' }, { label: 'English', value: 'en' }]} />
          </Form.Item>
          <Form.Item>
            <Button type="primary" loading={saving} onClick={handleSaveProfile}>保存修改</Button>
          </Form.Item>
        </Form>
      </Card>

      <Card title="修改密码">
        <Form form={pwdForm} layout="vertical" style={{ maxWidth: 480 }}>
          <Form.Item label="当前密码" name="old_password" rules={[{ required: true, message: '请输入当前密码' }]}>
            <Input.Password autoComplete="off" />
          </Form.Item>
          <Form.Item label="新密码" name="new_password" rules={[
            { required: true, message: '请输入新密码' },
            { min: 6, message: '密码至少6位' },
          ]}>
            <Input.Password autoComplete="off" />
          </Form.Item>
          <Form.Item label="确认新密码" name="confirm_password" rules={[{ required: true, message: '请确认新密码' }]}>
            <Input.Password autoComplete="off" />
          </Form.Item>
          <Form.Item>
            <Button type="primary" loading={pwdSaving} onClick={handleChangePassword} icon={<KeyOutlined />}>
              修改密码
            </Button>
          </Form.Item>
        </Form>
      </Card>
    </Space>
  )
}

// ---------- 系统设置 ----------

function GeneralSettings() {
  const [form] = Form.useForm()
  const [saving, setSaving] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetch = async () => {
      try {
        const res: any = await apiClient.get('/system/config')
        const cfg = res?.data || res
        form.setFieldsValue({
          image_max_concurrent: cfg.image_max_concurrent ?? 2,
          storage_backend: cfg.storage_backend || 'local',
          app_debug: cfg.app_debug ?? false,
          app_log_level: cfg.app_log_level || 'INFO',
        })
      } catch {
        // ignore
      } finally {
        setLoading(false)
      }
    }
    fetch()
  }, [form])

  const handleSave = async () => {
    setSaving(true)
    try {
      await apiClient.put('/system/config', form.getFieldsValue())
      message.success('系统设置已更新')
    } catch {
      message.error('保存失败')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Card loading={loading} title="系统参数配置">
      <Form
        form={form}
        layout="vertical"
        style={{ maxWidth: 480 }}
        onFinish={handleSave}
      >
        <Form.Item label="存储后端" name="storage_backend">
          <Select options={[
            { label: '本地存储', value: 'local' },
            { label: 'S3 兼容', value: 's3' },
            { label: '阿里云 OSS', value: 'oss' },
          ]} />
        </Form.Item>
        <Form.Item label="最大并发数" name="image_max_concurrent" tooltip="图片生成最大并发任务数">
          <InputNumber min={1} max={10} style={{ width: '100%' }} />
        </Form.Item>
        <Form.Item label="调试模式" name="app_debug" valuePropName="checked">
          <Switch />
        </Form.Item>
        <Form.Item label="日志级别" name="app_log_level">
          <Select options={[
            { label: 'DEBUG', value: 'DEBUG' },
            { label: 'INFO', value: 'INFO' },
            { label: 'WARNING', value: 'WARNING' },
            { label: 'ERROR', value: 'ERROR' },
          ]} />
        </Form.Item>
        <Form.Item>
          <Button type="primary" htmlType="submit" loading={saving}>保存设置</Button>
        </Form.Item>
      </Form>
    </Card>
  )
}

// ---------- 存储管理 ----------

function StorageManagement() {
  const [stats, setStats] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [clearing, setClearing] = useState(false)

  const fetchStats = useCallback(async () => {
    setLoading(true)
    try {
      const res: any = await apiClient.get('/system/storage/stats')
      setStats(res?.data || res)
    } catch {
      setStats(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchStats() }, [fetchStats])

  const handleClearCache = async () => {
    setClearing(true)
    try {
      const res: any = await apiClient.post('/system/storage/clear-cache')
      const data = res?.data || res
      message.success(`已清理 ${data?.cleared_mb || 0} MB 缓存`)
      fetchStats()
    } catch {
      message.error('清理失败')
    } finally {
      setClearing(false)
    }
  }

  const usagePercent = stats ? Math.min(100, Math.round((stats.total_size_mb / stats.storage_limit_mb) * 100)) : 0

  return (
    <Card loading={loading}>
      <Row gutter={24}>
        <Col span={8}>
          <Card size="small">
            <Statistic title="存储路径" value={stats?.storage_path || '-'} valueStyle={{ fontSize: 14 }} />
          </Card>
        </Col>
        <Col span={8}>
          <Card size="small">
            <Statistic title="已用空间" value={stats?.total_size_mb || 0} suffix="MB" precision={2} />
          </Card>
        </Col>
        <Col span={8}>
          <Card size="small">
            <Statistic title="文件数量" value={stats?.file_count || 0} />
          </Card>
        </Col>
      </Row>

      <Divider />

      <div style={{ marginBottom: 16 }}>
        <Text strong>存储使用率</Text>
        <Progress percent={usagePercent} status={usagePercent > 80 ? 'exception' : 'active'} format={p => `${p}% (${stats?.total_size_mb || 0}MB / ${stats?.storage_limit_mb || 10240}MB)`} />
      </div>

      <Space>
        <Button type="primary" icon={<ReloadOutlined />} onClick={fetchStats}>刷新统计</Button>
        <Button danger icon={<DeleteOutlined />} loading={clearing} onClick={handleClearCache}>清理缓存</Button>
      </Space>
    </Card>
  )
}

// ---------- 操作日志 ----------

function ActivityLogs() {
  const [logs, setLogs] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [moduleFilter, setModuleFilter] = useState('')
  const [search, setSearch] = useState('')
  const [pagination, setPagination] = useState({ current: 1, pageSize: 15, total: 0 })

  const fetchLogs = useCallback(async (page = 1) => {
    setLoading(true)
    try {
      const params: any = { page, page_size: pagination.pageSize }
      if (moduleFilter) params.module = moduleFilter
      if (search) params.search = search
      const res: any = await apiClient.get('/system/activity-logs', { params })
      const data = res?.data || res
      setLogs(data?.items || [])
      setPagination(prev => ({ ...prev, current: page, total: data?.total || 0 }))
    } catch {
      setLogs([])
    } finally {
      setLoading(false)
    }
  }, [moduleFilter, search, pagination.pageSize])

  useEffect(() => { fetchLogs() }, [fetchLogs])

  const columns = [
    { title: '时间', dataIndex: 'created_at', key: 'created_at', width: 170, render: (t: string) => t ? formatDate(t) : '-' },
    { title: '模块', dataIndex: 'module', key: 'module', width: 100, render: (m: string) => <Tag>{m}</Tag> },
    { title: '操作', dataIndex: 'action', key: 'action', width: 120 },
    { title: '用户', dataIndex: 'user_id', key: 'user_id', width: 100, render: (u: string) => u ? <Text code>{u.slice(0, 8)}</Text> : '-' },
    { title: '详情', dataIndex: 'details', key: 'details', ellipsis: true, render: (d: any) => d ? JSON.stringify(d) : '-' },
    { title: 'IP', dataIndex: 'ip_address', key: 'ip_address', width: 130 },
  ]

  return (
    <Card extra={
      <Space wrap>
        <Select
          style={{ width: 110 }}
          placeholder="模块"
          allowClear
          value={moduleFilter || undefined}
          onChange={v => setModuleFilter(v || '')}
          options={[
            { label: '全部', value: '' },
            { label: '系统', value: 'system' },
            { label: '项目', value: 'project' },
            { label: '模型', value: 'model' },
            { label: '用户', value: 'user' },
          ]}
        />
        <Input.Search
          placeholder="搜索详情..."
          style={{ width: 200 }}
          value={search}
          onChange={e => setSearch(e.target.value)}
          onSearch={() => fetchLogs(1)}
          allowClear
        />
        <Tooltip title="刷新">
          <Button icon={<ReloadOutlined />} onClick={() => fetchLogs(pagination.current)} />
        </Tooltip>
      </Space>
    }>
      <Table
        dataSource={logs}
        columns={columns}
        rowKey="id"
        loading={loading}
        pagination={{
          ...pagination,
          showSizeChanger: true,
          showTotal: (t) => `共 ${t} 条`,
        }}
        onChange={(pag) => fetchLogs(pag.current || 1)}
        locale={{ emptyText: '暂无操作日志' }}
        size="small"
        scroll={{ x: 800 }}
      />
    </Card>
  )
}

// ---------- 数据备份 ----------

function BackupManager() {
  const [backups, setBackups] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [creating, setCreating] = useState(false)
  const [restoring, setRestoring] = useState(false)

  const fetchBackups = useCallback(async () => {
    setLoading(true)
    try {
      const res: any = await apiClient.get('/system/backups')
      setBackups(res?.data || res || [])
    } catch {
      setBackups([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchBackups() }, [fetchBackups])

  const handleCreateBackup = async () => {
    setCreating(true)
    try {
      const res: any = await apiClient.post('/system/backup')
      const data = res?.data || res
      message.success(`备份创建成功: ${data?.backup_name || ''}`)
      fetchBackups()
    } catch {
      message.error('备份创建失败')
    } finally {
      setCreating(false)
    }
  }

  const handleRestore = (name: string) => {
    Modal.confirm({
      title: '确认恢复',
      content: `将从备份 ${name} 恢复数据，当前数据将被备份为 .bak 文件。确定继续？`,
      onOk: async () => {
        setRestoring(true)
        try {
          await apiClient.post('/system/backup/restore', { backup_name: name })
          message.success('数据恢复成功，请重新登录')
        } catch {
          message.error('数据恢复失败')
        } finally {
          setRestoring(false)
        }
      },
    })
  }

  const columns = [
    { title: '文件名', dataIndex: 'name', key: 'name' },
    { title: '大小', dataIndex: 'size_mb', key: 'size_mb', render: (s: number) => `${s} MB` },
    { title: '创建时间', dataIndex: 'created_at', key: 'created_at', render: (t: string) => t ? formatDate(t) : '-' },
    {
      title: '操作', key: 'action',
      render: (_: any, record: any) => (
        <Space>
          <Button type="link" size="small" icon={<DownloadOutlined />}>下载</Button>
          <Button type="link" size="small" danger icon={<UploadOutlined />} loading={restoring} onClick={() => handleRestore(record.name)}>
            恢复
          </Button>
        </Space>
      ),
    },
  ]

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      <Card>
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <Row gutter={16} align="middle">
            <Col flex="auto">
              <Text strong>手动备份</Text>
              <br />
              <Text type="secondary">创建当前数据的完整备份，包括数据库和配置文件</Text>
            </Col>
            <Col>
              <Button type="primary" icon={<CloudUploadOutlined />} loading={creating} onClick={handleCreateBackup}>
                创建备份
              </Button>
            </Col>
          </Row>
        </Space>
      </Card>

      <Card title="备份列表" extra={<Button icon={<ReloadOutlined />} onClick={fetchBackups}>刷新</Button>}>
        <Table
          dataSource={backups}
          columns={columns}
          rowKey="name"
          loading={loading}
          pagination={false}
          locale={{ emptyText: '暂无备份数据' }}
          size="small"
        />
      </Card>
    </Space>
  )
}

// ---------- 通知设置 ----------

function NotificationSettings() {
  const [form] = Form.useForm()
  const [saving, setSaving] = useState(false)

  const handleSave = async () => {
    setSaving(true)
    try {
      await apiClient.post('/notifications/settings', form.getFieldsValue())
      message.success('通知设置已保存')
    } catch {
      message.error('保存失败')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Card title="通知偏好">
      <Form
        form={form}
        layout="vertical"
        initialValues={{
          task_complete: true,
          task_failed: true,
          system_notice: true,
          email_digest: false,
        }}
        style={{ maxWidth: 480 }}
      >
        <Form.Item label="任务完成通知" name="task_complete" valuePropName="checked">
          <Switch />
        </Form.Item>
        <Form.Item label="任务失败通知" name="task_failed" valuePropName="checked">
          <Switch />
        </Form.Item>
        <Form.Item label="系统公告" name="system_notice" valuePropName="checked">
          <Switch />
        </Form.Item>
        <Form.Item label="邮件摘要" name="email_digest" valuePropName="checked">
          <Switch />
        </Form.Item>
        <Form.Item>
          <Button type="primary" loading={saving} onClick={handleSave}>
            保存设置
          </Button>
        </Form.Item>
      </Form>
    </Card>
  )
}
