import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { Spin, Empty } from 'antd'
import { novelApi } from '../../api/novelApi'
import StoryBreakdownDetail from './detail'

/**
 * 剧情拆解（项目级入口，不再经过小说选择过渡页）。
 * 每项目仅允许一本小说：自动获取该项目的小说，直接进入剧情拆解详情。
 */
export default function ProjectStoryBreakdown() {
  const { id: projectId } = useParams<{ id: string }>()
  const [novelId, setNovelId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!projectId) return
    setLoading(true)
    novelApi.list(projectId).then((res: any) => {
      const items = res.data?.items || []
      setNovelId(items[0]?.id || null)
    }).catch(() => {
      setNovelId(null)
    }).finally(() => setLoading(false))
  }, [projectId])

  if (!projectId) {
    return <Empty description="请先选择一个项目" />
  }

  if (loading) {
    return <Spin style={{ display: 'block', margin: '60px auto' }} tip="加载小说..." />
  }

  if (!novelId) {
    return <Empty description="该项目暂无小说，请先导入小说" />
  }

  return <StoryBreakdownDetail projectId={projectId} novelId={novelId} />
}
