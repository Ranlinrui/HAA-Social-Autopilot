import { Button } from '@/components/ui/button'

interface InlineConfirmProps {
  title: string
  message: string
  confirmLabel?: string
  cancelLabel?: string
  busy?: boolean
  onConfirm: () => void
  onCancel: () => void
}

export function InlineConfirm({
  title,
  message,
  confirmLabel = '确认',
  cancelLabel = '取消',
  busy = false,
  onConfirm,
  onCancel,
}: InlineConfirmProps) {
  return (
    <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-950">
      <div className="font-medium">{title}</div>
      <div className="mt-1">{message}</div>
      <div className="mt-3 flex gap-2">
        <Button type="button" size="sm" variant="destructive" disabled={busy} onClick={onConfirm}>
          {confirmLabel}
        </Button>
        <Button type="button" size="sm" variant="outline" disabled={busy} onClick={onCancel}>
          {cancelLabel}
        </Button>
      </div>
    </div>
  )
}
