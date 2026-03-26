import { useState, useEffect } from 'react'
import { Plus, Trash2, Power, PowerOff, Bell, MessageSquare, TrendingUp, RefreshCw, Send, Loader2, ExternalLink, Repeat2, Bot, Settings } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import api, { formatTwitterActionError } from '@/services/api'
import { InlineConfirm } from '@/components/InlineConfirm'
import { InlineNotice } from '@/components/InlineNotice'
import { TwitterRiskBanner, getWriteBlockedReason, type TwitterRiskStateLike } from '@/components/TwitterRiskStatus'
import { TwitterGuardedButton } from '@/components/TwitterGuardedButton'

interface MonitoredAccount {
  id: number
  username: string
  user_id?: string
  display_name?: string
  priority: number
  last_tweet_id?: string
  last_checked_at?: string
  is_active: boolean
  auto_engage: boolean
  engage_action: string
  engage_delay: number
  created_at: string
}

interface Notification {
  id: number
  account_id: number
  tweet_id: string
  tweet_text: string
  tweet_url: string
  author_username: string
  author_name: string
  tweet_created_at: string
  notified_at: string
  is_commented: boolean
  comment_text?: string
  commented_at?: string
  auto_engage_status?: string
  auto_engage_error?: string
}

interface Stats extends TwitterRiskStateLike {
  total_accounts: number
  active_accounts: number
  total_notifications: number
  commented_notifications: number
  uncommented_notifications: number
  today_notifications: number
  monitor_running: boolean
  backoff_seconds?: number
  backoff_until?: string
  read_only_until?: string
  auth_backoff_until?: string
  recovery_until?: string
}

