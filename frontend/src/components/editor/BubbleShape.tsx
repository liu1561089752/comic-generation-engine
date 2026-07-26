import React, { useEffect, useRef } from 'react'
import { Group, Rect, Text, Ellipse, Transformer } from 'react-konva'
import type { BubbleData } from '../../stores/editorStore'

interface Props {
  bubble: BubbleData
  isSelected: boolean
  tool: 'select' | 'drag'
  hidden: boolean
  locked: boolean
  onSelect: () => void
  onDragEnd: (x: number, y: number) => void
  onResize?: (id: string, width: number, height: number, x: number, y: number) => void
}

export const BubbleShape: React.FC<Props> = ({
  bubble,
  isSelected,
  tool,
  hidden,
  locked,
  onSelect,
  onDragEnd,
  onResize,
}) => {
  const shapeRef = useRef<any>(null)
  const trRef = useRef<any>(null)

  if (hidden) return null

  const bubbleStyles: Record<string, { fill: string; stroke: string; dash?: number[] }> = {
    narration: { fill: '#f0f0f0', stroke: '#999' },
    dialogue: { fill: '#ffffff', stroke: '#52c41a' },
    thinking: { fill: '#e8f4fd', stroke: '#1890ff', dash: [6, 3] },
  }

  const style = bubbleStyles[bubble.type] || bubbleStyles.dialogue
  const fontSize = bubble.fontSize || 14
  const textColor = bubble.color || '#333'

  useEffect(() => {
    if (isSelected && trRef.current && shapeRef.current) {
      trRef.current.nodes([shapeRef.current])
      trRef.current.getLayer()?.batchDraw()
    }
  }, [isSelected])

  const handleTransformEnd = () => {
    if (!shapeRef.current) return
    const node = shapeRef.current
    const scaleX = node.scaleX()
    const scaleY = node.scaleY()
    const newWidth = Math.max(60, node.width() * scaleX)
    const newHeight = Math.max(40, node.height() * scaleY)
    node.scaleX(1)
    node.scaleY(1)
    // 从 top-left / top-right / bottom-left 锚点缩放会同时改变节点坐标，必须一起写回 store
    // thinking 用 Ellipse 渲染，节点 x/y 是中心点，要换算回左上角
    const isEllipse = bubble.type === 'thinking'
    const newX = isEllipse ? node.x() - newWidth / 2 : node.x()
    const newY = isEllipse ? node.y() - newHeight / 2 : node.y()
    if (onResize) {
      onResize(bubble.id, newWidth, newHeight, newX, newY)
    }
  }

  const renderShape = () => {
    const commonProps = {
      ref: shapeRef,
      draggable: tool === 'drag' && !locked,
      onClick: onSelect,
      onTap: onSelect,
      onDragEnd: (e: any) => {
        onDragEnd(e.target.x(), e.target.y())
      },
      name: `bubble-${bubble.id}`,
    }

    switch (bubble.type) {
      case 'narration':
        return (
          <Rect
            {...commonProps}
            x={bubble.x}
            y={bubble.y}
            width={bubble.width}
            height={bubble.height}
            fill={style.fill}
            stroke={isSelected ? '#6C5CE7' : style.stroke}
            strokeWidth={isSelected ? 2.5 : 1.5}
            cornerRadius={8}
          />
        )
      case 'dialogue':
        return (
          <React.Fragment>
            <Rect
              {...commonProps}
              x={bubble.x}
              y={bubble.y}
              width={bubble.width}
              height={bubble.height}
              fill={style.fill}
              stroke={isSelected ? '#6C5CE7' : style.stroke}
              strokeWidth={isSelected ? 2.5 : 1.5}
              cornerRadius={16}
            />
            <Text
              x={bubble.x + bubble.width - 20}
              y={bubble.y + bubble.height - 8}
              text="▼"
              fontSize={16}
              fill={style.fill}
              stroke={isSelected ? '#6C5CE7' : style.stroke}
              strokeWidth={1}
              listening={false}
            />
          </React.Fragment>
        )
      case 'thinking':
        return (
          <Ellipse
            {...commonProps}
            // Ellipse 的 x/y 是中心点，落点要换算回左上角再写回 store
            onDragEnd={(e: any) => {
              onDragEnd(e.target.x() - bubble.width / 2, e.target.y() - bubble.height / 2)
            }}
            x={bubble.x + bubble.width / 2}
            y={bubble.y + bubble.height / 2}
            radiusX={bubble.width / 2}
            radiusY={bubble.height / 2}
            fill={style.fill}
            stroke={isSelected ? '#6C5CE7' : style.stroke}
            strokeWidth={isSelected ? 2.5 : 1.5}
            dash={style.dash}
          />
        )
      default:
        return null
    }
  }

  return (
    <React.Fragment>
      <Group>
        {renderShape()}
        <Text
          x={bubble.x + 10}
          y={bubble.y + 10}
          width={bubble.width - 20}
          height={bubble.height - 20}
          text={bubble.text}
          fontSize={fontSize}
          fill={textColor}
          fontFamily={bubble.fontFamily || 'sans-serif'}
          align="left"
          verticalAlign="middle"
          wrap="word"
        />
      </Group>
      {isSelected && (
        <Transformer
          ref={trRef}
          rotateEnabled={true}
          keepRatio={false}
          enabledAnchors={['top-left', 'top-right', 'bottom-left', 'bottom-right']}
          boundBoxFunc={(oldBox, newBox) => {
            if (newBox.width < 60 || newBox.height < 40) return oldBox
            return newBox
          }}
          onTransformEnd={handleTransformEnd}
        />
      )}
    </React.Fragment>
  )
}

export default BubbleShape
