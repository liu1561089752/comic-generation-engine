import type { StreamSection } from '../../hooks/useTaskProgress'

/**
 * 流式输出面板：AI 任务运行时显示实时生成的内容。
 *
 * 配合后端任务 stream_output（JSONL 多流，按 key 分组）与
 * useTaskProgress.streamSections 使用。多流并行（如分镜多章并行）时
 * 每个分块渲染一个小节（带章节标题）；单流任务只有一个分块。
 * 仅在有内容时渲染（无内容时返回 null，页面上不出现任何东西）。
 */
interface StreamOutputPanelProps {
  /** 是否显示（任务 running 且已有内容时） */
  visible: boolean
  /** 流式输出分块（按 key 分组后的章节/批次） */
  sections: StreamSection[]
  /** 面板标题文案 */
  title?: string
  /** 面板最大高度（px），超出后可手动滚动 */
  maxHeight?: number
}

export default function StreamOutputPanel({
  visible,
  sections,
  title = 'AI 正在生成内容（流式输出）...',
  maxHeight = 300,
}: StreamOutputPanelProps) {
  if (!visible || sections.length === 0) return null

  return (
    <div
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
      {sections.map(sec => (
        <div key={sec.key ?? 'main'} style={{ marginBottom: sections.length > 1 ? 14 : 0 }}>
          {sec.title && (
            <div style={{ fontWeight: 600, color: '#555', fontSize: 12, marginBottom: 4 }}>
              {sec.title}
            </div>
          )}
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
            {sec.text}
          </pre>
        </div>
      ))}
    </div>
  )
}
