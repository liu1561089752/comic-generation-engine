import { Spin } from 'antd'

interface LoadingProps {
  tip?: string
  fullScreen?: boolean
}

export default function Loading({ tip = '加载中...', fullScreen = false }: LoadingProps) {
  if (fullScreen) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Spin tip={tip} size="large">
          <div className="p-12" />
        </Spin>
      </div>
    )
  }

  return (
    <div className="flex items-center justify-center py-20">
      <Spin tip={tip} size="large">
        <div className="p-8" />
      </Spin>
    </div>
  )
}
