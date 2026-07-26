import React from 'react'
import { Typography, Divider } from 'antd'
import { PictureOutlined, CheckCircleFilled } from '@ant-design/icons'
import { useEditorStore } from '../../stores/editorStore'
import { useNavigate, useParams } from 'react-router-dom'

const { Text: AntText } = Typography

const PageThumbnails: React.FC = () => {
  // 路由定义为 projects/:id/editor/:pageId，参数名是 id
  const { id: projectId } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const pages = useEditorStore((s) => s.pages)
  const currentPage = useEditorStore((s) => s.currentPage)

  const handlePageClick = (pageId: string) => {
    if (projectId) {
      navigate(`/projects/${projectId}/editor/${pageId}`)
    }
  }

  return (
    <div>
      <AntText strong style={{ fontSize: 13 }}>页面导航</AntText>
      <Divider style={{ margin: '8px 0' }} />

      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {pages.map((page) => {
          const isCurrent = currentPage?.id === page.id || window.location.pathname.endsWith(page.id)

          return (
            <div
              key={page.id}
              onClick={() => handlePageClick(page.id)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                padding: '6px 8px',
                borderRadius: 6,
                cursor: 'pointer',
                background: isCurrent ? '#e6f7ff' : 'transparent',
                border: isCurrent ? '1px solid #91d5ff' : '1px solid transparent',
                transition: 'all 0.2s',
              }}
              onMouseEnter={(e) => {
                if (!isCurrent) e.currentTarget.style.background = '#f5f5f5'
              }}
              onMouseLeave={(e) => {
                if (!isCurrent) e.currentTarget.style.background = 'transparent'
              }}
            >
              {/* 缩略图 */}
              <div
                style={{
                  width: 40,
                  height: 54,
                  borderRadius: 4,
                  background: '#1a1a2e',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  overflow: 'hidden',
                  flexShrink: 0,
                }}
              >
                {page.thumbnail_url ? (
                  <img
                    src={page.thumbnail_url}
                    alt={`第 ${page.page_number} 页`}
                    style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                  />
                ) : (
                  <PictureOutlined style={{ color: '#555', fontSize: 16 }} />
                )}
              </div>

              {/* 信息 */}
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 13, fontWeight: isCurrent ? 600 : 400 }}>
                  第 {page.page_number} 页
                </div>
                <div style={{ fontSize: 11, color: '#999' }}>
                  {page.panel_count} 个分镜
                  {page.status === 'completed' && (
                    <CheckCircleFilled style={{ color: '#52c41a', marginLeft: 4, fontSize: 10 }} />
                  )}
                </div>
              </div>
            </div>
          )
        })}
      </div>

      {pages.length === 0 && (
        <div style={{ textAlign: 'center', padding: '20px 0', color: '#999', fontSize: 12 }}>
          暂无页面
        </div>
      )}
    </div>
  )
}

export default PageThumbnails
