import { useState, useRef, useCallback, useEffect } from 'react'

type TaskStatus = 'queued' | 'running' | 'completed' | 'failed' | 'cancelled'

interface TaskProgressState {
  taskId: string | null
  status: TaskStatus | null
  progress: number
  errorMessage: string | null
  logs: Array<{ timestamp: string; message: string; level: string }>
  // 流式输出文本（生成脚本等任务的实时内容，增量拼接）
  streamText: string
  polling: boolean
}

interface UseTaskProgressOptions {
  projectId: string | undefined
  onCompleted?: () => void
  onFailed?: (error: string) => void
  pollInterval?: number // ms, default 2000
}

export function useTaskProgress({ projectId, onCompleted, onFailed, pollInterval = 2000 }: UseTaskProgressOptions) {
  const [state, setState] = useState<TaskProgressState>({
    taskId: null,
    status: null,
    progress: 0,
    errorMessage: null,
    logs: [],
    streamText: '',
    polling: false,
  })
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  // 已消费的 stream_output 长度（轮询只取增量，避免重复拼接）
  const streamLenRef = useRef(0)
  // 轮询代次：startPolling / stopPolling / 卸载时递增，使旧循环在途请求的回调失效
  const generationRef = useRef(0)
  const onCompletedRef = useRef(onCompleted)
  const onFailedRef = useRef(onFailed)
  onCompletedRef.current = onCompleted
  onFailedRef.current = onFailed
  // D56: 连续失败计数 + 最大重试
  const failCountRef = useRef(0)
  const MAX_FAILS = 10

  const stopPolling = useCallback(() => {
    generationRef.current += 1
    if (timerRef.current) {
      clearTimeout(timerRef.current)
      timerRef.current = null
    }
    setState(prev => ({ ...prev, polling: false }))
  }, [])

  const startPolling = useCallback((taskId: string) => {
    // 先终止上一轮轮询（含在途请求），避免两条循环共享 timerRef / state
    if (timerRef.current) {
      clearTimeout(timerRef.current)
      timerRef.current = null
    }
    const generation = ++generationRef.current
    streamLenRef.current = 0
    setState({
      taskId,
      status: 'queued',
      progress: 0,
      errorMessage: null,
      logs: [],
      streamText: '',
      polling: true,
    })
    failCountRef.current = 0

    const fetchStatus = async () => {
      if (!projectId) return
      try {
        const { default: apiClient } = await import('../api/client')
        const res = await apiClient.get(`/projects/${projectId}/tasks/${taskId}/status`)
        // 代次不一致：本轮轮询已被新任务或 stopPolling / 卸载取代，丢弃结果且不再调度
        if (generation !== generationRef.current) return
        const data = res.data?.data || res.data
        // 成功时重置失败计数（D56）
        failCountRef.current = 0
        // 流式输出增量：只取上次消费长度之后的新内容
        let streamText = ''
        const fullStream: string = data.stream_output || ''
        if (fullStream.length > streamLenRef.current) {
          streamText = fullStream.slice(streamLenRef.current)
          streamLenRef.current = fullStream.length
        }
        setState(prev => ({
          ...prev,
          status: data.status,
          progress: data.progress || 0,
          errorMessage: data.error_message || null,
          logs: data.logs || [],
          streamText: streamText ? prev.streamText + streamText : prev.streamText,
        }))

        if (data.status === 'completed') {
          stopPolling()
          onCompletedRef.current?.()
          return
        } else if (data.status === 'failed') {
          stopPolling()
          onFailedRef.current?.(data.error_message || '任务失败')
          return
        }
        // 继续轮询：使用原始间隔
        timerRef.current = setTimeout(fetchStatus, pollInterval)
      } catch (e) {
        if (generation !== generationRef.current) return
        // D56: 网络错误时指数退避 + 最大重试，不无限轮询
        console.warn('轮询任务状态失败:', e)
        failCountRef.current += 1
        if (failCountRef.current >= MAX_FAILS) {
          stopPolling()
          onFailedRef.current?.('任务状态查询连续失败，请检查网络后刷新页面')
          return
        }
        const backoff = Math.min(pollInterval * Math.pow(2, failCountRef.current - 1), 30000)
        timerRef.current = setTimeout(fetchStatus, backoff)
      }
    }

    fetchStatus()
  }, [projectId, pollInterval, stopPolling])

  // cleanup on unmount
  useEffect(() => {
    return () => {
      generationRef.current += 1
      if (timerRef.current) {
        clearTimeout(timerRef.current)
        timerRef.current = null
      }
    }
  }, [])

  return {
    ...state,
    startPolling,
    stopPolling,
    isRunning: state.status === 'queued' || state.status === 'running',
    isCompleted: state.status === 'completed',
    isFailed: state.status === 'failed',
  }
}
