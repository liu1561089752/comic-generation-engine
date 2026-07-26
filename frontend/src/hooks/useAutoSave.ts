import { useCallback, useEffect, useRef, useState } from 'react'

type SaveStatus = 'saved' | 'saving' | 'unsaved' | 'error'

interface UseAutoSaveOptions {
  onSave: () => Promise<void>
}

/**
 * 手动保存 Hook —— 不包含任何自动定时保存逻辑。
 * 仅提供 triggerSave() 供按钮点击或 AI 请求完成后调用。
 *
 * D54: 增加 markDirty() 追踪未保存修改，useBeforeUnload 在有未保存修改时生效。
 */
export function useAutoSave({ onSave }: UseAutoSaveOptions) {
  const [saveStatus, setSaveStatus] = useState<SaveStatus>('saved')
  // D54: 用 ref 缓存 dirty 状态，避免频繁 markDirty 触发重渲染
  const dirtyRef = useRef(false)

  const markDirty = useCallback(() => {
    dirtyRef.current = true
    setSaveStatus(prev => prev === 'saving' ? prev : 'unsaved')
  }, [])

  const triggerSave = useCallback(async () => {
    setSaveStatus('saving')
    try {
      await onSave()
      dirtyRef.current = false
      setSaveStatus('saved')
    } catch {
      setSaveStatus('error')
    }
  }, [onSave])

  return { saveStatus, triggerSave, markDirty }
}

// Beforeunload hook
export function useBeforeUnload(shouldWarn: boolean) {
  useEffect(() => {
    if (!shouldWarn) return

    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault()
      e.returnValue = ''
    }

    window.addEventListener('beforeunload', handler)
    return () => window.removeEventListener('beforeunload', handler)
  }, [shouldWarn])
}
