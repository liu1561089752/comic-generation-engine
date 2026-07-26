import React from 'react'
import { Layout, Typography, Divider, Button, Input, InputNumber, Select, ColorPicker } from 'antd'
import {
  PictureOutlined,
  CommentOutlined,
  HighlightOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons'
import type { PanelInfo, BubbleData } from '../../stores/editorStore'
import LayerPanel from './LayerPanel'

const { Sider } = Layout
const { Text: AntText } = Typography
const { TextArea } = Input

interface Props {
  isDirty: boolean
  selectedInfo: PanelInfo | null
  selectedBubbleInfo: BubbleData | null
  bubbleText: string
  onBubbleTextChange: (text: string) => void
  onUpdateBubble: (id: string, updates: Partial<BubbleData>) => void
  onRemoveBubble: (id: string) => void
  onAddBubble: (panelId: string, type: 'narration' | 'dialogue' | 'thinking') => void
  onReplaceImage: () => void
}

export const PropertiesPanel: React.FC<Props> = ({
  isDirty,
  selectedInfo,
  selectedBubbleInfo,
  bubbleText,
  onBubbleTextChange,
  onUpdateBubble,
  onRemoveBubble,
  onAddBubble,
  onReplaceImage,
}) => {
  return (
    <Sider
      width={300}
      theme="light"
      style={{ borderLeft: '1px solid #f0f0f0', background: '#fafafa', overflow: 'auto' }}
    >
      <div style={{ padding: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <AntText strong style={{ fontSize: 15 }}>属性面板</AntText>
          {isDirty && (
            <span style={{ fontSize: 11, color: '#faad14' }}>● 未保存</span>
          )}
        </div>
        <Divider style={{ margin: '12px 0' }} />

        {selectedInfo ? (
          <div>
            <div style={{ marginBottom: 16 }}>
              <AntText type="secondary" style={{ fontSize: 12 }}>分镜编号</AntText>
              <div style={{ fontSize: 14, fontWeight: 500 }}>Panel {selectedInfo.panel_number}</div>
            </div>

            <Divider style={{ margin: '8px 0' }} />

            <div style={{ marginBottom: 12 }}>
              <AntText type="secondary" style={{ fontSize: 12 }}>位置 (X, Y)</AntText>
              <div style={{ fontSize: 14 }}>
                ({Math.round(selectedInfo.x)}, {Math.round(selectedInfo.y)})
              </div>
            </div>

            <div style={{ marginBottom: 12 }}>
              <AntText type="secondary" style={{ fontSize: 12 }}>尺寸 (W × H)</AntText>
              <div style={{ fontSize: 14 }}>
                {Math.round(selectedInfo.width)} × {Math.round(selectedInfo.height)}
              </div>
            </div>

            <Divider style={{ margin: '8px 0' }} />

            <div style={{ marginBottom: 12 }}>
              <AntText type="secondary" style={{ fontSize: 12 }}>图片状态</AntText>
              <div style={{ fontSize: 14, display: 'flex', alignItems: 'center', gap: 6 }}>
                <PictureOutlined style={{ color: selectedInfo.image_url ? '#52c41a' : '#d9d9d9' }} />
                {selectedInfo.image_url ? '已加载' : '暂无图片'}
              </div>
            </div>

            <div style={{ marginBottom: 12 }}>
              <Button
                block
                icon={<PictureOutlined />}
                onClick={onReplaceImage}
              >
                替换图片
              </Button>
            </div>

            <Divider style={{ margin: '8px 0' }} />
            <AntText type="secondary" style={{ fontSize: 12 }}>添加气泡</AntText>
            <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>
              <Button
                size="small"
                icon={<CommentOutlined />}
                onClick={() => onAddBubble(selectedInfo.id, 'narration')}
                style={{ fontSize: 11 }}
              >
                旁白
              </Button>
              <Button
                size="small"
                icon={<HighlightOutlined />}
                onClick={() => onAddBubble(selectedInfo.id, 'dialogue')}
                style={{ fontSize: 11 }}
              >
                对话
              </Button>
              <Button
                size="small"
                icon={<ThunderboltOutlined />}
                onClick={() => onAddBubble(selectedInfo.id, 'thinking')}
                style={{ fontSize: 11 }}
              >
                内心
              </Button>
            </div>
          </div>
        ) : selectedBubbleInfo ? (
          <div>
            <div style={{ marginBottom: 12 }}>
              <AntText type="secondary" style={{ fontSize: 12 }}>气泡类型</AntText>
              <Select
                style={{ width: '100%', marginTop: 6 }}
                size="small"
                value={selectedBubbleInfo.type}
                onChange={(val) => {
                  const sizes: Record<string, { width: number; height: number }> = {
                    narration: { width: selectedBubbleInfo.width, height: 80 },
                    dialogue: { width: selectedBubbleInfo.width, height: 100 },
                    thinking: { width: selectedBubbleInfo.width, height: selectedBubbleInfo.width },
                  }
                  const size = sizes[val] || { width: selectedBubbleInfo.width, height: selectedBubbleInfo.height }
                  onUpdateBubble(selectedBubbleInfo.id, { type: val as BubbleData['type'], ...size })
                }}
                options={[
                  { label: '📖 旁白', value: 'narration' },
                  { label: '💬 对话', value: 'dialogue' },
                  { label: '💭 内心独白', value: 'thinking' },
                ]}
              />
            </div>

            <Divider style={{ margin: '8px 0' }} />

            <div style={{ marginBottom: 12 }}>
              <AntText type="secondary" style={{ fontSize: 12 }}>文本内容</AntText>
              <TextArea
                value={bubbleText}
                onChange={(e) => onBubbleTextChange(e.target.value)}
                rows={4}
                style={{ marginTop: 6, fontSize: 13 }}
                placeholder="输入气泡文本..."
              />
            </div>

            <Divider style={{ margin: '8px 0' }} />
            <AntText type="secondary" style={{ fontSize: 12 }}>文字样式</AntText>

            <div style={{ display: 'flex', gap: 8, marginTop: 6, marginBottom: 12 }}>
              <div style={{ flex: 1 }}>
                <AntText type="secondary" style={{ fontSize: 11 }}>字号</AntText>
                <InputNumber
                  size="small"
                  style={{ width: '100%' }}
                  min={8}
                  max={72}
                  value={selectedBubbleInfo.fontSize || 14}
                  onChange={(val) => {
                    if (val) onUpdateBubble(selectedBubbleInfo.id, { fontSize: val })
                  }}
                />
              </div>
              <div style={{ flex: 1 }}>
                <AntText type="secondary" style={{ fontSize: 11 }}>字体</AntText>
                <Select
                  size="small"
                  style={{ width: '100%' }}
                  value={selectedBubbleInfo.fontFamily || 'sans-serif'}
                  onChange={(val) => onUpdateBubble(selectedBubbleInfo.id, { fontFamily: val })}
                  options={[
                    { label: '无衬线', value: 'sans-serif' },
                    { label: '宋体', value: 'serif' },
                    { label: '黑体', value: '"Microsoft YaHei"' },
                    { label: '楷体', value: 'KaiTi' },
                  ]}
                />
              </div>
            </div>

            <div style={{ marginBottom: 12 }}>
              <AntText type="secondary" style={{ fontSize: 11 }}>文字颜色</AntText>
              <div style={{ marginTop: 4 }}>
                <ColorPicker
                  size="small"
                  value={selectedBubbleInfo.color || '#333333'}
                  onChange={(color) => onUpdateBubble(selectedBubbleInfo.id, { color: color.toHexString() })}
                  showText
                />
              </div>
            </div>

            <Divider style={{ margin: '8px 0' }} />

            <div style={{ marginBottom: 12 }}>
              <AntText type="secondary" style={{ fontSize: 12 }}>位置 (X, Y)</AntText>
              <div style={{ fontSize: 14 }}>
                ({Math.round(selectedBubbleInfo.x)}, {Math.round(selectedBubbleInfo.y)})
              </div>
            </div>

            <div style={{ marginBottom: 12 }}>
              <AntText type="secondary" style={{ fontSize: 12 }}>尺寸 (W × H)</AntText>
              <div style={{ fontSize: 14 }}>
                {Math.round(selectedBubbleInfo.width)} × {Math.round(selectedBubbleInfo.height)}
              </div>
            </div>

            <Divider style={{ margin: '8px 0' }} />

            <Button
              danger
              block
              onClick={() => onRemoveBubble(selectedBubbleInfo.id)}
            >
              删除气泡
            </Button>
          </div>
        ) : (
          <div style={{ textAlign: 'center', padding: '40px 0', color: '#999' }}>
            <PictureOutlined style={{ fontSize: 32, display: 'block', marginBottom: 8, opacity: 0.3 }} />
            <AntText type="secondary">点击画布中的元素查看属性</AntText>
            <div style={{ marginTop: 16, fontSize: 12, color: '#bbb' }}>
              <div>快捷键:</div>
              <div>Ctrl+Z 撤销 | Ctrl+Y 重做</div>
              <div>Delete 删除 | Ctrl+S 保存</div>
              <div>+/- 缩放</div>
            </div>
          </div>
        )}

        <Divider style={{ margin: '16px 0' }} />
        <LayerPanel />
      </div>
    </Sider>
  )
}

export default PropertiesPanel
