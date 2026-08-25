import { useState } from 'react'

/**
 * O15: 懒加载图片组件。
 *
 * 基于原生 <img loading="lazy" decoding="async">，浏览器在图片进入视口前不下载资源，
 * 适合漫画页缩略图、参考图网格等图片密集场景。相比 antd <Image> 更轻量：
 * - 无 preview 放大（纯展示场景不需要）
 * - 加载中显示占位背景，加载完成后淡入
 * - 加载失败显示 fallback 文本占位（不再请求无效资源）
 */
interface LazyImageProps {
  src: string
  alt?: string
  style?: React.CSSProperties
  className?: string
  onClick?: () => void
  /** 加载中/失败的占位背景色，默认浅灰 */
  placeholderColor?: string
  /** 加载失败时显示的占位文本 */
  fallback?: string
}

export default function LazyImage({
  src,
  alt = '',
  style,
  className,
  onClick,
  placeholderColor = '#f0f0f0',
  fallback = 'NA',
}: LazyImageProps) {
  const [loaded, setLoaded] = useState(false)
  const [error, setError] = useState(false)

  // 无图或加载失败：渲染占位块，避免发起无效请求
  if (!src || error) {
    return (
      <div
        className={className}
        onClick={onClick}
        style={{
          ...style,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: placeholderColor,
          color: '#999',
          fontSize: 11,
          overflow: 'hidden',
        }}
      >
        {fallback}
      </div>
    )
  }

  return (
    <img
      src={src}
      alt={alt}
      loading="lazy"
      decoding="async"
      onClick={onClick}
      className={className}
      style={{
        ...style,
        opacity: loaded ? 1 : 0,
        transition: 'opacity 0.25s ease',
        background: placeholderColor,
      }}
      onLoad={() => setLoaded(true)}
      onError={() => setError(true)}
    />
  )
}
