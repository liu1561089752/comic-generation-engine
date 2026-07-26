import { useEffect, useRef, useState } from 'react'
import { Select, Input, Space } from 'antd'
import { SearchOutlined } from '@ant-design/icons'
import { projectApi } from '../../api/projectApi'
import type { Project } from '../../types/project'

interface ProjectFilterProps {
  projectId?: string
  onProjectChange?: (projectId: string | undefined) => void
  searchPlaceholder?: string
  searchValue?: string
  onSearchChange?: (value: string) => void
  showSearch?: boolean
  extra?: React.ReactNode
}

export default function ProjectFilter(props: ProjectFilterProps) {
  const {
    projectId,
    onProjectChange,
    searchPlaceholder = '搜索...',
    searchValue,
    onSearchChange,
    showSearch = true,
    extra,
  } = props

  const [projects, setProjects] = useState<Project[]>([])
  const [loading, setLoading] = useState(false)
  const debounceRef = useRef<ReturnType<typeof setTimeout>>()

  useEffect(() => {
    setLoading(true)
    projectApi
      .list({ page_size: 999 })
      .then((res: any) => {
        const list = res.data?.items || res.data || []
        setProjects(Array.isArray(list) ? list : [])
      })
      .catch(() => {
        setProjects([])
      })
      .finally(() => {
        setLoading(false)
      })
  }, [])

  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value
    if (debounceRef.current) {
      clearTimeout(debounceRef.current)
    }
    debounceRef.current = setTimeout(() => {
      onSearchChange?.(value)
    }, 300)
  }

  const handleProjectSelect = (value: string | undefined) => {
    onProjectChange?.(value || undefined)
  }

  return (
    <Space size="middle" wrap>
      <Select
        placeholder="全部项目"
        style={{ minWidth: 200 }}
        allowClear
        loading={loading}
        value={projectId}
        onChange={handleProjectSelect}
        options={[
          { label: '全部项目', value: '' },
          ...projects.map((p) => ({
            label: p.name,
            value: p.id,
          })),
        ]}
      />
      {showSearch && (
        <Input
          placeholder={searchPlaceholder}
          prefix={<SearchOutlined />}
          allowClear
          defaultValue={searchValue}
          onChange={handleSearchChange}
          style={{ width: 250 }}
        />
      )}
      {extra}
    </Space>
  )
}
