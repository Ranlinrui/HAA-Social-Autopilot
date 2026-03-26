import type { ReactNode } from 'react'
import { Loader2 } from 'lucide-react'
import { Button, type ButtonProps } from '@/components/ui/button'

interface TwitterGuardedButtonProps extends Omit<ButtonProps, 'children'> {
  label: ReactNode
  icon?: ReactNode
  loading?: boolean
  loadingLabel?: ReactNode
  writeBlocked?: boolean
  writeBlockedReason?: string
}

export function TwitterGuardedButton({
  label,
  icon,
  loading,
  loadingLabel,
  writeBlocked,
  writeBlockedReason,
  disabled,
  title,
  className,
  ...props
}: TwitterGuardedButtonProps) {
  const isDisabled = !!disabled || !!writeBlocked
  const resolvedTitle = writeBlocked ? (writeBlockedReason || '当前账号处于写入保护期') : title

  return (
    <Button
      {...props}
      disabled={isDisabled}
      title={resolvedTitle}
      className={className}
    >
      {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : icon}
      {loading ? (loadingLabel || label) : label}
    </Button>
  )
}
