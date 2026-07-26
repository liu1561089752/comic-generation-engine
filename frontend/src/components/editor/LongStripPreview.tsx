import React, { useEffect, useRef, useState, useCallback } from 'react'
import { Button, Tooltip, Slider } from 'antd'
import {
  CloseOutlined,
  ZoomInOutlined,
  ZoomOutOutlined,
  VerticalAlignBottomOutlined,
} from '@ant-design/icons'
import { useEditorStore } from '../../stores/editorStore'
import type { PanelInfo } from '../../stores/editorStore'

const CANVAS_WIDTH = 1080

interface LongStripPreviewProps {
  visible: boolean
  onClose: () => void
}

const LongStripPreview: React.FC<LongStripPreviewProps> = ({ visible, onClose }) => {
  const panels = useEditorStore((s) => s.panels)
  const [scale, setScale] = useState(0.4)
  const containerRef = useRef<HTMLDivElement>(null)

  // 计算总高度
  const totalHeight = panels.reduce((sum, p) => sum + p.height, 0) + (panels.length - 1) * 4
  const stripWidth = CANVAS_WIDTH * scale
  const stripHeight = totalHeight * scale

  // 键盘事件
  useEffect(() => {
    if (!visible) return
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [visible, onClose])

  const handleZoomIn = useCallback(() => {
    setScale((s) => Math.min(s + 0.1, 1.5))
  }, [])

  const handleZoomOut = useCallback(() => {
    setScale((s) => Math.max(s - 0.1, 0.1))
  }, [])

  const handleFitView = useCallback(() => {
    if (!containerRef.current) return
    const containerWidth = containerRef.current.clientWidth - 80
    const containerHeight = containerRef.current.clientHeight - 80
    const scaleX = containerWidth / CANVAS_WIDTH
    const scaleY = containerHeight / totalHeight
    setScale(Math.min(scaleX, scaleY, 0.8))
  }, [totalHeight])

  if (!visible) return null

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        background: 'rgba(0, 0, 0, 0.9)',
        zIndex: 1000,
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {/* 顶部控制栏 */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '12px 24px',
          background: '#1a1a2e',
          borderBottom: '1px solid #333',
        }}
      >
        <span style={{ color: '#fff', fontWeight: 600, fontSize: 16 }}>长图预览</span>

        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <Tooltip title="缩小">
            <Button
              icon={<ZoomOutOutlined />}
              onClick={handleZoomOut}
              size="small"
              style={{ color: '#fff', background: 'transparent', borderColor: '#555' }}
            />
          </Tooltip>

          <span style={{ color: '#fff', fontSize: 13, minWidth: 40, textAlign: 'center' }}>
            {Math.round(scale * 100)}%
          </span>

          <Tooltip title="放大">
            <Button
              icon={<ZoomInOutlined />}
              onClick={handleZoomIn}
              size="small"
              style={{ color: '#fff', background: 'transparent', borderColor: '#555' }}
            />
          </Tooltip>

          <Slider
            min={10}
            max={150}
            value={Math.round(scale * 100)}
            onChange={(v) => setScale(v / 100)}
            style={{ width: 120, margin: '0 8px' }}
            trackStyle={{ background: '#6C5CE7' }}
            handleStyle={{ borderColor: '#6C5CE7' }}
          />

          <Tooltip title="适应视图">
            <Button
              icon={<VerticalAlignBottomOutlined />}
              onClick={handleFitView}
              size="small"
              style={{ color: '#fff', background: 'transparent', borderColor: '#555' }}
            />
          </Tooltip>

          <div style={{ width: 1, height: 20, background: '#444', margin: '0 8px' }} />

          <Tooltip title="关闭 (ESC)">
            <Button
              icon={<CloseOutlined />}
              onClick={onClose}
              style={{ color: '#fff', background: 'transparent', borderColor: '#555' }}
            />
          </Tooltip>
        </div>
      </div>

      {/* 预览区域 */}
      <div
        ref={containerRef}
        style={{
          flex: 1,
          overflow: 'auto',
          display: 'flex',
          justifyContent: 'center',
          padding: 24,
        }}
      >
        <div
          style={{
            width: stripWidth,
            minHeight: stripHeight,
            position: 'relative',
            alignSelf: 'flex-start',
          }}
        >
          {panels.map((panel, index) => (
            <PanelPreview
              key={panel.id}
              panel={panel}
              scale={scale}
              offsetY={panels.slice(0, index).reduce((sum, p) => sum + p.height + 4, 0) * scale}
            />
          ))}
        </div>
      </div>
    </div>
  )
}

const PanelPreview: React.FC<{
  panel: PanelInfo
  scale: number
  offsetY: number
}> = ({ panel, scale, offsetY }) => {
  const imgRef = useRef<HTMLImageElement | null>(null)
  const [loaded, setLoaded] = useState(false)

  useEffect(() => {
    if (!panel.image_url) {
      setLoaded(false)
      return
    }
    const img = new window.Image()
    img.crossOrigin = 'anonymous'
    img.onload = () => {
      imgRef.current = img
      setLoaded(true)
    }
    img.onerror = () => setLoaded(false)
    img.src = panel.image_url
  }, [panel.image_url])

  const w = panel.width * scale
  const h = panel.height * scale

  return (
    <div
      style={{
        position: 'absolute',
        top: offsetY,
        left: 0,
        width: w,
        height: h,
        background: '#2a2a4e',
        borderRadius: 2,
        overflow: 'hidden',
        border: '1px solid #444',
      }}
    >
      {loaded && imgRef.current ? (
        <img
          src={panel.image_url}
          alt={`Panel ${panel.panel_number}`}
          style={{ width: '100%', height: '100%', objectFit: 'cover' }}
        />
      ) : (
        <div
          style={{
            width: '100%',
            height: '100%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#666',
            fontSize: 14,
          }}
        >
          Panel {panel.panel_number}
        </div>
      )}
    </div>
  )
}

export default LongStripPreview
