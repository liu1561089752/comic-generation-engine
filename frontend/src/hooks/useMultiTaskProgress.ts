/**
 * T8 D23: Multi-task tracking via Map.
 *
 * Tracks multiple concurrent tasks by task_id, each with its own polling state.
 * Replaces single-task `useTaskProgress` for pages that need parallel task tracking
 * (e.g., generation center, tasks page).
 *
 * Each task is polled independently. Failed polls use exponential backoff
 * with a max retry count to avoid infinite polling.
 */
import { useState, useRef, useCallback, useEffect } from 'react'

type TaskStatus = 'queued' | 'running' | 'completed' | 'failed' | 'cancelled'

interface TaskEntry {
  taskId: string
  status: TaskStatus | null
  progress: number
  errorMessage: string | null
  logs: Array<{ timestamp: string; message: string; level: string }>
  polling: boolean
  failCount: number
}

interface UseMultiTaskProgressOptions {
  projectId: string | undefined
  pollInterval?: number
  onTaskCompleted?: (taskId: string) => void
  onTaskFailed?: (taskId: string, error: string) => void
}

const MAX_FAILS = 10

export function useMultiTaskProgress({
  projectId,
  pollInterval = 2000,
  onTaskCompleted,
  onTaskFailed,
}: UseMultiTaskProgressOptions) {
  const [tasks, setTasks] = useState<Record<string, TaskEntry>>({})
  const timersRef = useRef<Record<string, ReturnType<typeof setTimeout>>>({})
  // 按 taskId 记录轮询代次：清理定时器时递增，使该任务在途请求的回调失效
  const generationsRef = useRef<Record<string, number>>({})
  const onCompletedRef = useRef(onTaskCompleted)
  const onFailedRef = useRef(onTaskFailed)
  onCompletedRef.current = onTaskCompleted
  onFailedRef.current = onTaskFailed

  const clearTimer = useCallback((taskId: string) => {
    generationsRef.current[taskId] = (generationsRef.current[taskId] || 0) + 1
    const t = timersRef.current[taskId]
    if (t) {
      clearTimeout(t)
      delete timersRef.current[taskId]
    }
  }, [])

  const stopPolling = useCallback((taskId: string) => {
    clearTimer(taskId)
    setTasks((prev) => {
      if (!prev[taskId]) return prev
      return { ...prev, [taskId]: { ...prev[taskId], polling: false } }
    })
  }, [clearTimer])

  const stopAll = useCallback(() => {
    Object.keys(timersRef.current).forEach(clearTimer)
    setTasks((prev) => {
      const next: Record<string, TaskEntry> = {}
      for (const [k, v] of Object.entries(prev)) {
        next[k] = { ...v, polling: false }
      }
      return next
    })
  }, [clearTimer])

  const removeTask = useCallback((taskId: string) => {
    clearTimer(taskId)
    setTasks((prev) => {
      if (!prev[taskId]) return prev
      const next = { ...prev }
      delete next[taskId]
      return next
    })
  }, [clearTimer])

  const startPolling = useCallback((taskId: string) => {
    // 终止该 taskId 上一轮轮询（含在途请求），代次取清理后的最新值
    clearTimer(taskId)
    const generation = generationsRef.current[taskId]
    setTasks((prev) => ({
      ...prev,
      [taskId]: {
        taskId,
        status: 'queued',
        progress: 0,
        errorMessage: null,
        logs: [],
        polling: true,
        failCount: 0,
      },
    }))

    const fetchStatus = async () => {
      if (!projectId) return
      try {
        const { default: apiClient } = await import('../api/client')
        const res = await apiClient.get(`/projects/${projectId}/tasks/${taskId}/status`)
        // 代次不一致：该任务的轮询已被重启或停止（含卸载），丢弃结果且不再调度
        if (generation !== generationsRef.current[taskId]) return
        const data = res.data?.data || res.data

        setTasks((prev) => {
          if (!prev[taskId]) return prev
          return {
            ...prev,
            [taskId]: {
              ...prev[taskId],
              status: data.status,
              progress: data.progress || 0,
              errorMessage: data.error_message || null,
              logs: data.logs || [],
              failCount: 0,
            },
          }
        })

        if (data.status === 'completed') {
          clearTimer(taskId)
          setTasks((prev) =>
            prev[taskId] ? { ...prev, [taskId]: { ...prev[taskId], polling: false } } : prev
          )
          onCompletedRef.current?.(taskId)
          return
        } else if (data.status === 'failed') {
          clearTimer(taskId)
          setTasks((prev) =>
            prev[taskId] ? { ...prev, [taskId]: { ...prev[taskId], polling: false } } : prev
          )
          onFailedRef.current?.(taskId, data.error_message || '任务失败')
          return
        }
        timersRef.current[taskId] = setTimeout(fetchStatus, pollInterval)
      } catch (e) {
        if (generation !== generationsRef.current[taskId]) return
        console.warn(`轮询任务 ${taskId} 状态失败:`, e)
        setTasks((prev) => {
          if (!prev[taskId]) return prev
          const failCount = prev[taskId].failCount + 1
          if (failCount >= MAX_FAILS) {
            clearTimer(taskId)
            onFailedRef.current?.(taskId, '任务状态查询连续失败，请检查网络后刷新页面')
            return { ...prev, [taskId]: { ...prev[taskId], polling: false, failCount } }
          }
          const backoff = Math.min(pollInterval * Math.pow(2, failCount - 1), 30000)
          if (generation === generationsRef.current[taskId]) {
            timersRef.current[taskId] = setTimeout(fetchStatus, backoff)
          }
          return { ...prev, [taskId]: { ...prev[taskId], failCount } }
        })
      }
    }

    fetchStatus()
  }, [projectId, pollInterval, clearTimer])

  // cleanup on unmount
  useEffect(() => {
    return () => {
      Object.values(timersRef.current).forEach(clearTimeout)
      timersRef.current = {}
      // 卸载后使所有在途轮询回调失效，避免继续请求并在已卸载组件上 setState
      for (const taskId of Object.keys(generationsRef.current)) {
        generationsRef.current[taskId] += 1
      }
    }
  }, [])

  return {
    tasks,
    startPolling,
    stopPolling,
    stopAll,
    removeTask,
    /** Map-style accessors */
    taskList: Object.values(tasks),
    getTask: (taskId: string) => tasks[taskId],
    isAnyPolling: Object.values(tasks).some((t) => t.polling),
  }
}
