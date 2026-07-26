import React, { useCallback, useRef } from 'react'
import { Typography, Divider, Button, Tooltip } from 'antd'
import {
  EyeOutlined,
  EyeInvisibleOutlined,
  LockOutlined,
  UnlockOutlined,
  DragOutlined,
  PictureOutlined,
  CommentOutlined,
} from '@ant-design/icons'
import { useEditorStore } from '../../stores/editorStore'
import type { BubbleData } from '../../stores/editorStore'

const { Text: AntText } = Typography

interface LayerItem {
  id: string
  type: 'panel' | 'bubble'
  label: string
  bubbleType?: BubbleData['type']
  panelNumber?: number
}

const LayerPanel: React.FC = () => {
  const panels = useEditorStore((s) => s.panels)
  const bubbles = useEditorStore((s) => s.bubbles)
  const selectedPanelId = useEditorStore((s) => s.selectedPanelId)
  const selectedBubbleId = useEditorStore((s) => s.selectedBubbleId)
  const hiddenLayerIds = useEditorStore((s) => s.hiddenLayerIds)
  const lockedLayerIds = useEditorStore((s) => s.lockedLayerIds)
  const setSelectedPanelId = useEditorStore((s) => s.setSelectedPanelId)
  const setSelectedBubbleId = useEditorStore((s) => s.setSelectedBubbleId)
  const toggleLayerVisibility = useEditorStore((s) => s.toggleLayerVisibility)
  const toggleLayerLock = useEditorStore((s) => s.toggleLayerLock)
  const reorderLayer = useEditorStore((s) => s.reorderLayer)

  const dragItemRef = useRef<number | null>(null)
  const dragOverRef = useRef<number | null>(null)

  // 构建层列表：先 panels 再 bubbles
  const layers: LayerItem[] = [
    ...panels.map((p) => ({
      id: p.id,
      type: 'panel' as const,
      label: `Panel ${p.panel_number}`,
      panelNumber: p.panel_number,
    })),
    ...bubbles.map((b) => ({
      id: b.id,
      type: 'bubble' as const,
      label: getBubbleLabel(b),
      bubbleType: b.type,
    })),
  ]

  const isSelected = (id: string, type: string) => {
    if (type === 'panel') return selectedPanelId === id
    return selectedBubbleId === id
  }

  const handleSelect = (item: LayerItem) => {
    if (lockedLayerIds.includes(item.id)) return
    if (item.type === 'panel') {
      setSelectedPanelId(item.id)
    } else {
      setSelectedBubbleId(item.id)
    }
  }

  const handleDragStart = (index: number) => {
    dragItemRef.current = index
  }

  const handleDragOver = (index: number) => {
    dragOverRef.current = index
  }

  const handleDrop = useCallback(() => {
    const from = dragItemRef.current
    const to = dragOverRef.current
    if (from !== null && to !== null && from !== to) {
      reorderLayer(from, to)
    }
    dragItemRef.current = null
    dragOverRef.current = null
  }, [reorderLayer])

  return (
    <div>
      <AntText strong style={{ fontSize: 15 }}>图层管理</AntText>
      <Divider style={{ margin: '12px 0' }} />

      <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        {layers.map((item, index) => {
          const hidden = hiddenLayerIds.includes(item.id)
          const locked = lockedLayerIds.includes(item.id)
          const selected = isSelected(item.id, item.type)

          return (
            <div
              key={item.id}
              draggable
              onDragStart={() => handleDragStart(index)}
              onDragOver={(e) => {
                e.preventDefault()
                handleDragOver(index)
              }}
              onDrop={handleDrop}
              onClick={() => handleSelect(item)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                padding: '6px 8px',
                borderRadius: 6,
                cursor: locked ? 'not-allowed' : 'pointer',
                background: selected ? '#e6f7ff' : 'transparent',
                border: selected ? '1px solid #91d5ff' : '1px solid transparent',
                transition: 'all 0.2s',
                opacity: hidden ? 0.4 : 1,
              }}
              onMouseEnter={(e) => {
                if (!selected) {
                  e.currentTarget.style.background = '#f5f5f5'
                }
              }}
              onMouseLeave={(e) => {
                if (!selected) {
                  e.currentTarget.style.background = 'transparent'
                }
              }}
            >
              {/* 拖拽手柄 */}
              <DragOutlined style={{ color: '#bbb', cursor: 'grab', fontSize: 12 }} />

              {/* 类型图标 */}
              {item.type === 'panel' ? (
                <PictureOutlined style={{ color: '#6C5CE7', fontSize: 14 }} />
              ) : (
                <CommentOutlined
                  style={{
                    color:
                      item.bubbleType === 'narration'
                        ? '#999'
                        : item.bubbleType === 'thinking'
                          ? '#1890ff'
                          : '#52c41a',
                    fontSize: 14,
                  }}
                />
              )}

              {/* 标签 */}
              <span style={{ flex: 1, fontSize: 13, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {item.label}
              </span>

              {/* 显隐切换 */}
              <Tooltip title={hidden ? '显示' : '隐藏'}>
                <Button
                  type="text"
                  size="small"
                  icon={hidden ? <EyeInvisibleOutlined /> : <EyeOutlined />}
                  onClick={(e) => {
                    e.stopPropagation()
                    toggleLayerVisibility(item.id)
                  }}
                  style={{ color: hidden ? '#999' : '#666', fontSize: 12 }}
                />
              </Tooltip>

              {/* 锁定切换 */}
              <Tooltip title={locked ? '解锁' : '锁定'}>
                <Button
                  type="text"
                  size="small"
                  icon={locked ? <LockOutlined /> : <UnlockOutlined />}
                  onClick={(e) => {
                    e.stopPropagation()
                    toggleLayerLock(item.id)
                  }}
                  style={{ color: locked ? '#ff4d4f' : '#666', fontSize: 12 }}
                />
              </Tooltip>
            </div>
          )
        })}
      </div>

      {layers.length === 0 && (
        <div style={{ textAlign: 'center', padding: '20px 0', color: '#999', fontSize: 13 }}>
          暂无图层
        </div>
      )}
    </div>
  )
}

function getBubbleLabel(bubble: BubbleData): string {
  const typeMap: Record<string, string> = {
    narration: '旁白',
    dialogue: '对话',
    thinking: '内心独白',
  }
  const label = typeMap[bubble.type] || bubble.type
  const textPreview = bubble.text.length > 10 ? bubble.text.slice(0, 10) + '...' : bubble.text
  return `${label}: ${textPreview}`
}

export default LayerPanel
