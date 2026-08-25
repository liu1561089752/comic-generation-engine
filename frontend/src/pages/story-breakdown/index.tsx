import { useState } from 'react'
import { Card } from 'antd'
import { useNavigate } from 'react-router-dom'
import ProjectFilter from '../../components/common/ProjectFilter'
import EmptyState from '../../components/common/EmptyState'

/**
 * 剧情拆解（全局入口）：
 * 与小说管理一致——先提示选择项目，选择后直接跳转到对应项目的剧情拆解页。
 */
export default function StoryBreakdownLanding() {
  const navigate = useNavigate()
  const [projectId, setProjectId] = useState<string | undefined>(undefined)

  const handleProjectChange = (newProjectId: string | undefined) => {
    if (newProjectId) {
      navigate(`/projects/${newProjectId}/story-breakdown`, { replace: true })
    } else {
      setProjectId(undefined)
    }
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <h2 style={{ margin: 0, fontSize: 20, fontWeight: 600 }}>剧情拆解</h2>
      </div>

      <Card style={{ marginBottom: 16 }}>
        <ProjectFilter
          projectId={projectId}
          onProjectChange={handleProjectChange}
          showSearch={false}
        />
      </Card>

      {!projectId && (
        <EmptyState description="请先选择一个项目，进入该项目的剧情拆解" />
      )}
    </div>
  )
}
