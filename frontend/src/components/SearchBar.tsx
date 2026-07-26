import { useState, useRef, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { Input, List, Typography, Tag, Spin, Empty, Space } from 'antd'
import { SearchOutlined, ProjectOutlined, FileTextOutlined, TeamOutlined, EnvironmentOutlined, CheckCircleOutlined } from '@ant-design/icons'
import apiClient from '../api/client'
import type { ApiResponse } from '../types'

const { Text } = Typography

interface SearchResult {
  projects?: Array<{
    id: string
    name: string
    status: string
    updated_at: string | null
  }>
  novels?: Array<{
    id: string
    title: string
    project_id: string
    project_name: string | null
  }>
  characters?: Array<{
    id: string
    name: string
    role_type: string
    project_id: string
    project_name: string | null
  }>
  scenes?: Array<{
    id: string
    location: string
    description: string | null
    chapter_id: string | null
  }>
  tasks?: Array<{
    id: string
    task_type: string
    status: string
    project_id: string | null
    progress: number
  }>
}

type ResultKey = keyof SearchResult

const taskStatusColor: Record<string, string> = {
  queued: 'default',
  running: 'processing',
  completed: 'success',
  failed: 'error',
  cancelled: 'warning',
}

function highlightText(text: string, keyword: string): React.ReactNode {
  if (!keyword.trim()) return text
  const escaped = keyword.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const parts = text.split(new RegExp(`(${escaped})`, 'gi'))
  return parts.map((part, i) =>
    part.toLowerCase() === keyword.toLowerCase()
      ? <span key={i} style={{ color: '#1890ff', fontWeight: 600 }}>{part}</span>
      : part
  )
}

export default function SearchBar() {
  const navigate = useNavigate()
  const inputRef = useRef<any>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const listRef = useRef<HTMLDivElement>(null)
  // 防抖定时器 + 请求序号：只接受最新一次搜索的响应
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const searchSeqRef = useRef(0)
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [results, setResults] = useState<SearchResult | null>(null)
  const [activeIndex, setActiveIndex] = useState(-1)

  // Ctrl+K 快捷键
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault()
        inputRef.current?.focus()
        setOpen(true)
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])

  // 点击外部关闭
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  // 卸载时取消未触发的防抖搜索
  useEffect(() => {
    return () => {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current)
        debounceRef.current = null
      }
    }
  }, [])

  // 构建扁平化结果列表用于键盘导航
  const getFlatItems = useCallback((): { type: ResultKey; item: any }[] => {
    if (!results) return []
    const items: { type: ResultKey; item: any }[] = []
    const keys: ResultKey[] = ['projects', 'novels', 'characters', 'scenes', 'tasks']
    for (const key of keys) {
      const list = results[key]
      if (list && list.length > 0) {
        items.push(...list.map((item: any) => ({ type: key, item })))
      }
    }
    return items
  }, [results])

  const flatItems = getFlatItems()

  const handleSearch = useCallback((value: string) => {
    setQuery(value)
    setActiveIndex(-1)
    if (debounceRef.current) {
      clearTimeout(debounceRef.current)
      debounceRef.current = null
    }
    // 序号递增后，之前发出的请求响应一律作废
    const seq = ++searchSeqRef.current
    if (!value.trim()) {
      setResults(null)
      setLoading(false)
      return
    }

    setLoading(true)
    debounceRef.current = setTimeout(async () => {
      try {
        const res: any = await apiClient.get<ApiResponse<SearchResult>>('/search', {
          params: { q: value, limit: 5 },
        })
        if (seq !== searchSeqRef.current) return
        setResults(res.data)
      } catch (e) {
        if (seq !== searchSeqRef.current) return
        console.error('搜索失败:', e)
      } finally {
        if (seq === searchSeqRef.current) {
          setLoading(false)
        }
      }
    }, 250)
  }, [])

  const handleResultClick = (type: string, item: any) => {
    setOpen(false)
    setQuery('')
    if (debounceRef.current) {
      clearTimeout(debounceRef.current)
      debounceRef.current = null
    }
    searchSeqRef.current += 1
    setResults(null)
    switch (type) {
      case 'projects':
        navigate(`/projects/${item.id}`)
        break
      case 'novels':
        navigate(`/projects/${item.project_id}/novels/${item.id}`)
        break
      case 'characters':
        navigate(`/projects/${item.project_id}/characters/${item.id}`)
        break
      case 'scenes':
        if (item.chapter_id) {
          navigate(`/projects/${item.project_id || ''}/storyboard`)
        }
        break
      case 'tasks':
        navigate('/tasks')
        break
    }
  }

  // 键盘导航
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!open || flatItems.length === 0) return

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault()
        setActiveIndex((prev) => (prev < flatItems.length - 1 ? prev + 1 : 0))
        break
      case 'ArrowUp':
        e.preventDefault()
        setActiveIndex((prev) => (prev > 0 ? prev - 1 : flatItems.length - 1))
        break
      case 'Enter':
        e.preventDefault()
        if (activeIndex >= 0 && activeIndex < flatItems.length) {
          const { type, item } = flatItems[activeIndex]
          handleResultClick(type, item)
        }
        break
      case 'Escape':
        e.preventDefault()
        setOpen(false)
        inputRef.current?.blur()
        break
    }
  }

  // 自动滚动到活动项
  useEffect(() => {
    if (activeIndex >= 0 && listRef.current) {
      const items = listRef.current.querySelectorAll('.search-result-item')
      if (items[activeIndex]) {
        items[activeIndex].scrollIntoView({ block: 'nearest' })
      }
    }
  }, [activeIndex])

  const hasResults = results && (
    (results.projects && results.projects.length > 0) ||
    (results.novels && results.novels.length > 0) ||
    (results.characters && results.characters.length > 0) ||
    (results.scenes && results.scenes.length > 0) ||
    (results.tasks && results.tasks.length > 0)
  )

  const resultCount = results
    ? Object.entries(results).reduce((sum, [, list]) => sum + (list?.length || 0), 0)
    : 0

  const renderModuleSection = (key: ResultKey, title: string, icon: React.ReactNode) => {
    const items = results?.[key]
    if (!items || items.length === 0) return null

    return (
      <div key={key}>
        <div style={{ padding: '8px 16px 4px', fontSize: 12, color: '#999' }}>
          {icon} {title}
        </div>
        <List
          dataSource={items}
          renderItem={(item: any, _idx: number) => {
            const globalIdx = flatItems.findIndex(
              (fi) => fi.type === key && fi.item.id === item.id
            )
            const isActive = globalIdx === activeIndex
            const displayName = item.name || item.title || item.location || item.task_type || item.id?.slice(0, 8)

            return (
              <List.Item
                className="search-result-item"
                style={{
                  cursor: 'pointer',
                  padding: '6px 16px',
                  background: isActive ? '#e6f7ff' : undefined,
                }}
                onMouseDown={() => handleResultClick(key, item)}
                onMouseEnter={() => setActiveIndex(globalIdx)}
              >
                <List.Item.Meta
                  title={
                    <Text style={{ fontSize: 14 }} ellipsis>
                      {highlightText(displayName, query)}
                    </Text>
                  }
                  description={
                    <Space size={4} wrap>
                      {key === 'projects' && (
                        <Tag color="blue" style={{ fontSize: 11, lineHeight: '18px' }}>
                          {item.status}
                        </Tag>
                      )}
                      {key === 'characters' && (
                        <Tag style={{ fontSize: 11, lineHeight: '18px' }}>
                          {item.role_type}
                        </Tag>
                      )}
                      {key === 'tasks' && (
                        <>
                          <Tag color={taskStatusColor[item.status] || 'default'} style={{ fontSize: 11, lineHeight: '18px' }}>
                            {item.status}
                          </Tag>
                          <Text type="secondary" style={{ fontSize: 12 }}>
                            进度 {item.progress}%
                          </Text>
                        </>
                      )}
                      {key === 'scenes' && item.description && (
                        <Text type="secondary" style={{ fontSize: 12 }} ellipsis>
                          {highlightText(item.description, query)}
                        </Text>
                      )}
                      {(key === 'novels' || key === 'characters') && item.project_name && (
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          {item.project_name}
                        </Text>
                      )}
                    </Space>
                  }
                />
              </List.Item>
            )
          }}
        />
      </div>
    )
  }

  return (
    <div ref={containerRef} style={{ position: 'relative', width: 320 }}>
      <Input
        ref={inputRef}
        placeholder="搜索项目、小说、人物... (Ctrl+K)"
        prefix={<SearchOutlined style={{ color: '#bfbfbf' }} />}
        value={query}
        onChange={(e) => handleSearch(e.target.value)}
        onFocus={() => setOpen(true)}
        onKeyDown={handleKeyDown}
        allowClear
        style={{ borderRadius: 6 }}
      />

      {open && (query || loading) && (
        <div
          ref={listRef}
          style={{
            position: 'absolute',
            top: '100%',
            left: 0,
            right: 0,
            marginTop: 4,
            background: '#fff',
            borderRadius: 8,
            boxShadow: '0 4px 12px rgba(0,0,0,0.12)',
            maxHeight: 480,
            overflow: 'auto',
            zIndex: 1050,
          }}
        >
          {loading ? (
            <div style={{ padding: 24, textAlign: 'center' }}>
              <Spin size="small" />
            </div>
          ) : hasResults ? (
            <div style={{ padding: '8px 0' }}>
              <div style={{ padding: '4px 16px 8px', borderBottom: '1px solid #f0f0f0' }}>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  找到 {resultCount} 条结果
                  {flatItems.length > 0 && activeIndex >= 0 && (
                    <span style={{ marginLeft: 8 }}>
                      ({activeIndex + 1}/{flatItems.length})
                    </span>
                  )}
                </Text>
              </div>
              {renderModuleSection('projects', '项目', <ProjectOutlined />)}
              {renderModuleSection('novels', '小说', <FileTextOutlined />)}
              {renderModuleSection('characters', '人物', <TeamOutlined />)}
              {renderModuleSection('scenes', '场景', <EnvironmentOutlined />)}
              {renderModuleSection('tasks', '任务', <CheckCircleOutlined />)}
            </div>
          ) : (
            <div style={{ padding: 24, textAlign: 'center' }}>
              <Empty description="未找到相关结果" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            </div>
          )}
        </div>
      )}
    </div>
  )
}
