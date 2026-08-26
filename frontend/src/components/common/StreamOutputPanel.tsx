import { useEffect, useRef } from 'react'

/**
 * 流式输出面板：AI 任务运行时实时显示生成内容（打字机效果）。
 *
 * 配合后端任务 stream_output（轮询接口增量返回）与 useTaskProgress.streamText 使用。
 * 文本更新时自动滚动到底部。
 */
interface StreamOutputPanelProps {
  /** 是否显示（任务 running 且已有内容时） */
  visible: boolean
  /** 已拼接的流式文本 */
  streamText: string
  /** 面板标题文案 */
  title?: string
  /** 面板最大高度（px） */
  maxHeight?: number
}

export default function StreamOutputPanel({
  visible,
  streamText,
  title = 'AI 正在生成内容（流式输出）...',
  maxHeight = 260,
}: StreamOutputPanelProps) {
  const boxRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    if (boxRef.current) {
      boxRef.current.scrollTop = boxRef.current.scrollHeight
    }
  }, [streamText])

  if (!visible || !streamText) return null

  return (
    <div
      ref={boxRef}
      style={{
        marginBottom: 16,
        padding: '12px 16px',
        background: '#f6f8fa',
        borderRadius: 8,
        border: '1px solid #d9d9d9',
        maxHeight,
        overflow: 'auto',
      }}
    >
      <div style={{ fontSize: 12, color: '#888', marginBottom: 6 }}>{title}</div>
      <pre
        style={{
          margin: 0,
          fontSize: 13,
          lineHeight: 1.6,
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-all',
          fontFamily: 'inherit',
          color: '#333',
        }}
      >
        {streamText}
        <span style={{ color: '#1677ff' }}>▍</span>
      </pre>
    </div>
  )
}
