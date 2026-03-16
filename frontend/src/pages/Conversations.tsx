import { useState, useEffect } from 'react'
import { RefreshCw, Send, Loader2, ExternalLink, Bot, User, Settings, Power, PowerOff } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import api from '@/services/api'

interface HistoryTurn {
  role: 'us' | 'them'
  text: string
  tweet_id: string
  at: string
}

interface Thread {
  id: number
  root_tweet_id: string
  root_tweet_text?: string
  our_reply_id: string
  our_reply_text?: string
  latest_mention_id: string
  latest_mention_text: string
  from_username: string
  mention_created_at?: string
  history?: HistoryTurn[]
  status: string
  mode: string
  draft_reply?: string
  replied_tweet_id?: string
  replied_text?: string
  replied_at?: string
  auto_error?: string
  created_at?: string
}

interface ConvSettings {
  mode: string
  poll_interval: number
  auto_reply_delay: number
  enabled: boolean
}

interface Stats {
  total_threads: number
  pending_threads: number
  mode: string
  enabled: boolean
}

const STATUS_LABELS: Record<string, { label: string; className: string }> = {
  pending: { label: '待回复', className: 'bg-orange-50 text-orange-700' },
  auto_replied: { label: '已自动回复', className: 'bg-purple-50 text-purple-700' },
  manual_replied: { label: '已手动回复', className: 'bg-green-50 text-green-700' },
  ignored: { label: '已忽略', className: 'bg-gray-50 text-gray-500' },
}

