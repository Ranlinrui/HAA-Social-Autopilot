import { Button } from '@/components/ui/button'

export interface TwitterRiskStateLike {
  risk_stage?: string
  write_blocked?: boolean
  write_block_reason?: string
  write_resume_seconds?: number
  last_risk_error?: string
  read_only_until?: string
  auth_backoff_until?: string
  recovery_until?: string
}

export interface TwitterRiskAccountLike extends TwitterRiskStateLike {
  risk_account_key: string
  is_persisted?: boolean
  is_active_display_only?: boolean
}

const RISK_STAGE_LABELS: Record<string, string> = {
  normal: '正常',
  auth_cooldown: '认证冷却',
  read_only: '只读保护',
  recovery_cautious: '恢复期-谨慎',
  recovery_limited: '恢复期-限流',
}

export function formatRiskStage(stage?: string) {
  return RISK_STAGE_LABELS[stage || ''] || stage || '未知'
}

export function formatRiskTime(value?: string) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', { hour12: false })
}

export function getRiskResumeMinutes(value?: number) {
  return Math.max(1, Math.ceil((value || 0) / 60))
}

export function getWriteBlockedReason(state?: TwitterRiskStateLike | null) {
  return state?.write_block_reason || '当前账号处于写入保护期'
}

export function TwitterRiskBanner({ state }: { state?: TwitterRiskStateLike | null }) {
  if (!state) return null

  if (state.write_blocked) {
    const resumeMinutes = getRiskResumeMinutes(state.write_resume_seconds)
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900">
        <div className="font-medium">当前处于写入保护期</div>
        <div className="mt-1">
          {getWriteBlockedReason(state)}
          {`，预计约 ${resumeMinutes} 分钟后再试。`}
        </div>
        {(state.read_only_until || state.auth_backoff_until) && (
          <div className="mt-1 text-xs text-red-800">
            截止时间：{formatRiskTime(state.read_only_until || state.auth_backoff_until)}
          </div>
        )}
        {state.last_risk_error && (
          <div className="mt-1 text-xs text-red-800">
            最近一次风险错误：{state.last_risk_error}
          </div>
        )}
      </div>
    )
  }

  if (state.risk_stage && state.risk_stage !== 'normal') {
    const resumeMinutes = getRiskResumeMinutes(state.write_resume_seconds)
    return (
      <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
        当前账号处于恢复阶段：<span className="font-medium">{formatRiskStage(state.risk_stage)}</span>
        {state.write_resume_seconds ? `，恢复窗口约剩 ${resumeMinutes} 分钟。` : '，系统会自动限流发帖/回复/转推。'}
        {state.recovery_until && (
          <div className="mt-1 text-xs text-amber-800">
            预计恢复截止时间：{formatRiskTime(state.recovery_until)}
          </div>
        )}
      </div>
    )
  }

  return null
}

export function TwitterRiskAccountPanel({
  items,
  activeUsername,
  resettingKey,
  onReset,
}: {
  items: TwitterRiskAccountLike[]
  activeUsername?: string
  resettingKey?: string | null
  onReset: (accountKey: string) => void
}) {
  if (!items.length) return null

  return (
    <div className="pt-4 border-t space-y-3">
      <div>
        <label className="text-sm font-medium">账号风险面板</label>
        <p className="text-xs text-muted-foreground mt-1">
          展示当前进程内记录过的账号风险状态。切换 Cookie 测试时，可以直接看不同账号是否仍处于恢复期。
        </p>
      </div>
      <div className="space-y-2">
        {items.map((item) => {
          const minutes = getRiskResumeMinutes(item.write_resume_seconds)
          const tone =
            item.write_blocked
              ? 'border-red-200 bg-red-50 text-red-900'
              : item.risk_stage !== 'normal'
                ? 'border-amber-200 bg-amber-50 text-amber-900'
                : 'border-slate-200 bg-slate-50 text-slate-800'
          const canReset = !!item.is_persisted

          return (
            <div key={item.risk_account_key} className={`rounded-lg border px-4 py-3 text-sm ${tone}`}>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="font-medium">
                    @{item.risk_account_key}
                    {activeUsername === item.risk_account_key ? ' · 当前活跃账号' : ''}
                  </div>
                  <div className="mt-1 text-xs opacity-80">
                    {item.is_active_display_only
                      ? '仅展示当前活跃账号状态'
                      : item.is_persisted
                        ? '存在真实风控记录'
                        : '当前无真实风控记录'}
                  </div>
                </div>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => onReset(item.risk_account_key)}
                  disabled={!canReset || resettingKey === item.risk_account_key}
                >
                  {resettingKey === item.risk_account_key ? '重置中' : '重置风控'}
                </Button>
              </div>
              <div className="mt-1">
                阶段：{formatRiskStage(item.risk_stage)}
                {item.write_blocked
                  ? `，写入受限，预计约 ${minutes} 分钟后恢复`
                  : item.risk_stage !== 'normal' && item.write_resume_seconds
                    ? `，恢复窗口约剩 ${minutes} 分钟`
                    : '，当前可写'}
              </div>
              {(item.read_only_until || item.auth_backoff_until || item.recovery_until) && (
                <div className="mt-1 text-xs opacity-90">
                  截止时间：{formatRiskTime(item.read_only_until || item.auth_backoff_until || item.recovery_until)}
                </div>
              )}
              {item.write_block_reason && (
                <div className="mt-1 text-xs opacity-90">{item.write_block_reason}</div>
              )}
              {item.last_risk_error && (
                <div className="mt-1 text-xs opacity-90">最近错误：{item.last_risk_error}</div>
              )}
              {!canReset && (
                <div className="mt-1 text-xs opacity-80">当前没有可清理的真实风控记录，因此无需重置。</div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
