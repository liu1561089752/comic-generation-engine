import React from 'react'
import { Button, Layout, Divider, Tooltip } from 'antd'
import {
  ZoomInOutlined,
  ZoomOutOutlined,
  DragOutlined,
  SelectOutlined,
  ArrowLeftOutlined,
  ExpandOutlined,
  SaveOutlined,
  UndoOutlined,
  RedoOutlined,
  CommentOutlined,
  HighlightOutlined,
  ThunderboltOutlined,
  OrderedListOutlined,
  AppstoreOutlined,
} from '@ant-design/icons'

const { Sider } = Layout

interface Props {
  tool: 'select' | 'drag'
  setTool: (tool: 'select' | 'drag') => void
  isDirty: boolean
  showLayerPanel: boolean
  onBack: () => void
  onZoomIn: () => void
  onZoomOut: () => void
  onResetView: () => void
  onUndo: () => void
  onRedo: () => void
  onAddBubble: (type: 'narration' | 'dialogue' | 'thinking') => void
  onToggleLayerPanel: () => void
  onLongStripPreview: () => void
  onSave: () => void
}

export const EditorToolbar: React.FC<Props> = ({
  tool,
  setTool,
  isDirty,
  showLayerPanel,
  onBack,
  onZoomIn,
  onZoomOut,
  onResetView,
  onUndo,
  onRedo,
  onAddBubble,
  onToggleLayerPanel,
  onLongStripPreview,
  onSave,
}) => {
  return (
    <Sider
      width={60}
      theme="light"
      style={{ borderRight: '1px solid #f0f0f0', background: '#fafafa' }}
    >
      <div style={{ padding: '12px 0', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
        <Tooltip title="返回" placement="right">
          <Button
            icon={<ArrowLeftOutlined />}
            onClick={onBack}
            style={{ marginBottom: 12 }}
          />
        </Tooltip>

        <Divider style={{ margin: '4px 0' }} />

        <Tooltip title="选择工具" placement="right">
          <Button
            icon={<SelectOutlined />}
            type={tool === 'select' ? 'primary' : 'default'}
            onClick={() => setTool('select')}
          />
        </Tooltip>

        <Tooltip title="移动工具" placement="right">
          <Button
            icon={<DragOutlined />}
            type={tool === 'drag' ? 'primary' : 'default'}
            onClick={() => setTool('drag')}
          />
        </Tooltip>

        <Divider style={{ margin: '4px 0' }} />

        <Tooltip title="放大" placement="right">
          <Button icon={<ZoomInOutlined />} onClick={onZoomIn} />
        </Tooltip>

        <Tooltip title="缩小" placement="right">
          <Button icon={<ZoomOutOutlined />} onClick={onZoomOut} />
        </Tooltip>

        <Tooltip title="重置视图" placement="right">
          <Button icon={<ExpandOutlined />} onClick={onResetView} />
        </Tooltip>

        <Divider style={{ margin: '4px 0' }} />

        <Tooltip title="撤销 (Ctrl+Z)" placement="right">
          <Button icon={<UndoOutlined />} onClick={onUndo} />
        </Tooltip>

        <Tooltip title="重做 (Ctrl+Y)" placement="right">
          <Button icon={<RedoOutlined />} onClick={onRedo} />
        </Tooltip>

        <Divider style={{ margin: '4px 0' }} />

        <Tooltip title="添加旁白" placement="right">
          <Button
            icon={<CommentOutlined />}
            onClick={() => onAddBubble('narration')}
            style={{ fontSize: 12 }}
          />
        </Tooltip>

        <Tooltip title="添加对话" placement="right">
          <Button
            icon={<HighlightOutlined />}
            onClick={() => onAddBubble('dialogue')}
            style={{ fontSize: 12 }}
          />
        </Tooltip>

        <Tooltip title="添加内心独白" placement="right">
          <Button
            icon={<ThunderboltOutlined />}
            onClick={() => onAddBubble('thinking')}
            style={{ fontSize: 12 }}
          />
        </Tooltip>

        <Divider style={{ margin: '4px 0' }} />

        <Tooltip title="图层面板" placement="right">
          <Button
            icon={<OrderedListOutlined />}
            type={showLayerPanel ? 'primary' : 'default'}
            onClick={onToggleLayerPanel}
          />
        </Tooltip>

        <Tooltip title="长图预览" placement="right">
          <Button
            icon={<AppstoreOutlined />}
            onClick={onLongStripPreview}
          />
        </Tooltip>

        <Divider style={{ margin: '4px 0' }} />

        <Tooltip title="保存 (Ctrl+S)" placement="right">
          <Button
            icon={<SaveOutlined />}
            type={isDirty ? 'primary' : 'default'}
            onClick={onSave}
          />
        </Tooltip>
      </div>
    </Sider>
  )
}

export default EditorToolbar
