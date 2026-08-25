import { useEffect, useState } from 'react'
import { Table, Button, Tag, Card, message, Space, Modal } from 'antd'
import { PlusOutlined, ReloadOutlined } from '@ant-design/icons'
import { useNavigate, useParams } from 'react-router-dom'
import { useNovelStore } from '../../stores/novelStore'
import { novelApi } from '../../api/novelApi'
import { formatDate, formatWordCount } from '../../utils/format'
import NovelUploadModal from '../../components/NovelUploadModal'
import ProjectFilter from '../../components/common/ProjectFilter'
import EmptyState from '../../components/common/EmptyState'
import Loading from '../../components/common/Loading'
import type { Novel } from '../../types/novel'

export default function NovelList() {
  const navigate = useNavigate()
  const { id: urlProjectId } = useParams<{ id: string }>()
  const [modalOpen, setModalOpen] = useState(false)

  const {
    novels,
    loading,
    uploading,
    uploadProgress,
    fetchNovels,
    uploadNovel,
  } = useNovelStore()

  // urlProjectId 存在 → 项目模式；否则 → 全局模式
  const isGlobalMode = !urlProjectId
  const [selectedProjectId, setSelectedProjectId] = useState<string | undefined>(urlProjectId)

  // 项目模式：监听 URL 参数变化
  useEffect(() => {
    setSelectedProjectId(urlProjectId)
  }, [urlProjectId])

  useEffect(() => {
    if (selectedProjectId) {
      fetchNovels(selectedProjectId)
    }
  }, [selectedProjectId, fetchNovels])

  const handleProjectChange = (projectId: string | undefined) => {
    if (projectId) {
      navigate(`/projects/${projectId}/novels`, { replace: true })
    }
    // 全局模式清空选择时，不清除 selectedProjectId 以避免重复请求
    // 用户可通过重新选择项目来加载数据
  }

  const handleUpload = async (file: File, title?: string) => {
    if (!selectedProjectId) {
      message.error('请先选择项目')
      return
    }
    if (novels.length > 0) {
      message.warning('每个项目仅允许上传一本小说')
      return
    }
    try {
      await uploadNovel(selectedProjectId, file, title)
      message.success('小说上传成功')
      setModalOpen(false)
      fetchNovels(selectedProjectId)
    } catch {
      message.error('上传失败')
    }
  }

  const columns = [
    {
      title: '小说标题',
      dataIndex: 'title',
      key: 'title',
      render: (title: string, record: Novel) => (
        <Button
          type="link"
          onClick={() => navigate(`/projects/${selectedProjectId}/novels/${record.id}`)}
          style={{ padding: 0 }}
        >
          {title}
        </Button>
      ),
    },
    {
      title: '作者',
      dataIndex: 'author',
      key: 'author',
      width: 150,
      render: (author?: string) => author || '-',
    },
    {
      title: '字数',
      dataIndex: 'word_count',
      key: 'word_count',
      width: 100,
      render: (count: number) => formatWordCount(count),
    },
    {
      title: '格式',
      dataIndex: 'format',
      key: 'format',
      width: 80,
      render: (format: string) => <Tag>{format}</Tag>,
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (date: string) => formatDate(date),
    },
    {
      title: '操作',
      key: 'action',
      width: 80,
      render: (_: any, record: Novel) => (
        <Button type="link" danger size="small" onClick={() => handleDelete(record)}>
          删除
        </Button>
      ),
    },
  ]

  const handleDelete = (record: Novel) => {
    if (!selectedProjectId) return
    Modal.confirm({
      title: `确认删除「${record.title}」？`,
      content: '将删除该小说及其全部下游数据（章节/脚本/分镜/排版/生成的图片），且每项目仅允许一本小说，删除后需重新上传。此操作不可撤销。',
      okText: '确认删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        try {
          await novelApi.remove(selectedProjectId, record.id)
          message.success('小说已删除')
          fetchNovels(selectedProjectId)
        } catch {
          message.error('删除失败')
        }
      },
    })
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <h2 style={{ margin: 0, fontSize: 20, fontWeight: 600 }}>小说管理</h2>
        {selectedProjectId && (
          <Space>
            <Button
              icon={<ReloadOutlined />}
              onClick={() => fetchNovels(selectedProjectId!)}
            >
              刷新
            </Button>
            {novels.length === 0 && (
              <Button
                type="primary"
                icon={<PlusOutlined />}
                onClick={() => setModalOpen(true)}
              >
                导入小说
              </Button>
            )}
          </Space>
        )}
      </div>

      <Card style={{ marginBottom: 16 }}>
        <ProjectFilter
          projectId={selectedProjectId}
          onProjectChange={handleProjectChange}
          showSearch={false}
          extra={
            isGlobalMode && selectedProjectId && novels.length === 0 ? (
              <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>
                导入小说
              </Button>
            ) : undefined
          }
        />
      </Card>

      {!selectedProjectId ? (
        <EmptyState description="请先在顶部选择一个项目" />
      ) : loading ? (
        <Loading tip="加载小说列表..." />
      ) : novels.length === 0 ? (
        <EmptyState
          description="暂无小说，请先导入小说文件"
          actionText="导入小说"
          onAction={() => setModalOpen(true)}
        />
      ) : (
        <Table
          dataSource={novels}
          columns={columns}
          rowKey="id"
          pagination={{ showSizeChanger: true, pageSize: 10 }}
        />
      )}

      <NovelUploadModal
        open={modalOpen}
        uploading={uploading}
        uploadProgress={uploadProgress}
        onCancel={() => setModalOpen(false)}
        onFileSelect={handleUpload}
      />
    </div>
  )
}
