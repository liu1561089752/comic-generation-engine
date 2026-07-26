import { useState } from 'react'
import { Modal, Upload, Button, message, Progress } from 'antd'
import { InboxOutlined } from '@ant-design/icons'
import type { UploadFile, RcFile, UploadProps } from 'antd/es/upload/interface'

const { Dragger } = Upload

const MAX_FILE_SIZE = 50 * 1024 * 1024 // 50MB
const ACCEPTED_TYPES = '.txt,.docx,.md'

interface NovelUploadModalProps {
  open: boolean
  uploading: boolean
  uploadProgress?: number
  onCancel: () => void
  onFileSelect: (file: File, title?: string) => void
}

export default function NovelUploadModal({
  open,
  uploading,
  uploadProgress = 0,
  onCancel,
  onFileSelect,
}: NovelUploadModalProps) {
  const [selectedFile, setSelectedFile] = useState<RcFile | null>(null)

  const beforeUpload = (file: RcFile): boolean => {
    const isValidSize = file.size <= MAX_FILE_SIZE
    if (!isValidSize) {
      message.error('文件大小不能超过 50MB')
      return false
    }

    const isValidType =
      file.name.endsWith('.txt') ||
      file.name.endsWith('.docx') ||
      file.name.endsWith('.md')
    if (!isValidType) {
      message.error('仅支持 .txt、.docx、.md 格式文件')
      return false
    }

    setSelectedFile(file)
    // 自动从文件名推断标题（去掉扩展名）
    const title = file.name.replace(/\.(txt|docx|md)$/i, '')
    onFileSelect(file, title)
    return false
  }

  const handleRemove = () => {
    setSelectedFile(null)
  }

  const draggerProps: UploadProps = {
    name: 'file',
    multiple: false,
    accept: ACCEPTED_TYPES,
    showUploadList: false,
    beforeUpload,
    onRemove: handleRemove,
    fileList: selectedFile ? [selectedFile as unknown as UploadFile] : [],
  }

  return (
    <Modal
      title="导入小说"
      open={open}
      onCancel={onCancel}
      footer={null}
      width={520}
      destroyOnClose
    >
      <Dragger {...draggerProps}>
        <p className="ant-upload-drag-icon">
          <InboxOutlined />
        </p>
        <p className="ant-upload-text">点击或拖拽文件到此区域上传</p>
        <p className="ant-upload-hint">
          支持 .txt、.docx、.md 格式，单个文件不超过 50MB
        </p>
      </Dragger>

      {selectedFile && (
        <div style={{ marginTop: 16 }}>
          <div style={{ marginBottom: 8 }}>
            <span style={{ fontWeight: 500 }}>{selectedFile.name}</span>
            <Button
              type="link"
              danger
              size="small"
              onClick={handleRemove}
              style={{ float: 'right' }}
            >
              移除
            </Button>
          </div>
          {uploading && (
            <Progress
              percent={uploadProgress > 0 ? uploadProgress : 100}
              status={uploadProgress > 0 && uploadProgress < 100 ? 'active' : 'active'}
              format={(percent) => (percent && percent < 100 ? `${percent}%` : '处理中...')}
            />
          )}
        </div>
      )}
    </Modal>
  )
}