export default function Monitor() {
  const [accounts, setAccounts] = useState<MonitoredAccount[]>([])
  const [notifications, setNotifications] = useState<Notification[]>([])
  const [stats, setStats] = useState<Stats | null>(null)
  const [newUsername, setNewUsername] = useState('')
  const [newPriority, setNewPriority] = useState(2)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')
  const [actionMessage, setActionMessage] = useState<{ tone: 'error' | 'success' | 'info'; title: string; message: string } | null>(null)
  const [adding, setAdding] = useState(false)
  const [pendingDeleteAccountId, setPendingDeleteAccountId] = useState<number | null>(null)
  const [pendingRetweetNotifId, setPendingRetweetNotifId] = useState<number | null>(null)

  // Auto-engage config panel state per account
  const [engagePanel, setEngagePanel] = useState<Record<number, boolean>>({})
  const [engageConfig, setEngageConfig] = useState<Record<number, { auto_engage: boolean; engage_action: string; engage_delay: number }>>({})
  const [savingEngage, setSavingEngage] = useState<Record<number, boolean>>({})

  // AI reply states
  const [replyDrafts, setReplyDrafts] = useState<Record<number, string>>({})
  const [generating, setGenerating] = useState<Record<number, boolean>>({})
  const [sending, setSending] = useState<Record<number, boolean>>({})
  const [quoting, setQuoting] = useState<Record<number, boolean>>({})
  const [retweeting, setRetweeting] = useState<Record<number, boolean>>({})
  const [replyErrors, setReplyErrors] = useState<Record<number, string>>({})
  // 'reply' | 'quote' | null - which action panel is open
  const [activePanel, setActivePanel] = useState<Record<number, 'reply' | 'quote' | null>>({})
  const writeBlockedReason = getWriteBlockedReason(stats)

  useEffect(() => {
    loadData()
    const interval = setInterval(loadData, 30000) // Refresh every 30s
    return () => clearInterval(interval)
  }, [])

  const loadData = async () => {
    let hasFailure = false

    try {
      setLoadError('')
      const [accountsRes, notificationsRes, statsRes] = await Promise.allSettled([
        api.get('/monitor/accounts'),
        api.get('/monitor/notifications?limit=50'),
        api.get('/monitor/stats')
      ])

      if (accountsRes.status === 'fulfilled') {
        setAccounts(accountsRes.value.data)
        const configs: Record<number, { auto_engage: boolean; engage_action: string; engage_delay: number }> = {}
        for (const acc of accountsRes.value.data) {
          configs[acc.id] = { auto_engage: acc.auto_engage, engage_action: acc.engage_action, engage_delay: acc.engage_delay }
        }
        setEngageConfig(configs)
      } else {
        hasFailure = true
      }

      if (notificationsRes.status === 'fulfilled') {
        setNotifications(notificationsRes.value.data)
      } else {
        hasFailure = true
      }

      if (statsRes.status === 'fulfilled') {
        setStats(statsRes.value.data)
      } else {
        hasFailure = true
      }

      if (hasFailure) {
        const firstError =
          accountsRes.status === 'rejected'
            ? accountsRes.reason
            : notificationsRes.status === 'rejected'
              ? notificationsRes.reason
              : statsRes.status === 'rejected'
                ? statsRes.reason
                : null
        setLoadError(formatTwitterActionError(firstError, '部分监控数据加载失败'))
      }
    } catch (error) {
      console.error('Failed to load data:', error)
      setLoadError(formatTwitterActionError(error, '监控数据加载失败'))
    } finally {
      setLoading(false)
    }
  }

  const handleAddAccount = async () => {
    if (!newUsername.trim()) return
    setAdding(true)
    try {
      await api.post('/monitor/accounts', {
        username: newUsername.trim(),
        priority: newPriority
      })
      setNewUsername('')
      setNewPriority(2)
      await loadData()
      setActionMessage({ tone: 'success', title: '监控账号已添加', message: `@${newUsername.trim()} 已加入监控列表。` })
    } catch (error: any) {
      setActionMessage({ tone: 'error', title: '添加监控账号失败', message: formatTwitterActionError(error, '添加监控账号失败') })
    } finally {
      setAdding(false)
    }
  }

  const handleDeleteAccount = async (id: number) => {
    try {
      await api.delete(`/monitor/accounts/${id}`)
      await loadData()
      setPendingDeleteAccountId(null)
      setActionMessage({ tone: 'success', title: '监控账号已删除', message: '该账号已从监控列表移除。' })
    } catch (error) {
      setActionMessage({ tone: 'error', title: '删除监控账号失败', message: formatTwitterActionError(error, '删除监控账号失败') })
    }
  }

  const handleToggleAccount = async (id: number) => {
    try {
      await api.patch(`/monitor/accounts/${id}/toggle`)
      await loadData()
      setActionMessage({ tone: 'success', title: '监控状态已更新', message: '账号监控开关已切换。' })
    } catch (error) {
      setActionMessage({ tone: 'error', title: '切换监控失败', message: formatTwitterActionError(error, '切换监控账号状态失败') })
    }
  }

  const handleMarkCommented = async (id: number, text: string) => {
    try {
      await api.post(`/monitor/notifications/${id}/comment`, { comment_text: text })
      await loadData()
    } catch (error) {
      setActionMessage({ tone: 'error', title: '更新通知状态失败', message: formatTwitterActionError(error, '更新通知状态失败') })
    }
  }

  const handleGenerateReply = async (notif: Notification) => {
    const mode = activePanel[notif.id] || 'reply'
    setGenerating(prev => ({ ...prev, [notif.id]: true }))
    setReplyErrors(prev => ({ ...prev, [notif.id]: '' }))
    try {
      const res = await api.post('/engage/generate-reply', {
        tweet_id: notif.tweet_id,
        tweet_text: notif.tweet_text,
        author_username: notif.author_username,
        mode
      })
      setReplyDrafts(prev => ({ ...prev, [notif.id]: res.data.content }))
    } catch (e: any) {
      setReplyErrors(prev => ({ ...prev, [notif.id]: formatTwitterActionError(e, '生成回复草稿失败') }))
    } finally {
      setGenerating(prev => ({ ...prev, [notif.id]: false }))
    }
  }

  const handleSendReply = async (notif: Notification) => {
    const content = replyDrafts[notif.id]
    if (!content?.trim()) return
    setSending(prev => ({ ...prev, [notif.id]: true }))
    setReplyErrors(prev => ({ ...prev, [notif.id]: '' }))
    try {
      await api.post(`/engage/reply/${notif.tweet_id}`, { content })
      await handleMarkCommented(notif.id, content)
      setReplyDrafts(prev => ({ ...prev, [notif.id]: '' }))
      setActivePanel(prev => ({ ...prev, [notif.id]: null }))
    } catch (e: any) {
      setReplyErrors(prev => ({ ...prev, [notif.id]: formatTwitterActionError(e, '发送回复失败') }))
    } finally {
      setSending(prev => ({ ...prev, [notif.id]: false }))
    }
  }

  const handleQuoteTweet = async (notif: Notification) => {
    const content = replyDrafts[notif.id]
    if (!content?.trim()) return
    setQuoting(prev => ({ ...prev, [notif.id]: true }))
    setReplyErrors(prev => ({ ...prev, [notif.id]: '' }))
    try {
      await api.post('/engage/quote', { tweet_url: notif.tweet_url, content })
      await handleMarkCommented(notif.id, `[引用转发] ${content}`)
      setReplyDrafts(prev => ({ ...prev, [notif.id]: '' }))
      setActivePanel(prev => ({ ...prev, [notif.id]: null }))
    } catch (e: any) {
      setReplyErrors(prev => ({ ...prev, [notif.id]: formatTwitterActionError(e, '引用转发失败') }))
    } finally {
      setQuoting(prev => ({ ...prev, [notif.id]: false }))
    }
  }

  const handleRetweet = async (notif: Notification) => {
    setRetweeting(prev => ({ ...prev, [notif.id]: true }))
    setReplyErrors(prev => ({ ...prev, [notif.id]: '' }))
    try {
      await api.post(`/engage/retweet/${notif.tweet_id}`)
      await handleMarkCommented(notif.id, '[转发]')
      setPendingRetweetNotifId(null)
    } catch (e: any) {
      setReplyErrors(prev => ({ ...prev, [notif.id]: formatTwitterActionError(e, '转发失败') }))
    } finally {
      setRetweeting(prev => ({ ...prev, [notif.id]: false }))
    }
  }

  const handleSaveEngageConfig = async (accountId: number) => {
    const config = engageConfig[accountId]
    if (!config) return
    setSavingEngage(prev => ({ ...prev, [accountId]: true }))
    try {
      await api.patch(`/monitor/accounts/${accountId}/auto-engage`, config)
      await loadData()
      setEngagePanel(prev => ({ ...prev, [accountId]: false }))
      setActionMessage({ tone: 'success', title: '自动互动配置已保存', message: '新的自动互动参数已生效。' })
    } catch (e: any) {
      setActionMessage({ tone: 'error', title: '保存自动互动配置失败', message: formatTwitterActionError(e, '保存自动互动配置失败') })
    } finally {
      setSavingEngage(prev => ({ ...prev, [accountId]: false }))
    }
  }

  const getPriorityColor = (priority: number) => {
    const colors = { 1: 'bg-red-100 text-red-800', 2: 'bg-yellow-100 text-yellow-800', 3: 'bg-green-100 text-green-800' }
    return colors[priority as keyof typeof colors] || 'bg-gray-100 text-gray-800'
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    )
  }

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold">账号监控</h1>
        <p className="text-muted-foreground mt-1">监控名人/交易所账号，第一时间发现新推文</p>
      </div>

      {actionMessage && (
        <InlineNotice
          tone={actionMessage.tone}
          title={actionMessage.title}
          message={actionMessage.message}
          dismissible
          autoHideMs={actionMessage.tone === 'error' ? undefined : 4000}
          onClose={() => setActionMessage(null)}
        />
      )}

      {pendingDeleteAccountId !== null && (
        <InlineConfirm
          title="确认停止监控"
          message="该账号将从监控列表中移除，但历史通知记录不会被删除。"
          confirmLabel="停止监控"
          onConfirm={() => handleDeleteAccount(pendingDeleteAccountId)}
          onCancel={() => setPendingDeleteAccountId(null)}
        />
      )}

      {pendingRetweetNotifId !== null && (() => {
        const notif = notifications.find((item) => item.id === pendingRetweetNotifId)
        if (!notif) return null
        return (
          <InlineConfirm
            title="确认转发"
            message={`即将转发 @${notif.author_username} 的推文，并同步更新该通知状态。`}
            confirmLabel="确认转发"
            busy={!!retweeting[notif.id]}
            onConfirm={() => handleRetweet(notif)}
            onCancel={() => setPendingRetweetNotifId(null)}
          />
        )
      })()}

      {loadError && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900">
          <div className="font-medium">监控页加载失败</div>
          <div className="mt-1">{loadError}</div>
          <div className="mt-2">
            <Button type="button" variant="outline" size="sm" onClick={loadData}>
              <RefreshCw className="mr-2 h-4 w-4" />
              重新加载
            </Button>
          </div>
        </div>
      )}

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">监控账号</p>
                  <p className="text-2xl font-bold">{stats.active_accounts}/{stats.total_accounts}</p>
                </div>
                <TrendingUp className="h-8 w-8 text-blue-500" />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">今日推文</p>
                  <p className="text-2xl font-bold">{stats.today_notifications}</p>
                </div>
                <Bell className="h-8 w-8 text-green-500" />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">待评论</p>
                  <p className="text-2xl font-bold">{stats.uncommented_notifications}</p>
                </div>
                <MessageSquare className="h-8 w-8 text-orange-500" />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">监控状态</p>
                  <p className="text-sm font-medium">{stats.monitor_running ? '运行中' : '已停止'}</p>
                </div>
                {stats.monitor_running ? (
                  <Power className="h-8 w-8 text-green-500" />
                ) : (
                  <PowerOff className="h-8 w-8 text-gray-400" />
                )}
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      <TwitterRiskBanner state={stats} />

      {stats && (stats.backoff_seconds || 0) > 0 && (
        <Card className="border-amber-200 bg-amber-50">
          <CardContent className="pt-6">
            <p className="text-sm font-medium text-amber-900">监控当前处于风控冷却期</p>
            <p className="text-sm text-amber-800 mt-1">
              剩余约 {Math.ceil((stats.backoff_seconds || 0) / 60)} 分钟，期间会暂停新的监控抓取和自动互动。
            </p>
          </CardContent>
        </Card>
      )}

      {/* Add Account */}
      <Card>
        <CardHeader>
          <CardTitle>添加监控账号</CardTitle>
          <CardDescription>输入 Twitter 用户名（如 @binance 或 binance）</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex gap-3">
            <Input
              placeholder="用户名"
              value={newUsername}
              onChange={(e) => setNewUsername(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleAddAccount()}
            />
            <select
              className="px-3 py-2 border rounded-md"
              value={newPriority}
              onChange={(e) => setNewPriority(Number(e.target.value))}
            >
              <option value={1}>高优先级 (2分钟)</option>
              <option value={2}>中优先级 (5分钟)</option>
              <option value={3}>低优先级 (15分钟)</option>
            </select>
            <Button onClick={handleAddAccount} disabled={adding || !newUsername.trim()}>
              <Plus className="h-4 w-4 mr-2" />
              添加
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Accounts List */}
      <Card>
        <CardHeader>
          <CardTitle>监控列表 ({accounts.length})</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {accounts.map((account) => (
              <div key={account.id} className="border rounded-lg overflow-hidden">
                <div className="flex items-center justify-between p-3">
                  <div className="flex items-center gap-3">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-medium">@{account.username}</span>
                        {account.display_name && (
                          <span className="text-sm text-muted-foreground">({account.display_name})</span>
                        )}
                        <Badge className={getPriorityColor(account.priority)}>
                          优先级 {account.priority}
                        </Badge>
                        {!account.is_active && (
                          <Badge variant="outline">已暂停</Badge>
                        )}
                        {account.auto_engage && (
                          <Badge className="bg-purple-100 text-purple-800">
                            <Bot className="h-3 w-3 mr-1" />
                            自动互动
                          </Badge>
                        )}
                      </div>
                      {account.last_checked_at && (
                        <p className="text-xs text-muted-foreground mt-1">
                          最后检查: {new Date(account.last_checked_at + 'Z').toLocaleString('zh-CN')}
                        </p>
                      )}
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => setEngagePanel(prev => ({ ...prev, [account.id]: !prev[account.id] }))}
                      title="自动互动设置"
                    >
                      <Settings className="h-4 w-4" />
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => handleToggleAccount(account.id)}
                    >
                      {account.is_active ? <PowerOff className="h-4 w-4" /> : <Power className="h-4 w-4" />}
                    </Button>
                    <Button
                      size="sm"
                      variant="destructive"
                      onClick={() => setPendingDeleteAccountId(account.id)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>

                {/* Auto-engage config panel */}
                {engagePanel[account.id] && engageConfig[account.id] && (
                  <div className="border-t bg-gray-50 p-3 space-y-3">
                    <p className="text-sm font-medium text-gray-700">自动互动设置</p>
                    <div className="flex items-center gap-3 flex-wrap">
                      <label className="flex items-center gap-2 text-sm cursor-pointer">
                        <input
                          type="checkbox"
                          checked={engageConfig[account.id].auto_engage}
                          onChange={e => setEngageConfig(prev => ({
                            ...prev,
                            [account.id]: { ...prev[account.id], auto_engage: e.target.checked }
                          }))}
                          className="w-4 h-4"
                        />
                        启用自动互动
                      </label>
                      <select
                        className="px-2 py-1 text-sm border rounded-md bg-white"
                        value={engageConfig[account.id].engage_action}
                        onChange={e => setEngageConfig(prev => ({
                          ...prev,
                          [account.id]: { ...prev[account.id], engage_action: e.target.value }
                        }))}
                        disabled={!engageConfig[account.id].auto_engage}
                      >
                        <option value="reply">仅评论</option>
                        <option value="retweet">仅转发</option>
                        <option value="both">评论+转发</option>
                      </select>
                      <div className="flex items-center gap-1 text-sm">
                        <span>基础延迟</span>
                        <input
                          type="number"
                          min={30}
                          max={300}
                          className="w-16 px-2 py-1 border rounded-md text-sm bg-white"
                          value={engageConfig[account.id].engage_delay}
                          onChange={e => setEngageConfig(prev => ({
                            ...prev,
                            [account.id]: { ...prev[account.id], engage_delay: Number(e.target.value) }
                          }))}
                          disabled={!engageConfig[account.id].auto_engage}
                        />
                        <span>秒 (实际随机浮动)</span>
                      </div>
                    </div>
                    <p className="text-xs text-muted-foreground">
                      检测到新推文后，系统会在基础延迟上随机浮动 ±40%，并有 15% 概率额外等待 1-3 分钟，模拟真人行为。
                    </p>
                    <Button
                      size="sm"
                      onClick={() => handleSaveEngageConfig(account.id)}
                      disabled={savingEngage[account.id]}
                    >
                      {savingEngage[account.id] ? <Loader2 className="h-3.5 w-3.5 animate-spin mr-1" /> : null}
                      保存
                    </Button>
                  </div>
                )}
              </div>
            ))}
            {accounts.length === 0 && (
              <p className="text-center text-muted-foreground py-8">暂无监控账号</p>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Notifications */}
      <Card>
        <CardHeader>
          <CardTitle>推文通知 ({notifications.length})</CardTitle>
          <CardDescription>最新 50 条推文通知</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {notifications.map((notif) => (
              <div key={notif.id} className={`p-4 border rounded-lg ${notif.is_commented ? 'bg-gray-50' : 'bg-white'}`}>
                <div className="flex items-start gap-3">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="font-medium">@{notif.author_username}</span>
                      <span className="text-xs text-muted-foreground">
                        {new Date(notif.tweet_created_at + 'Z').toLocaleString('zh-CN')}
                      </span>
                      {notif.is_commented && (
                        <Badge variant="outline" className="bg-green-50 text-green-700">已评论</Badge>
                      )}
                      {!notif.is_commented && notif.auto_engage_status === 'scheduled' && (
                        <Badge variant="outline" className="bg-purple-50 text-purple-700">
                          <Bot className="h-3 w-3 mr-1" />自动处理中
                        </Badge>
                      )}
                      {!notif.is_commented && notif.auto_engage_status === 'failed' && (
                        <Badge variant="outline" className="bg-red-50 text-red-700">自动失败</Badge>
                      )}
                    </div>
                    <p className="text-sm mb-2 leading-relaxed">{notif.tweet_text}</p>
                    <a
                      href={notif.tweet_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 text-xs text-blue-600 hover:underline"
                    >
                      查看推文 <ExternalLink className="h-3 w-3" />
                    </a>

                    {notif.is_commented && notif.comment_text && (
                      <div className="mt-3 p-2 bg-green-50 rounded text-sm">
                        <p className="text-xs text-green-700 mb-1">已操作:</p>
                        <p>{notif.comment_text}</p>
                      </div>
                    )}

                    {!notif.is_commented && (
                      <div className="mt-3 space-y-2">
                        {/* Action buttons */}
                        <div className="flex gap-2 flex-wrap">
                          <button
                            onClick={() => setActivePanel(prev => ({ ...prev, [notif.id]: prev[notif.id] === 'reply' ? null : 'reply' }))}
                            className={`flex items-center gap-1.5 px-3 py-1.5 text-sm border rounded-md transition-colors ${activePanel[notif.id] === 'reply' ? 'bg-primary text-primary-foreground' : 'hover:bg-accent'}`}
                          >
                            <MessageSquare className="h-3.5 w-3.5" />
                            评论
                          </button>
                          <button
                            onClick={() => setActivePanel(prev => ({ ...prev, [notif.id]: prev[notif.id] === 'quote' ? null : 'quote' }))}
                            className={`flex items-center gap-1.5 px-3 py-1.5 text-sm border rounded-md transition-colors ${activePanel[notif.id] === 'quote' ? 'bg-primary text-primary-foreground' : 'hover:bg-accent'}`}
                          >
                            <Repeat2 className="h-3.5 w-3.5" />
                            引用转发
                          </button>
                          <TwitterGuardedButton
                            onClick={() => setPendingRetweetNotifId(notif.id)}
                            disabled={retweeting[notif.id]}
                            loading={retweeting[notif.id]}
                            icon={<Repeat2 className="h-3.5 w-3.5 text-green-600" />}
                            label="转发"
                            variant="outline"
                            writeBlocked={!!stats?.write_blocked}
                            writeBlockedReason={writeBlockedReason}
                            className="h-auto gap-1.5 px-3 py-1.5 text-sm"
                          />
                        </div>

                        {/* Reply / Quote panel */}
                        {(activePanel[notif.id] === 'reply' || activePanel[notif.id] === 'quote') && (
                          <div className="space-y-2 pt-1">
                            <div className="relative">
                              <textarea
                                className="w-full px-3 py-2 text-sm rounded-md border bg-background focus:outline-none focus:ring-2 focus:ring-primary resize-none"
                                rows={3}
                                placeholder={activePanel[notif.id] === 'quote' ? '输入引用转发的评论内容...' : '点击「AI 生成」获取回复草稿，或直接输入...'}
                                value={replyDrafts[notif.id] || ''}
                                onChange={e => setReplyDrafts(prev => ({ ...prev, [notif.id]: e.target.value }))}
                                maxLength={280}
                              />
                              <span className={`absolute bottom-2 right-2 text-xs ${(replyDrafts[notif.id]?.length || 0) > 260 ? 'text-destructive' : 'text-muted-foreground'}`}>
                                {replyDrafts[notif.id]?.length || 0}/280
                              </span>
                            </div>
                            {replyErrors[notif.id] && (
                              <p className="text-xs text-destructive">{replyErrors[notif.id]}</p>
                            )}
                            <div className="flex gap-2">
                              <button
                                onClick={() => handleGenerateReply(notif)}
                                disabled={generating[notif.id]}
                                className="flex items-center gap-1.5 px-3 py-1.5 text-sm border rounded-md hover:bg-accent disabled:opacity-50"
                              >
                                {generating[notif.id] ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
                                AI 生成
                              </button>
                              {activePanel[notif.id] === 'reply' ? (
                                <TwitterGuardedButton
                                  onClick={() => handleSendReply(notif)}
                                  disabled={sending[notif.id] || !replyDrafts[notif.id]?.trim()}
                                  loading={sending[notif.id]}
                                  icon={<Send className="h-3.5 w-3.5" />}
                                  label="发送评论"
                                  writeBlocked={!!stats?.write_blocked}
                                  writeBlockedReason={writeBlockedReason}
                                  className="h-auto gap-1.5 px-3 py-1.5 text-sm"
                                />
                              ) : (
                                <TwitterGuardedButton
                                  onClick={() => handleQuoteTweet(notif)}
                                  disabled={quoting[notif.id] || !replyDrafts[notif.id]?.trim()}
                                  loading={quoting[notif.id]}
                                  icon={<Repeat2 className="h-3.5 w-3.5" />}
                                  label="发送引用"
                                  writeBlocked={!!stats?.write_blocked}
                                  writeBlockedReason={writeBlockedReason}
                                  className="h-auto gap-1.5 px-3 py-1.5 text-sm"
                                />
                              )}
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}
            {notifications.length === 0 && (
              <p className="text-center text-muted-foreground py-8">暂无推文通知</p>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
