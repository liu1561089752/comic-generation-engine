import React from 'react'
import { Modal, Typography } from 'antd'
import { PictureOutlined } from '@ant-design/icons'

const { Text: AntText } = Typography

export interface CandidateImage {
  id: string
  url: string
  thumbnail_url: string
}

interface Props {
  open: boolean
  onClose: () => void
  onReplace: (imageUrl: string) => void
  images: CandidateImage[]
}

export const ImageReplaceModal: React.FC<Props> = ({
  open,
  onClose,
  onReplace,
  images,
}) => {
  return (
    <Modal
      title="替换图片"
      open={open}
      onCancel={onClose}
      footer={null}
      width={480}
      destroyOnClose
    >
      {images.length > 0 ? (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(2, 1fr)',
            gap: 12,
          }}
        >
          {images.map((img) => (
            <div
              key={img.id}
              onClick={() => onReplace(img.url)}
              style={{
                borderRadius: 8,
                overflow: 'hidden',
                cursor: 'pointer',
                border: '2px solid transparent',
                transition: 'border-color 0.2s',
                aspectRatio: '3/4',
                background: '#1a1a2e',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = '#6C5CE7'
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = 'transparent'
              }}
            >
              {img.thumbnail_url || img.url ? (
                <img
                  src={img.thumbnail_url || img.url}
                  alt="候选图片"
                  style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                  onError={(e) => {
                    (e.target as HTMLImageElement).style.display = 'none'
                  }}
                />
              ) : (
                <PictureOutlined style={{ fontSize: 32, color: '#555' }} />
              )}
            </div>
          ))}
        </div>
      ) : (
        <div style={{ textAlign: 'center', padding: '40px 0', color: '#999' }}>
          <PictureOutlined style={{ fontSize: 40, display: 'block', marginBottom: 12, opacity: 0.3 }} />
          <AntText type="secondary">暂无候选图片</AntText>
        </div>
      )}
    </Modal>
  )
}

export default ImageReplaceModal
