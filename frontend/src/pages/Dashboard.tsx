import { useEffect, useState } from 'react'
import { Activity, ArrowDownRight, ArrowUpRight, Flag, Pause, Play, RefreshCw, TrendingUp } from 'lucide-react'

type TradeSide = 'LONG' | 'SHORT'

interface TradeItem {
  id: string
  symbol: string
  side: TradeSide
  leverage: string
  size: number
  pnl: number
  pnlPercent: number
  closedAt: string
}

interface DashboardConfig {
  startingBalance: number
  targetBalance: number
  refreshSeconds: number
  maxPnlPercent: number
  symbols: string[]
}

const defaultConfig: DashboardConfig = {
  startingBalance: 100,
  targetBalance: 100000,
  refreshSeconds: 4,
  maxPnlPercent: 18,
  symbols: ['BTC', 'ETH', 'SOL', 'PEPE', 'DOGE', 'BNB', 'AVAX', 'ORDI', 'WIF', 'ARB', 'NEAR', 'SEI'],
}

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max)
}

function rand(min: number, max: number) {
  return Math.random() * (max - min) + min
}

function pick<T>(items: T[]): T {
  return items[Math.floor(Math.random() * items.length)]
}

function formatMoney(value: number) {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: value >= 1000 ? 0 : 2,
  }).format(value)
}

function formatCompactMoney(value: number) {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    notation: 'compact',
    maximumFractionDigits: 2,
  }).format(value)
}

function formatPercent(value: number) {
  const sign = value > 0 ? '+' : ''
  return `${sign}${value.toFixed(2)}%`
}

