import { useEffect, useState } from 'react'
import { Button, Space, message } from 'antd'
import { RobotOutlined } from '@ant-design/icons'
import { useParams } from 'react-router-dom'
import { useWorldStore } from '../../stores/worldStore'
import { useMultiTaskProgress } from '../../hooks/useMultiTaskProgress'
import EmptyState from '../../components/common/EmptyState'
import Loading from '../../components/common/Loading'
import WorldDetail from './[id]'

/**
 * 世界观管理页（每项目仅允许一个世界观）：
 * - 无世界观：显示空状态 + AI辅助创建入口
 * - 已有世界观：直接渲染世界观详情（含场景/道具/建筑/服装 Tab）
 */
export default function WorldList() {
  const { id: urlProjectId } = useParams<{ id: string }>()
  const [projectId, setProjectId] = useState<string | undefined>(urlProjectId)
  const { worlds, loading, fetchWorlds, aiCreateWorld } = useWorldStore()

  const [aiLoading, setAiLoading] = useState(false)

  // AI 创建世界观任务（纳入任务中心管理）
  const taskProgress = useMultiTaskProgress({
    projectId,
    onTaskCompleted: (taskId) => {
      if (!projectId) return
      const output = taskProgress.getTask(taskId)?.outputData
      if (output?.name) {
        message.success(`世界观「${output.name}」创建成功`)
      } else {
        message.success('AI 创建世界观完成')
      }
      fetchWorlds(projectId)
    },
    onTaskFailed: (_taskId, error) => {
      message.error(error || 'AI 创建世界观失败')
    },
  })

  useEffect(() => {
    setProjectId(urlProjectId)
  }, [urlProjectId])

  useEffect(() => {
    if (projectId) {
      fetchWorlds(projectId)
    }
  }, [projectId, fetchWorlds])

  const handleAiCreate = async () => {
    if (!projectId) return
    setAiLoading(true)
    try {
      // 获取项目小说文本
      const novelRes: any = await import('../../api/novelApi').then(m => m.novelApi.list(projectId))
      const novels = novelRes?.data?.items || []
      if (!novels || novels.length === 0) {
        message.warning('当前项目没有小说，请先上传小说')
        return
      }
      const firstNovel = novels[0]
      let novelText = firstNovel.cleaned_text || firstNovel.raw_text
      if (!novelText) {
        // 列表接口未返回文本内容，获取详情
        const detailRes: any = await import('../../api/novelApi').then(m => m.novelApi.getById(projectId, firstNovel.id))
        const detail = detailRes?.data
        novelText = detail?.cleaned_text || detail?.raw_text
        if (!novelText) {
          message.warning('小说内容为空')
          return
        }
      }

      const taskId = await aiCreateWorld(projectId, novelText)
      if (taskId) {
        taskProgress.startPolling(taskId)
        message.info('AI 创建世界观任务已提交，可在任务中心查看进度')
      }
    } catch {
      message.error('AI创建世界观失败')
    } finally {
      setAiLoading(false)
    }
  }

  if (!projectId) {
    return <EmptyState description="请先选择一个项目" />
  }

  // 每项目仅允许一个世界观，取列表第一个即为当前世界观
  const currentWorld = worlds[0]

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <h2 style={{ margin: 0, fontSize: 20, fontWeight: 600 }}>世界观管理</h2>
        <Space>
          <Button icon={<RobotOutlined />} loading={aiLoading} onClick={handleAiCreate}>
            AI辅助创建
          </Button>
        </Space>
      </div>

      {loading && !currentWorld ? (
        <Loading tip="加载世界观..." />
      ) : currentWorld ? (
        <WorldDetail
          projectId={projectId}
          worldId={currentWorld.id}
          onDeleted={() => fetchWorlds(projectId)}
        />
      ) : (
        <EmptyState
          description="暂无世界观，点击「AI辅助创建」从小说文本生成世界观"
          actionText="AI辅助创建"
          onAction={handleAiCreate}
        />
      )}
    </div>
  )
}
