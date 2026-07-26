import { useEffect, useRef, useCallback } from 'react'
import { useAuthStore } from '../stores/authStore'

interface WebSocketMessage {
  type: string
  data: unknown
}

type MessageHandler = (message: WebSocketMessage) => void

export function useWebSocket(url: string, onMessage?: MessageHandler) {
  const wsRef = useRef<WebSocket | null>(null)
  const token = useAuthStore((state) => state.token)
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout>>()
  // D60: 用 ref 持有最新的 onMessage，避免它进入 connect 依赖数组
  // 导致每次父组件渲染（onMessage 引用变化）时 WebSocket 重连
  const onMessageRef = useRef(onMessage)
  onMessageRef.current = onMessage
  // 重连退避计数
  const reconnectAttemptsRef = useRef(0)

  const connect = useCallback(() => {
    if (!token) return

    const wsUrl = `${url}?token=${token}`
    const ws = new WebSocket(wsUrl)

    ws.onopen = () => {
      console.log('WebSocket connected')
      reconnectAttemptsRef.current = 0
    }

    ws.onmessage = (event) => {
      try {
        const message: WebSocketMessage = JSON.parse(event.data)
        onMessageRef.current?.(message)
      } catch (e) {
        console.error('Failed to parse WebSocket message:', e)
      }
    }

    ws.onclose = () => {
      // 指数退避重连，避免服务端不可用时疯狂重连
      const attempts = reconnectAttemptsRef.current++
      const delay = Math.min(1000 * Math.pow(2, attempts), 30000)
      console.log(`WebSocket disconnected, reconnecting in ${delay}ms...`)
      reconnectTimeoutRef.current = setTimeout(() => {
        connect()
      }, delay)
    }

    ws.onerror = (error) => {
      console.error('WebSocket error:', error)
      ws.close()
    }

    wsRef.current = ws
  }, [url, token])

  useEffect(() => {
    connect()

    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
      }
      wsRef.current?.close()
    }
  }, [connect])

  const send = useCallback((message: WebSocketMessage) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message))
    }
  }, [])

  return { send }
}