export default function Conversations() {
  const [threads, setThreads] = useState<Thread[]>([])
  const [stats, setStats] = useState<Stats | null>(null)
  const [settings, setSettings] = useState<ConvSettings | null>(null)
  const [loading, setLoading] = useState(true)
  const [filterStatus, setFilterStatus] = useState<string>('pending')
  const [showSettings, setShowSettings] = useState(false)

  // Per-thread state
  const [drafts, setDrafts] = useState<Record<number, string>>({})
  const [generating, setGenerating] = useState<Record<number, boolean>>({})
  const [sending, setSending] = useState<Record<number, boolean>>({})
  const [errors, setErrors] = useState<Record<number, string>>({})
  const [expanded, setExpanded] = useState<Record<number, boolean>>({})

  // Settings edit state
  const [editSettings, setEditSettings] = useState<Partial<ConvSettings>>({})
  const [savingSettings, setSavingSettings] = useState(false)

  useEffect(() => {
    loadAll()
    const interval = setInterval(loadAll, 30000)
    return () => clearInterval(interval)
  }, [filterStatus])

  const loadAll = async () => {
    try {
      const [threadsRes, statsRes, settingsRes] = await Promise.all([
        api.get(`/conversation/threads?status=${filterStatus}&limit=50`),
        api.get('/conversation/stats'),
        api.get('/conversation/settings'),
      ])
      setThreads(threadsRes.data)
      setStats(statsRes.data)
      setSettings(settingsRes.data)
      setEditSettings(settingsRes.data)
      // Pre-fill drafts from existing draft_reply
      const newDrafts: Record<number, string> = {}
      for (const t of threadsRes.data as Thread[]) {
        if (t.draft_reply && !drafts[t.id]) {
          newDrafts[t.id] = t.draft_reply
        }
      }
      if (Object.keys(newDrafts).length > 0) {
        setDrafts(prev => ({ ...prev, ...newDrafts }))
      }
    } catch (e) {
      console.error('Failed to load conversations:', e)
    } finally {
      setLoading(false)
    }
  }

  const handleGenerateDraft = async (thread: Thread) => {
    setGenerating(prev => ({ ...prev, [thread.id]: true }))
    setErrors(prev => ({ ...prev, [thread.id]: '' }))
    try {
      const res = await api.post(`/conversation/threads/${thread.id}/generate-draft`)
      setDrafts(prev => ({ ...prev, [thread.id]: res.data.draft }))
    } catch (e: any) {
      setErrors(prev => ({ ...prev, [thread.id]: e.response?.data?.detail || 'Failed to generate' }))
    } finally {
      setGenerating(prev => ({ ...prev, [thread.id]: false }))
    }
  }

  const handleSendReply = async (thread: Thread) => {
    const content = drafts[thread.id]
    if (!content?.trim()) return
    setSending(prev => ({ ...prev, [thread.id]: true }))
    setErrors(prev => ({ ...prev, [thread.id]: '' }))
    try {
      await api.post(`/conversation/threads/${thread.id}/reply`, { content })
      setDrafts(prev => ({ ...prev, [thread.id]: '' }))
      await loadAll()
    } catch (e: any) {
      setErrors(prev => ({ ...prev, [thread.id]: e.response?.data?.detail || 'Failed to send' }))
    } finally {
      setSending(prev => ({ ...prev, [thread.id]: false }))
    }
  }

  const handleIgnore = async (threadId: number) => {
    try {
      await api.post(`/conversation/threads/${threadId}/ignore`)
      await loadAll()
    } catch (e) {
      alert('Failed to ignore thread')
    }
  }

  const handleToggleMode = async (thread: Thread) => {
    const newMode = thread.mode === 'auto' ? 'manual' : 'auto'
    try {
      await api.patch(`/conversation/threads/${thread.id}/mode`, { mode: newMode })
      await loadAll()
    } catch (e) {
      alert('Failed to update mode')
    }
  }

  const handleSaveSettings = async () => {
    setSavingSettings(true)
    try {
      await api.patch('/conversation/settings', editSettings)
      await loadAll()
      setShowSettings(false)
    } catch (e: any) {
      alert(e.response?.data?.detail || 'Failed to save settings')
    } finally {
      setSavingSettings(false)
    }
  }

  const handleToggleEnabled = async () => {
    if (!settings) return
    try {
      await api.patch('/conversation/settings', { enabled: !settings.enabled })
      await loadAll()
    } catch (e) {
      alert('Failed to toggle')
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    )
  }

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">对话跟进</h1>
          <p className="text-muted-foreground mt-1">管理别人回复我们评论后的跟进对话</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={handleToggleEnabled}>
            {settings?.enabled ? <PowerOff className="h-4 w-4 mr-1" /> : <Power className="h-4 w-4 mr-1" />}
            {settings?.enabled ? '暂停轮询' : '启动轮询'}
          </Button>
          <Button variant="outline" size="sm" onClick={() => setShowSettings(!showSettings)}>
            <Settings className="h-4 w-4 mr-1" />
            设置
          </Button>
        </div>
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card>
            <CardContent className="pt-6">
              <p className="text-sm text-muted-foreground">待回复</p>
              <p className="text-2xl font-bold">{stats.pending_threads}</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <p className="text-sm text-muted-foreground">总对话数</p>
              <p className="text-2xl font-bold">{stats.total_threads}</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <p className="text-sm text-muted-foreground">全局模式</p>
              <p className="text-sm font-medium mt-1">
                {stats.mode === 'auto' ? (
                  <span className="flex items-center gap-1"><Bot className="h-4 w-4 text-purple-500" />自动</span>
                ) : (
                  <span className="flex items-center gap-1"><User className="h-4 w-4 text-blue-500" />手动</span>
                )}
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <p className="text-sm text-muted-foreground">轮询状态</p>
              <p className="text-sm font-medium mt-1">{stats.enabled ? '运行中' : '已暂停'}</p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Settings Panel */}
      {showSettings && settings && (
        <Card>
          <CardHeader>
            <CardTitle>对话跟进设置</CardTitle>
            <CardDescription>配置全局模式和轮询参数</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center gap-6 flex-wrap">
              <div>
                <label className="text-sm font-medium block mb-1">全局模式</label>
                <select
                  className="px-3 py-2 border rounded-md text-sm"
                  value={editSettings.mode || 'manual'}
                  onChange={e => setEditSettings(prev => ({ ...prev, mode: e.target.value }))}
                >
                  <option value="manual">手动 - 所有新对话需人工审核</option>
                  <option value="auto">自动 - LLM 生成后延迟发出</option>
                </select>
              </div>
              <div>
                <label className="text-sm font-medium block mb-1">轮询间隔（秒）</label>
                <input
                  type="number"
                  min={60}
                  className="w-24 px-3 py-2 border rounded-md text-sm"
                  value={editSettings.poll_interval || 180}
                  onChange={e => setEditSettings(prev => ({ ...prev, poll_interval: Number(e.target.value) }))}
                />
              </div>
              <div>
                <label className="text-sm font-medium block mb-1">自动回复基础延迟（秒）</label>
                <input
                  type="number"
                  min={30}
                  className="w-24 px-3 py-2 border rounded-md text-sm"
                  value={editSettings.auto_reply_delay || 120}
                  onChange={e => setEditSettings(prev => ({ ...prev, auto_reply_delay: Number(e.target.value) }))}
                />
              </div>
            </div>
            <p className="text-xs text-muted-foreground">
              自动模式下，系统检测到新回复后会预生成草稿，延迟后自动发出（延迟会随机浮动模拟真人）。手动模式下，新回复会出现在待回复列表等待你处理。
            </p>
            <Button size="sm" onClick={handleSaveSettings} disabled={savingSettings}>
              {savingSettings ? <Loader2 className="h-3.5 w-3.5 animate-spin mr-1" /> : null}
              保存
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Filter Tabs */}
      <div className="flex gap-2 border-b pb-2">
        {['pending', 'auto_replied', 'manual_replied', 'ignored'].map(s => (
          <button
            key={s}
            onClick={() => setFilterStatus(s)}
            className={`px-3 py-1.5 text-sm rounded-md transition-colors ${filterStatus === s ? 'bg-primary text-primary-foreground' : 'hover:bg-accent'}`}
          >
            {STATUS_LABELS[s]?.label || s}
          </button>
        ))}
      </div>

      {/* Thread List */}
      <div className="space-y-4">
        {threads.map(thread => (
          <Card key={thread.id} className={thread.status === 'pending' ? 'border-orange-200' : ''}>
            <CardContent className="pt-4 space-y-3">
              {/* Header */}
              <div className="flex items-start justify-between gap-2">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-medium">@{thread.from_username}</span>
                  <Badge variant="outline" className={STATUS_LABELS[thread.status]?.className}>
                    {STATUS_LABELS[thread.status]?.label || thread.status}
                  </Badge>
                  <Badge variant="outline" className={thread.mode === 'auto' ? 'bg-purple-50 text-purple-700' : 'bg-blue-50 text-blue-700'}>
                    {thread.mode === 'auto' ? <><Bot className="h-3 w-3 mr-1" />自动</> : <><User className="h-3 w-3 mr-1" />手动</>}
                  </Badge>
                  {thread.mention_created_at && (
                    <span className="text-xs text-muted-foreground">
                      {new Date(thread.mention_created_at + 'Z').toLocaleString('zh-CN')}
                    </span>
                  )}
                </div>
                <div className="flex gap-1 shrink-0">
                  <button
                    onClick={() => handleToggleMode(thread)}
                    className="px-2 py-1 text-xs border rounded hover:bg-accent"
                    title="切换此对话的模式"
                  >
                    切换模式
                  </button>
                  <a
                    href={`https://x.com/${thread.from_username}/status/${thread.latest_mention_id}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="px-2 py-1 text-xs border rounded hover:bg-accent flex items-center gap-1"
                  >
                    <ExternalLink className="h-3 w-3" />
                  </a>
                </div>
              </div>

              {/* Latest mention */}
              <div className="p-3 bg-orange-50 rounded-md text-sm">
                <p className="text-xs text-orange-600 mb-1">@{thread.from_username} 回复了我们：</p>
                <p>{thread.latest_mention_text}</p>
              </div>

              {/* Conversation history toggle */}
              {thread.history && thread.history.length > 0 && (
                <div>
                  <button
                    onClick={() => setExpanded(prev => ({ ...prev, [thread.id]: !prev[thread.id] }))}
                    className="text-xs text-blue-600 hover:underline"
                  >
                    {expanded[thread.id] ? '收起' : `查看完整对话 (${thread.history.length} 条)`}
                  </button>
                  {expanded[thread.id] && (
                    <div className="mt-2 space-y-2 border-l-2 border-gray-200 pl-3">
                      {thread.history.map((turn, i) => (
                        <div key={i} className={`text-sm p-2 rounded ${turn.role === 'us' ? 'bg-blue-50' : 'bg-gray-50'}`}>
                          <p className="text-xs text-muted-foreground mb-0.5">
                            {turn.role === 'us' ? 'Me' : `@${thread.from_username}`}
                            {turn.at && ` · ${new Date(turn.at).toLocaleString('zh-CN')}`}
                          </p>
                          <p>{turn.text}</p>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Already replied */}
              {thread.replied_text && (
                <div className="p-2 bg-green-50 rounded text-sm">
                  <p className="text-xs text-green-700 mb-1">我们的回复：</p>
                  <p>{thread.replied_text}</p>
                </div>
              )}

              {/* Auto error */}
              {thread.auto_error && (
                <p className="text-xs text-destructive">自动回复失败: {thread.auto_error}</p>
              )}

              {/* Reply panel for pending threads */}
              {thread.status === 'pending' && (
                <div className="space-y-2 pt-1">
                  <div className="relative">
                    <textarea
                      className="w-full px-3 py-2 text-sm rounded-md border bg-background focus:outline-none focus:ring-2 focus:ring-primary resize-none"
                      rows={3}
                      placeholder="点击「AI 生成」获取回复草稿，或直接输入..."
                      value={drafts[thread.id] || ''}
                      onChange={e => setDrafts(prev => ({ ...prev, [thread.id]: e.target.value }))}
                      maxLength={280}
                    />
                    <span className={`absolute bottom-2 right-2 text-xs ${(drafts[thread.id]?.length || 0) > 260 ? 'text-destructive' : 'text-muted-foreground'}`}>
                      {drafts[thread.id]?.length || 0}/280
                    </span>
                  </div>
                  {errors[thread.id] && (
                    <p className="text-xs text-destructive">{errors[thread.id]}</p>
                  )}
                  <div className="flex gap-2 flex-wrap">
                    <button
                      onClick={() => handleGenerateDraft(thread)}
                      disabled={generating[thread.id]}
                      className="flex items-center gap-1.5 px-3 py-1.5 text-sm border rounded-md hover:bg-accent disabled:opacity-50"
                    >
                      {generating[thread.id] ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
                      AI 生成
                    </button>
                    <button
                      onClick={() => handleSendReply(thread)}
                      disabled={sending[thread.id] || !drafts[thread.id]?.trim()}
                      className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-primary text-primary-foreground rounded-md hover:bg-primary/90 disabled:opacity-50"
                    >
                      {sending[thread.id] ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Send className="h-3.5 w-3.5" />}
                      发送回复
                    </button>
                    <button
                      onClick={() => handleIgnore(thread.id)}
                      className="flex items-center gap-1.5 px-3 py-1.5 text-sm border rounded-md hover:bg-accent text-muted-foreground"
                    >
                      忽略
                    </button>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        ))}
        {threads.length === 0 && (
          <p className="text-center text-muted-foreground py-12">
            {filterStatus === 'pending' ? '暂无待回复的对话' : '暂无记录'}
          </p>
        )}
      </div>
    </div>
  )
}
