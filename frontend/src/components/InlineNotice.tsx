import { useEffect, useState } from 'react'

interface InlineNoticeProps {
  tone?: 'error' | 'success' | 'info'
  title?: string
  message: string
  dismissible?: boolean
  autoHideMs?: number
  onClose?: () => void
}

const TONE_STYLES: Record<NonNullable<InlineNoticeProps['tone']>, string> = {
  error: 'border-red-200 bg-red-50 text-red-900',
  success: 'border-emerald-200 bg-emerald-50 text-emerald-900',
  info: 'border-slate-200 bg-slate-50 text-slate-900',
}

export function InlineNotice({
  tone = 'info',
  title,
  message,
  dismissible = false,
  autoHideMs,
  onClose,
}: InlineNoticeProps) {
  const [visible, setVisible] = useState(true)

  useEffect(() => {
    setVisible(true)
  }, [tone, title, message])

  useEffect(() => {
    if (!autoHideMs || autoHideMs <= 0) {
      return
    }

    const timeoutId = window.setTimeout(() => {
      setVisible(false)
      onClose?.()
    }, autoHideMs)

    return () => window.clearTimeout(timeoutId)
  }, [autoHideMs, onClose, tone, title, message])

  if (!visible) {
    return null
  }

  return (
    <div className={`rounded-lg border px-4 py-3 text-sm ${TONE_STYLES[tone]}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          {title && <div className="font-medium">{title}</div>}
          <div className={title ? 'mt-1' : ''}>{message}</div>
        </div>
        {dismissible && (
          <button
            type="button"
            className="shrink-0 text-xs font-medium opacity-70 transition hover:opacity-100"
            onClick={() => {
              setVisible(false)
              onClose?.()
            }}
          >
            关闭
          </button>
        )}
      </div>
    </div>
  )
}
