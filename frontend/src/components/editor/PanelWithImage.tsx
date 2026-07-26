import React from 'react'
import { Group, Rect, Text } from 'react-konva'
import type { PanelInfo } from '../../stores/editorStore'
import { useImageLoader } from './useImageLoader'

const DASHED_STROKE = [8, 4]

interface Props {
  panel: PanelInfo
  isSelected: boolean
  tool: 'select' | 'drag'
  hidden: boolean
  locked: boolean
  onSelect: () => void
  onDragEnd: (x: number, y: number) => void
}

export const PanelWithImage: React.FC<Props> = ({
  panel,
  isSelected,
  tool,
  hidden,
  locked,
  onSelect,
  onDragEnd,
}) => {
  const { image } = useImageLoader(panel.image_url)

  if (hidden) return null

  return (
    <Group
      x={panel.x}
      y={panel.y}
      onClick={onSelect}
      onTap={onSelect}
      draggable={tool === 'drag' && !locked}
      onDragEnd={(e) => {
        onDragEnd(e.target.x(), e.target.y())
      }}
    >
      {/* Group 的 x/y 已经是 panel 的绝对坐标，子元素一律用相对坐标 */}
      <Rect
        x={0}
        y={0}
        width={panel.width}
        height={panel.height}
        fill={image ? undefined : '#2a2a4e'}
        stroke={isSelected ? '#6C5CE7' : '#404060'}
        strokeWidth={2}
        dash={isSelected ? undefined : DASHED_STROKE}
      />

      {image && (
        <React.Fragment>
          <Rect
            x={0}
            y={0}
            width={panel.width}
            height={panel.height}
            fillPatternImage={image}
            fillPatternOffsetX={0}
            fillPatternOffsetY={0}
            fillPatternScale={{ x: panel.width / image.width, y: panel.height / image.height }}
          />
          {isSelected && (
            <Rect
              x={0}
              y={0}
              width={panel.width}
              height={panel.height}
              stroke="#6C5CE7"
              strokeWidth={3}
              listening={false}
            />
          )}
        </React.Fragment>
      )}

      {!image && (
        <Text
          x={0}
          y={panel.height / 2 - 14}
          width={panel.width}
          text={`Panel ${panel.panel_number}`}
          fontSize={24}
          fill="#666"
          align="center"
        />
      )}
    </Group>
  )
}

export default PanelWithImage
