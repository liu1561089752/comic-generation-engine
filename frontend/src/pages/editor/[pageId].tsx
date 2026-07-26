import React, { useRef, useEffect, useState, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Stage, Layer, Rect } from 'react-konva'
import { Layout, message } from 'antd'
import { useEditorStore } from '../../stores/editorStore'
import type { PanelInfo, BubbleData, CandidateImage } from '../../stores/editorStore'
import apiClient from '../../api/client'
import PageThumbnails from '../../components/editor/PageThumbnails'
import LongStripPreview from '../../components/editor/LongStripPreview'
import EditorToolbar from '../../components/editor/EditorToolbar'
import PropertiesPanel from '../../components/editor/PropertiesPanel'
import ImageReplaceModal from '../../components/editor/ImageReplaceModal'
import { PanelWithImage } from '../../components/editor/PanelWithImage'
import { BubbleShape } from '../../components/editor/BubbleShape'

const { Sider, Content } = Layout

const CANVAS_WIDTH = 1080
const CANVAS_HEIGHT = 1440

const ComicEditor: React.FC = () => {
  const { id: projectId, pageId } = useParams<{ id: string; pageId: string }>()
  const navigate = useNavigate()
  const {
    panels,
    bubbles,
    selectedPanelId,
    setSelectedPanelId,
    selectedBubbleId,
    setSelectedBubbleId,
    stageScale,
    setStageScale,
    tool,
    setTool,
    hiddenLayerIds,
    lockedLayerIds,
    isDirty,
    undo,
    redo,
    save,
    updateBubble,
    removeBubble,
    addBubble,
    replacePanelImage,
    candidateImages,
    setCandidateImages,
    loadPageData,
    setPages,
    setCurrentPage,
  } = useEditorStore()

  const containerRef = useRef<HTMLDivElement>(null)
  const [stagePosition, setStagePosition] = useState({ x: 0, y: 0 })
  const [selectedInfo, setSelectedInfo] = useState<PanelInfo | null>(null)
  const [selectedBubbleInfo, setSelectedBubbleInfo] = useState<BubbleData | null>(null)
  const [longStripVisible, setLongStripVisible] = useState(false)
  const [imageReplaceModalOpen, setImageReplaceModalOpen] = useState(false)
  const [bubbleText, setBubbleText] = useState('')
  const [showLayerPanel, setShowLayerPanel] = useState(false)
  const [showPageNav] = useState(true)

  useEffect(() => {
    if (projectId && pageId) {
      loadPageData(projectId, pageId)
    }
  }, [pageId, projectId, loadPageData])

  useEffect(() => {
    if (!projectId) return
    const loadPages = async () => {
      try {
        const res: any = await apiClient.get(`/projects/${projectId}/pages`)
        const data = (res as { data?: any[] }).data
        if (data) {
          setPages(data)
          const current = data.find((p: any) => p.id === pageId)
          if (current) setCurrentPage(current)
        }
      } catch {
        const mockPages = Array.from({ length: 6 }, (_, i) => ({
          id: `page-${i + 1}`,
          page_number: i + 1,
          panel_count: 3 + (i % 2),
          status: i < 4 ? 'completed' : 'draft',
        }))
        setPages(mockPages)
        const current = mockPages.find((p) => p.id === pageId)
        if (current) setCurrentPage(current)
      }
    }
    loadPages()
  }, [projectId, pageId, setPages, setCurrentPage])

  useEffect(() => {
    if (selectedPanelId) {
      const panel = panels.find((p) => p.id === selectedPanelId)
      setSelectedInfo(panel || null)
      setSelectedBubbleInfo(null)
      if (panel && !candidateImages[panel.id]) {
        loadCandidateImages(panel.id)
      }
    } else {
      setSelectedInfo(null)
    }
  }, [selectedPanelId, panels, candidateImages])

  useEffect(() => {
    if (selectedBubbleId) {
      const bubble = bubbles.find((b) => b.id === selectedBubbleId)
      setSelectedBubbleInfo(bubble || null)
      setSelectedInfo(null)
      if (bubble) setBubbleText(bubble.text)
    } else {
      setSelectedBubbleInfo(null)
    }
  }, [selectedBubbleId, bubbles])

  const loadCandidateImages = useCallback(
    async (panelId: string) => {
      if (!panelId || !projectId) return
      try {
        const res: any = await apiClient.get(`/projects/${projectId}/panels/${panelId}/images`)
        const data = (res as { data?: any[] }).data
        if (data) {
          setCandidateImages(
            panelId,
            data.map((img: any) => ({
              id: img.id,
              url: img.url,
              thumbnail_url: img.thumbnail_url || img.url,
            }))
          )
        }
      } catch {
        const mockImages = Array.from({ length: 4 }, (_, i) => ({
          id: `candidate-${panelId}-${i + 1}`,
          url: '',
          thumbnail_url: '',
        }))
        setCandidateImages(panelId, mockImages)
      }
    },
    [projectId]
  )

  const handleZoomIn = useCallback(() => {
    setStageScale((s) => Math.min(s + 0.1, 2))
  }, [setStageScale])

  const handleZoomOut = useCallback(() => {
    setStageScale((s) => Math.max(s - 0.1, 0.2))
  }, [setStageScale])

  const handleResetView = useCallback(() => {
    setStageScale(0.5)
    setStagePosition({ x: 0, y: 0 })
  }, [setStageScale])

  const handleWheel = useCallback(
    (e: any) => {
      e.evt.preventDefault()
      const scaleBy = 1.05
      const oldScale = stageScale
      const newScale = e.evt.deltaY > 0 ? oldScale / scaleBy : oldScale * scaleBy
      setStageScale(Math.max(0.2, Math.min(2, newScale)))
    },
    [stageScale, setStageScale]
  )

  const handleDragEnd = useCallback((panelId: string, x: number, y: number) => {
    const { updatePanelPosition } = useEditorStore.getState()
    useEditorStore.getState().saveSnapshot()
    updatePanelPosition(panelId, x, y)
  }, [])

  const handleBubbleDragEnd = useCallback((bubbleId: string, x: number, y: number) => {
    const state = useEditorStore.getState()
    state.saveSnapshot()
    state.updateBubble(bubbleId, { x, y })
  }, [])

  const handleBubbleResize = useCallback(
    (bubbleId: string, width: number, height: number, x: number, y: number) => {
      const state = useEditorStore.getState()
      state.saveSnapshot()
      state.updateBubble(bubbleId, { width, height, x, y })
    },
    []
  )

  const handleSelectPanel = useCallback(
    (panelId: string) => {
      setSelectedPanelId(panelId === selectedPanelId ? null : panelId)
    },
    [selectedPanelId, setSelectedPanelId]
  )

  const handleSelectBubble = useCallback(
    (bubbleId: string) => {
      setSelectedBubbleId(bubbleId === selectedBubbleId ? null : bubbleId)
    },
    [selectedBubbleId, setSelectedBubbleId]
  )

  const handleBubbleTextChange = useCallback(
    (text: string) => {
      setBubbleText(text)
      if (selectedBubbleId) {
        updateBubble(selectedBubbleId, { text })
      }
    },
    [selectedBubbleId, updateBubble]
  )

  const handleDeleteSelected = useCallback(() => {
    if (selectedBubbleId) {
      removeBubble(selectedBubbleId)
    }
  }, [selectedBubbleId, removeBubble])

  const handleSave = useCallback(async () => {
    if (!projectId) return
    try {
      await save(projectId)
      message.success('保存成功')
    } catch {
      message.error('保存失败，请稍后重试')
    }
  }, [save, projectId])

  const handleImageReplace = (imageUrl: string) => {
    if (selectedPanelId) {
      replacePanelImage(selectedPanelId, imageUrl)
      setImageReplaceModalOpen(false)
      message.success('图片已替换')
    }
  }

  const handleBack = () => {
    const pathParts = window.location.pathname.split('/')
    pathParts.pop()
    navigate(pathParts.join('/'))
  }

  const handleAddBubbleFromToolbar = useCallback(
    (type: 'narration' | 'dialogue' | 'thinking') => {
      if (selectedPanelId) addBubble(selectedPanelId, type)
      else message.info('请先选择一个分镜')
    },
    [selectedPanelId, addBubble]
  )

  const currentImages: CandidateImage[] = selectedPanelId ? candidateImages[selectedPanelId] || [] : []

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement).tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return

      if ((e.ctrlKey || e.metaKey) && e.key === 'z' && !e.shiftKey) {
        e.preventDefault()
        undo()
      } else if ((e.ctrlKey || e.metaKey) && (e.key === 'y' || (e.key === 'z' && e.shiftKey))) {
        e.preventDefault()
        redo()
      } else if (e.key === 'Delete' || e.key === 'Backspace') {
        e.preventDefault()
        handleDeleteSelected()
      } else if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault()
        void handleSave()
      } else if (e.key === '=' || e.key === '+') {
        e.preventDefault()
        handleZoomIn()
      } else if (e.key === '-') {
        e.preventDefault()
        handleZoomOut()
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [undo, redo, handleDeleteSelected, handleSave, handleZoomIn, handleZoomOut])

  return (
    <Layout style={{ height: 'calc(100vh - 56px)' }}>
      <EditorToolbar
        tool={tool}
        setTool={setTool}
        isDirty={isDirty}
        showLayerPanel={showLayerPanel}
        onBack={handleBack}
        onZoomIn={handleZoomIn}
        onZoomOut={handleZoomOut}
        onResetView={handleResetView}
        onUndo={() => undo()}
        onRedo={() => redo()}
        onAddBubble={handleAddBubbleFromToolbar}
        onToggleLayerPanel={() => setShowLayerPanel(!showLayerPanel)}
        onLongStripPreview={() => setLongStripVisible(true)}
        onSave={handleSave}
      />

      {showPageNav && (
        <Sider
          width={160}
          theme="light"
          style={{
            borderRight: '1px solid #f0f0f0',
            background: '#fafafa',
            overflow: 'auto',
          }}
        >
          <div style={{ padding: 12 }}>
            <PageThumbnails />
          </div>
        </Sider>
      )}

      <Content
        ref={containerRef}
        style={{
          overflow: 'auto',
          background: '#1a1a2e',
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'flex-start',
          padding: 24,
        }}
      >
        <div
          style={{
            boxShadow: '0 4px 20px rgba(0,0,0,0.4)',
            lineHeight: 0,
          }}
        >
          <Stage
            width={CANVAS_WIDTH * stageScale}
            height={CANVAS_HEIGHT * stageScale}
            scaleX={stageScale}
            scaleY={stageScale}
            x={stagePosition.x}
            y={stagePosition.y}
            onWheel={handleWheel}
            style={{ background: '#0f0f23' }}
          >
            <Layer>
              <Rect
                x={0}
                y={0}
                width={CANVAS_WIDTH}
                height={CANVAS_HEIGHT}
                fill="#1a1a2e"
                shadowColor="rgba(0,0,0,0.3)"
                shadowBlur={10}
              />

              {panels.map((panel) => (
                <PanelWithImage
                  key={panel.id}
                  panel={panel}
                  isSelected={selectedPanelId === panel.id}
                  tool={tool}
                  hidden={hiddenLayerIds.includes(panel.id)}
                  locked={lockedLayerIds.includes(panel.id)}
                  onSelect={() => handleSelectPanel(panel.id)}
                  onDragEnd={(x, y) => handleDragEnd(panel.id, x, y)}
                />
              ))}

              {bubbles.map((bubble) => (
                <BubbleShape
                  key={bubble.id}
                  bubble={bubble}
                  isSelected={selectedBubbleId === bubble.id}
                  tool={tool}
                  hidden={hiddenLayerIds.includes(bubble.id)}
                  locked={lockedLayerIds.includes(bubble.id)}
                  onSelect={() => handleSelectBubble(bubble.id)}
                  onDragEnd={(x, y) => handleBubbleDragEnd(bubble.id, x, y)}
                  onResize={handleBubbleResize}
                />
              ))}
            </Layer>
          </Stage>
        </div>
      </Content>

      <PropertiesPanel
        isDirty={isDirty}
        selectedInfo={selectedInfo}
        selectedBubbleInfo={selectedBubbleInfo}
        bubbleText={bubbleText}
        onBubbleTextChange={handleBubbleTextChange}
        onUpdateBubble={updateBubble}
        onRemoveBubble={removeBubble}
        onAddBubble={addBubble}
        onReplaceImage={() => setImageReplaceModalOpen(true)}
      />

      <ImageReplaceModal
        open={imageReplaceModalOpen}
        onClose={() => setImageReplaceModalOpen(false)}
        onReplace={handleImageReplace}
        images={currentImages}
      />

      <LongStripPreview
        visible={longStripVisible}
        onClose={() => setLongStripVisible(false)}
      />
    </Layout>
  )
}

export default ComicEditor
