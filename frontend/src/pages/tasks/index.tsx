import { useEffect, useState, useCallback, useRef } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Card, Modal, Space, Tabs, Typography, message } from 'antd'
import apiClient from '../../api/client'
import TaskListTab from './components/TaskListTab'
import type { TaskItem } from './components/types'

const { Text } = Typography

export default function TaskCenter() {
  const [searchParams, setSearchParams] = useSearchParams()

  // Tab
  const [activeTab, setActiveTab] = useState('list')

  // 列表状态
  const [loading, setLoading] = useState(false)
  const [tasks, setTasks] = useState<TaskItem[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)

  // 筛选
  const [statusFilter, setStatusFilter] = useState(searchParams.get('status') || '')
  const [typeFilter, setTypeFilter] = useState(searchParams.get('task_type') || '')
  const [priorityFilter, setPriorityFilter] = useState(searchParams.get('priority') || '')
  const [projectFilter, setProjectFilter] = useState(searchParams.get('project_id') || '')
  const [sortBy, setSortBy] = useState('created_at')
  const [sortOrder, setSortOrder] = useState('desc')
  const [dateRange, setDateRange] = useState<[string, string] | null>(null)

  // 详情面板
  const [expandedRowKeys, setExpandedRowKeys] = useState<string[]>([])

  // 批量选择
  const [selectedRowKeys, setSelectedRowKeys] = useState<string[]>([])

  // 操作状态
  const [actionLoading, setActionLoading] = useState<string | null>(null)
  const [batchLoading, setBatchLoading] = useState(false)

  // 列表轮询
  const pollingRef = useRef<ReturnType<typeof setInterval>>()

  // ─── 定时刷新 ───

  useEffect(() => {
    if (activeTab === 'list') {
      // 挂载及筛选/分页/排序变化时立即拉取一次（非 silent，展示 loading）
      fetchTasks()
      pollingRef.current = setInterval(() => {
        fetchTasks(true)
      }, 5000)
    }
    return () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current)
      }
    }
  }, [activeTab, page, pageSize, statusFilter, typeFilter, priorityFilter, projectFilter, sortBy, sortOrder, dateRange])

  // ─── 数据获取 ───

  const fetchTasks = useCallback(async (silent = false) => {
    if (!silent) setLoading(true)
    try {
      const params: any = {
        page,
        page_size: pageSize,
        sort_by: sortBy,
        sort_order: sortOrder,
      }
      if (statusFilter) params.status = statusFilter
      if (typeFilter) params.task_type = typeFilter
      if (priorityFilter) params.priority = priorityFilter
      if (projectFilter) params.project_id = projectFilter
      if (dateRange) {
        params.date_from = dateRange[0]
        params.date_to = dateRange[1]
      }

      const res: any = await apiClient.get('/tasks', { params })
      const data = res.data || res
      setTasks(data.items || [])
      setTotal(data.total || 0)
    } catch (e) {
      console.error('获取任务列表失败:', e)
      if (!silent) message.error('获取任务列表失败')
    } finally {
      if (!silent) setLoading(false)
    }
  }, [page, pageSize, statusFilter, typeFilter, priorityFilter, projectFilter, sortBy, sortOrder, dateRange])

  // ─── 操作 ───

  const handleCancel = async (taskId: string) => {
    setActionLoading(taskId)
    try {
      await apiClient.post(`/tasks/${taskId}/cancel`)
      message.success('任务已取消')
      fetchTasks()
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '取消失败')
    } finally {
      setActionLoading(null)
    }
  }

  const handleRetry = async (taskId: string) => {
    setActionLoading(taskId)
    try {
      await apiClient.post(`/tasks/${taskId}/retry`)
      message.success('任务已重新提交')
      fetchTasks()
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '重试失败')
    } finally {
      setActionLoading(null)
    }
  }

  const handleBatchCancel = async () => {
    if (selectedRowKeys.length === 0) {
      message.warning('请选择要取消的任务')
      return
    }
    Modal.confirm({
      title: '确认批量取消',
      content: `确定要取消选中的 ${selectedRowKeys.length} 个任务吗？`,
      onOk: async () => {
        setBatchLoading(true)
        try {
          const res: any = await apiClient.post('/tasks/batch-cancel', { task_ids: selectedRowKeys })
          const data = res.data || res
          message.success(`成功取消 ${data.succeeded?.length || 0} 个任务`)
          if (data.failed?.length > 0) {
            message.warning(`${data.failed.length} 个任务取消失败`)
          }
          setSelectedRowKeys([])
          fetchTasks()
        } catch {
          message.error('批量取消失败')
        } finally {
          setBatchLoading(false)
        }
      },
    })
  }

  const handleBatchRetry = async () => {
    if (selectedRowKeys.length === 0) {
      message.warning('请选择要重试的任务')
      return
    }
    Modal.confirm({
      title: '确认批量重试',
      content: `确定要重试选中的 ${selectedRowKeys.length} 个任务吗？`,
      onOk: async () => {
        setBatchLoading(true)
        try {
          const res: any = await apiClient.post('/tasks/batch-retry', { task_ids: selectedRowKeys })
          const data = res.data || res
          message.success(`成功重试 ${data.succeeded?.length || 0} 个任务`)
          if (data.failed?.length > 0) {
            message.warning(`${data.failed.length} 个任务重试失败`)
          }
          setSelectedRowKeys([])
          fetchTasks()
        } catch {
          message.error('批量重试失败')
        } finally {
          setBatchLoading(false)
        }
      },
    })
  }

  // ─── 筛选变更 ───

  const applyFilter = (key: string, value: string) => {
    const params = new URLSearchParams(searchParams)
    if (value) params.set(key, value)
    else params.delete(key)
    setSearchParams(params)
  }

  const handleStatusFilterChange = (v: string) => {
    setStatusFilter(v)
    setPage(1)
    applyFilter('status', v)
  }

  const handleTypeFilterChange = (v: string) => {
    setTypeFilter(v)
    setPage(1)
    applyFilter('task_type', v)
  }

  const handlePriorityFilterChange = (v: string) => {
    setPriorityFilter(v)
    setPage(1)
    applyFilter('priority', v)
  }

  const handleProjectFilterChange = (v: string) => {
    setProjectFilter(v)
    setPage(1)
  }

  const handleDateRangeChange = (range: [string, string] | null) => {
    setDateRange(range)
    setPage(1)
  }

  const handleSortChange = (field: string, order: 'asc' | 'desc') => {
    if (field === 'created_at') {
      setSortBy('created_at')
      setSortOrder(order)
    }
  }

  // ─── 渲染 ───

  const tabItems = [
    {
      key: 'list',
      label: '任务列表',
      children: (
        <TaskListTab
          tasks={tasks}
          loading={loading}
          total={total}
          page={page}
          pageSize={pageSize}
          statusFilter={statusFilter}
          typeFilter={typeFilter}
          priorityFilter={priorityFilter}
          projectFilter={projectFilter}
          sortBy={sortBy}
          sortOrder={sortOrder}
          selectedRowKeys={selectedRowKeys}
          expandedRowKeys={expandedRowKeys}
          actionLoading={actionLoading}
          batchLoading={batchLoading}
          onStatusFilterChange={handleStatusFilterChange}
          onTypeFilterChange={handleTypeFilterChange}
          onPriorityFilterChange={handlePriorityFilterChange}
          onProjectFilterChange={handleProjectFilterChange}
          onDateRangeChange={handleDateRangeChange}
          onSortByChange={setSortBy}
          onSortOrderChange={setSortOrder}
          onPageChange={(p, ps) => { setPage(p); setPageSize(ps) }}
          onSelectedRowKeysChange={setSelectedRowKeys}
          onExpandedRowKeysChange={setExpandedRowKeys}
          onSortChange={handleSortChange}
          onRefresh={() => fetchTasks()}
          onBatchCancel={handleBatchCancel}
          onBatchRetry={handleBatchRetry}
          onCancelTask={handleCancel}
          onRetryTask={handleRetry}
        />
      ),
    },
  ]

  return (
    <>
      <Card styles={{ body: { padding: '16px 24px' } }}>
        <Tabs
          activeKey={activeTab}
          onChange={(key) => setActiveTab(key)}
          items={tabItems}
          tabBarExtraContent={
            <Space>
              <Text type="secondary" style={{ fontSize: 12 }}>
                每5秒自动刷新
              </Text>
            </Space>
          }
        />
      </Card>
    </>
  )
}
