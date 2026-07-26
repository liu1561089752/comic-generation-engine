import { useEffect, useState } from 'react'

interface UseImageLoaderResult {
  image: HTMLImageElement | null
  loaded: boolean
}

export function useImageLoader(url: string): UseImageLoaderResult {
  const [state, setState] = useState<UseImageLoaderResult>({ image: null, loaded: false })

  useEffect(() => {
    if (!url) {
      setState({ image: null, loaded: false })
      return
    }
    const img = new window.Image()
    img.crossOrigin = 'anonymous'
    img.onload = () => {
      setState({ image: img, loaded: true })
    }
    img.onerror = () => {
      setState({ image: null, loaded: false })
    }
    img.src = url
    return () => {
      img.onload = null
      img.onerror = null
    }
  }, [url])

  return state
}