function formatTime(date = new Date()) {
  return date.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

function parseSymbols(input: string) {
  return input
    .split(',')
    .map((item) => item.trim().toUpperCase())
    .filter(Boolean)
}

function createNextTrade(balance: number, config: DashboardConfig): { trade: TradeItem; nextBalance: number } {
  const side: TradeSide = Math.random() > 0.45 ? 'LONG' : 'SHORT'
  const isWin = Math.random() > 0.33
  const pnlPercent = isWin
    ? rand(1.2, config.maxPnlPercent)
    : -rand(0.8, Math.max(2, config.maxPnlPercent * 0.55))

  const positionSize = clamp(balance * rand(0.08, 0.22), 25, balance * 0.35 + 20)
  const pnl = positionSize * (pnlPercent / 100)
  const nextBalance = Math.max(20, balance + pnl)

  return {
    nextBalance,
    trade: {
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
      symbol: pick(config.symbols),
      side,
      leverage: `${Math.floor(rand(2, 13))}x`,
      size: positionSize,
      pnl,
      pnlPercent,
      closedAt: formatTime(),
    },
  }
}

function buildSeedState(config: DashboardConfig) {
  let balance = config.startingBalance
  const trades: TradeItem[] = []
  const equityPoints = [balance]

  for (let i = 0; i < 8; i += 1) {
    const { trade, nextBalance } = createNextTrade(balance, config)
    balance = nextBalance
    trades.unshift(trade)
    equityPoints.push(balance)
  }

  return { balance, trades, equityPoints }
}

function buildChartPoints(values: number[]) {
  const width = 760
  const height = 280
  const padding = 18
  const min = Math.min(...values)
  const max = Math.max(...values)
  const spread = Math.max(max - min, 1)

  const points = values.map((value, index) => {
    const x = padding + (index / Math.max(values.length - 1, 1)) * (width - padding * 2)
    const y = height - padding - ((value - min) / spread) * (height - padding * 2)
    return `${x},${y}`
  })

  const area = [`${padding},${height - padding}`, ...points, `${width - padding},${height - padding}`].join(' ')

  return { points: points.join(' '), area, width, height, padding }
}

export default function Dashboard() {
  const [config, setConfig] = useState<DashboardConfig>(defaultConfig)
  const [form, setForm] = useState({
    startingBalance: String(defaultConfig.startingBalance),
    targetBalance: String(defaultConfig.targetBalance),
    refreshSeconds: String(defaultConfig.refreshSeconds),
    maxPnlPercent: String(defaultConfig.maxPnlPercent),
    symbols: defaultConfig.symbols.join(','),
  })
  const [currentBalance, setCurrentBalance] = useState(defaultConfig.startingBalance)
  const [trades, setTrades] = useState<TradeItem[]>([])
  const [equityPoints, setEquityPoints] = useState<number[]>([defaultConfig.startingBalance])
  const [running, setRunning] = useState(true)
  const [lastUpdate, setLastUpdate] = useState('--')

  useEffect(() => {
    const seeded = buildSeedState(defaultConfig)
    setCurrentBalance(seeded.balance)
    setTrades(seeded.trades)
    setEquityPoints(seeded.equityPoints)
    setLastUpdate(formatTime())
  }, [])

  useEffect(() => {
    if (!running) {
      return
    }

    const timer = window.setInterval(() => {
      setCurrentBalance((previousBalance) => {
        const { trade, nextBalance } = createNextTrade(previousBalance, config)

        setTrades((previousTrades) => [trade, ...previousTrades].slice(0, 18))
        setEquityPoints((previousPoints) => [...previousPoints, nextBalance].slice(-36))
        setLastUpdate(formatTime())

        return nextBalance
      })
    }, config.refreshSeconds * 1000)

    return () => window.clearInterval(timer)
  }, [config, running])

  const applyConfig = () => {
    const nextConfig: DashboardConfig = {
      startingBalance: Math.max(10, Number(form.startingBalance) || 100),
      targetBalance: Math.max(100, Number(form.targetBalance) || 100000),
      refreshSeconds: clamp(Number(form.refreshSeconds) || 4, 1, 20),
      maxPnlPercent: clamp(Number(form.maxPnlPercent) || 18, 1, 100),
      symbols: parseSymbols(form.symbols).length ? parseSymbols(form.symbols) : ['BTC', 'ETH', 'SOL'],
    }

    const seeded = buildSeedState(nextConfig)
    setConfig(nextConfig)
    setCurrentBalance(seeded.balance)
    setTrades(seeded.trades)
    setEquityPoints(seeded.equityPoints)
    setLastUpdate(formatTime())
  }

  const start = config.startingBalance
  const profit = currentBalance - start
  const profitPercent = start > 0 ? (profit / start) * 100 : 0
  const winningTrades = trades.filter((trade) => trade.pnl >= 0).length
  const winRate = trades.length ? (winningTrades / trades.length) * 100 : 0
  const progress =
    config.targetBalance > start
      ? ((currentBalance - start) / (config.targetBalance - start)) * 100
      : 0
  const chart = buildChartPoints(equityPoints)

  return (
    <div className="space-y-6 rounded-[28px] border border-sky-400/10 bg-[radial-gradient(circle_at_top_left,_rgba(56,189,248,0.16),_transparent_24%),radial-gradient(circle_at_85%_12%,_rgba(45,212,191,0.14),_transparent_22%),linear-gradient(180deg,_#08111d_0%,_#050b14_100%)] p-6 text-slate-100 shadow-[0_24px_80px_rgba(0,0,0,0.28)]">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div>
          <div className="mb-3 flex flex-wrap gap-2 text-[11px] font-medium uppercase tracking-[0.3em] text-sky-300/80">
            <span className="rounded-full border border-sky-400/20 bg-sky-400/10 px-3 py-1">Arena Dashboard</span>
            <span className="rounded-full border border-amber-400/20 bg-amber-400/10 px-3 py-1 text-amber-300">Simulated Data</span>
          </div>
          <h2 className="text-3xl font-semibold tracking-tight text-white">高频交易风格演示看板</h2>
          <p className="mt-2 max-w-3xl text-sm text-slate-300">
            右侧成交流会按设定节奏自动刷新，左侧参数可随时修改。页面已明确标记为模拟数据，仅用于前端展示和录屏演示。
          </p>
        </div>

        <div className="flex flex-wrap gap-3">
          <button
            onClick={applyConfig}
            className="inline-flex items-center gap-2 rounded-2xl bg-sky-400 px-4 py-2 text-sm font-semibold text-slate-950 transition hover:translate-y-[-1px]"
          >
            <RefreshCw className="h-4 w-4" />
            应用配置
          </button>
          <button
            onClick={() => setRunning((value) => !value)}
            className="inline-flex items-center gap-2 rounded-2xl border border-white/10 bg-white/5 px-4 py-2 text-sm font-semibold text-white transition hover:bg-white/10"
          >
            {running ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
            {running ? '暂停刷新' : '继续刷新'}
          </button>
        </div>
      </div>

      <div className="grid gap-6 2xl:grid-cols-[360px_minmax(0,1fr)]">
        <section className="space-y-4 rounded-[24px] border border-white/10 bg-slate-950/45 p-5 backdrop-blur">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-[11px] uppercase tracking-[0.28em] text-sky-300/70">控制面板</p>
              <h3 className="mt-1 text-lg font-semibold text-white">自定义演示数据</h3>
            </div>
            <span className={`rounded-full px-3 py-1 text-xs font-medium ${running ? 'bg-emerald-400/15 text-emerald-300' : 'bg-slate-400/15 text-slate-300'}`}>
              {running ? '运行中' : '已暂停'}
            </span>
          </div>

          <div className="grid gap-4 sm:grid-cols-2 2xl:grid-cols-1">
            <label className="space-y-2 text-sm text-slate-300">
              <span>起始资金</span>
              <input
                value={form.startingBalance}
                onChange={(event) => setForm((current) => ({ ...current, startingBalance: event.target.value }))}
                type="number"
                min="0"
                step="10"
                className="w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-white outline-none transition focus:border-sky-300/50 focus:bg-white/10"
              />
            </label>

            <label className="space-y-2 text-sm text-slate-300">
              <span>目标资金</span>
              <input
                value={form.targetBalance}
                onChange={(event) => setForm((current) => ({ ...current, targetBalance: event.target.value }))}
                type="number"
                min="0"
                step="100"
                className="w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-white outline-none transition focus:border-sky-300/50 focus:bg-white/10"
              />
            </label>

            <label className="space-y-2 text-sm text-slate-300">
              <span>刷新间隔(秒)</span>
              <input
                value={form.refreshSeconds}
                onChange={(event) => setForm((current) => ({ ...current, refreshSeconds: event.target.value }))}
                type="number"
                min="1"
                max="20"
                step="1"
                className="w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-white outline-none transition focus:border-sky-300/50 focus:bg-white/10"
              />
            </label>

            <label className="space-y-2 text-sm text-slate-300">
              <span>单笔收益上限(%)</span>
              <input
                value={form.maxPnlPercent}
                onChange={(event) => setForm((current) => ({ ...current, maxPnlPercent: event.target.value }))}
                type="number"
                min="1"
                max="100"
                step="1"
                className="w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-white outline-none transition focus:border-sky-300/50 focus:bg-white/10"
              />
            </label>
          </div>

          <label className="block space-y-2 text-sm text-slate-300">
            <span>币种池</span>
            <textarea
              value={form.symbols}
              onChange={(event) => setForm((current) => ({ ...current, symbols: event.target.value }))}
              rows={6}
              className="w-full rounded-[20px] border border-white/10 bg-white/5 px-4 py-3 text-white outline-none transition focus:border-sky-300/50 focus:bg-white/10"
            />
          </label>

          <div className="rounded-[20px] border border-sky-300/10 bg-sky-300/5 p-4 text-sm text-slate-300">
            <p className="font-medium text-sky-200">当前配置</p>
            <div className="mt-3 grid grid-cols-2 gap-3 text-xs text-slate-300/90">
              <div>
                <p className="text-slate-400">刷新频率</p>
                <p className="mt-1 font-medium text-white">每 {config.refreshSeconds}s</p>
              </div>
              <div>
                <p className="text-slate-400">币种数量</p>
                <p className="mt-1 font-medium text-white">{config.symbols.length} 个</p>
              </div>
              <div>
                <p className="text-slate-400">起始权益</p>
                <p className="mt-1 font-medium text-white">{formatMoney(config.startingBalance)}</p>
              </div>
              <div>
                <p className="text-slate-400">目标权益</p>
                <p className="mt-1 font-medium text-white">{formatCompactMoney(config.targetBalance)}</p>
              </div>
            </div>
          </div>
        </section>

        <section className="space-y-6">
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <div className="rounded-[24px] border border-white/10 bg-slate-950/45 p-5 backdrop-blur">
              <div className="flex items-center justify-between text-slate-400">
                <span className="text-sm">当前权益</span>
                <Activity className="h-5 w-5 text-sky-300" />
              </div>
              <p className="mt-4 text-3xl font-semibold text-white">{formatMoney(currentBalance)}</p>
              <p className={`mt-2 text-sm font-medium ${profit >= 0 ? 'text-emerald-300' : 'text-rose-300'}`}>
                {formatPercent(profitPercent)}
              </p>
            </div>

            <div className="rounded-[24px] border border-white/10 bg-slate-950/45 p-5 backdrop-blur">
              <div className="flex items-center justify-between text-slate-400">
                <span className="text-sm">总收益</span>
                {profit >= 0 ? <ArrowUpRight className="h-5 w-5 text-emerald-300" /> : <ArrowDownRight className="h-5 w-5 text-rose-300" />}
              </div>
              <p className="mt-4 text-3xl font-semibold text-white">
                {profit >= 0 ? '+' : '-'}{formatMoney(Math.abs(profit))}
              </p>
              <p className={`mt-2 text-sm font-medium ${profit >= 0 ? 'text-emerald-300' : 'text-rose-300'}`}>
                {formatPercent(profitPercent)}
              </p>
            </div>

            <div className="rounded-[24px] border border-white/10 bg-slate-950/45 p-5 backdrop-blur">
              <div className="flex items-center justify-between text-slate-400">
                <span className="text-sm">胜率</span>
                <TrendingUp className="h-5 w-5 text-cyan-300" />
              </div>
              <p className="mt-4 text-3xl font-semibold text-white">{winRate.toFixed(1)}%</p>
              <p className="mt-2 text-sm text-slate-400">{trades.length} 笔已完成交易</p>
            </div>

            <div className="rounded-[24px] border border-white/10 bg-slate-950/45 p-5 backdrop-blur">
              <div className="flex items-center justify-between text-slate-400">
                <span className="text-sm">目标进度</span>
                <Flag className="h-5 w-5 text-amber-300" />
              </div>
              <p className="mt-4 text-3xl font-semibold text-white">{clamp(progress, 0, 999).toFixed(1)}%</p>
              <p className="mt-2 text-sm text-slate-400">{formatCompactMoney(currentBalance)} / {formatCompactMoney(config.targetBalance)}</p>
            </div>
          </div>

          <div className="grid gap-5 xl:grid-cols-[minmax(0,1.15fr)_400px]">
            <div className="rounded-[24px] border border-white/10 bg-slate-950/45 p-5 backdrop-blur">
              <div className="mb-4 flex items-start justify-between gap-4">
                <div>
                  <p className="text-[11px] uppercase tracking-[0.28em] text-sky-300/70">权益曲线</p>
                  <h3 className="mt-1 text-lg font-semibold text-white">Balance Trajectory</h3>
                </div>
                <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 font-mono text-xs text-slate-300">
                  {lastUpdate}
                </span>
              </div>

              <svg viewBox={`0 0 ${chart.width} ${chart.height}`} className="h-[300px] w-full overflow-visible">
                <defs>
                  <linearGradient id="arena-line" x1="0%" y1="0%" x2="100%" y2="0%">
                    <stop offset="0%" stopColor="#38bdf8" />
                    <stop offset="100%" stopColor="#2dd4bf" />
                  </linearGradient>
                  <linearGradient id="arena-fill" x1="0%" y1="0%" x2="0%" y2="100%">
                    <stop offset="0%" stopColor="rgba(56, 189, 248, 0.30)" />
                    <stop offset="100%" stopColor="rgba(56, 189, 248, 0.02)" />
                  </linearGradient>
                </defs>
                <line x1={chart.padding} y1={chart.height - chart.padding} x2={chart.width - chart.padding} y2={chart.height - chart.padding} stroke="rgba(255,255,255,0.12)" />
                <line x1={chart.padding} y1={chart.padding} x2={chart.padding} y2={chart.height - chart.padding} stroke="rgba(255,255,255,0.12)" />
                <polygon points={chart.area} fill="url(#arena-fill)" />
                <polyline points={chart.points} fill="none" stroke="url(#arena-line)" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </div>

            <div className="rounded-[24px] border border-white/10 bg-slate-950/45 p-5 backdrop-blur">
              <div className="mb-4 flex items-start justify-between gap-4">
                <div>
                  <p className="text-[11px] uppercase tracking-[0.28em] text-sky-300/70">已完成交易</p>
                  <h3 className="mt-1 text-lg font-semibold text-white">Completed Trades</h3>
                </div>
                <span className="rounded-full border border-emerald-400/15 bg-emerald-400/10 px-3 py-1 font-mono text-xs text-emerald-300">
                  every {config.refreshSeconds}s
                </span>
              </div>

              <div className="space-y-3">
                {trades.map((trade) => {
                  const positive = trade.pnl >= 0
                  return (
                    <div
                      key={trade.id}
                      className="grid grid-cols-[minmax(0,1fr)_auto] gap-3 rounded-[20px] border border-white/8 bg-white/[0.035] p-4 transition duration-300 hover:border-sky-300/20 hover:bg-white/[0.055]"
                    >
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="text-sm font-semibold text-white">{trade.symbol} / USDT</p>
                          <span className={`rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] ${trade.side === 'LONG' ? 'bg-emerald-400/15 text-emerald-300' : 'bg-rose-400/15 text-rose-300'}`}>
                            {trade.side}
                          </span>
                        </div>
                        <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-xs text-slate-400">
                          <span>{trade.leverage}</span>
                          <span>Size {formatMoney(trade.size)}</span>
                          <span>{trade.closedAt}</span>
                        </div>
                      </div>

                      <div className="text-right">
                        <p className={`text-base font-semibold ${positive ? 'text-emerald-300' : 'text-rose-300'}`}>
                          {positive ? '+' : '-'}{formatMoney(Math.abs(trade.pnl))}
                        </p>
                        <p className={`mt-1 text-xs font-medium ${positive ? 'text-emerald-200' : 'text-rose-200'}`}>
                          {formatPercent(trade.pnlPercent)}
                        </p>
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          </div>
        </section>
      </div>
    </div>
  )
}
