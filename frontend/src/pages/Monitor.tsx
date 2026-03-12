import { useState, useEffect } from 'react'
import { Plus, Trash2, Power, PowerOff, Bell, MessageSquare, TrendingUp, RefreshCw, Send, Loader2, ExternalLink, Repeat2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import api from '@/services/api'

interface MonitoredAccount {
  id: number
  username: string
  user_id?: string
  display_name?: string
  priority: number
  last_tweet_id?: string
  last_checked_at?: string
  is_active: boolean
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
}

interface Stats {
  total_accounts: number
  active_accounts: number
  total_notifications: number
  commented_notifications: number
  uncommented_notifications: number
  today_notifications: number
  monitor_running: boolean
}

export default function Monitor() {
  const [accounts, setAccounts] = useState<MonitoredAccount[]>([])
  const [notifications, setNotifications] = useState<Notification[]>([])
  const [stats, setStats] = useState<Stats | null>(null)
  const [newUsername, setNewUsername] = useState('')
  const [newPriority, setNewPriority] = useState(2)
  const [loading, setLoading] = useState(true)
  const [adding, setAdding] = useState(false)

  // AI reply states
  const [replyDrafts, setReplyDrafts] = useState<Record<number, string>>({})
  const [generating, setGenerating] = useState<Record<number, boolean>>({})
  const [sending, setSending] = useState<Record<number, boolean>>({})
  const [quoting, setQuoting] = useState<Record<number, boolean>>({})
  const [retweeting, setRetweeting] = useState<Record<number, boolean>>({})
  const [replyErrors, setReplyErrors] = useState<Record<number, string>>({})
  // 'reply' | 'quote' | null - which action panel is open
  const [activePanel, setActivePanel] = useState<Record<number, 'reply' | 'quote' | null>>({})

  useEffect(() => {
    loadData()
    const interval = setInterval(loadData, 30000) // Refresh every 30s
    return () => clearInterval(interval)
  }, [])

  const loadData = async () => {
    try {
      const [accountsRes, notificationsRes, statsRes] = await Promise.all([
        api.get('/monitor/accounts'),
        api.get('/monitor/notifications?limit=50'),
        api.get('/monitor/stats')
      ])
      setAccounts(accountsRes.data)
      setNotifications(notificationsRes.data)
      setStats(statsRes.data)
    } catch (error) {
      console.error('Failed to load data:', error)
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
    } catch (error: any) {
      alert(error.response?.data?.detail || 'Failed to add account')
    } finally {
      setAdding(false)
    }
  }

  const handleDeleteAccount = async (id: number) => {
    if (!confirm('确定停止监控此账号？')) return
    try {
      await api.delete(`/monitor/accounts/${id}`)
      await loadData()
    } catch (error) {
      alert('Failed to delete account')
    }
  }

  const handleToggleAccount = async (id: number) => {
    try {
      await api.patch(`/monitor/accounts/${id}/toggle`)
      await loadData()
    } catch (error) {
      alert('Failed to toggle account')
    }
  }

  const handleMarkCommented = async (id: number, text: string) => {
    try {
      await api.post(`/monitor/notifications/${id}/comment`, { comment_text: text })
      await loadData()
    } catch (error) {
      alert('Failed to mark as commented')
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
      setReplyErrors(prev => ({ ...prev, [notif.id]: e.response?.data?.detail || 'Failed to generate reply' }))
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
      setReplyErrors(prev => ({ ...prev, [notif.id]: e.response?.data?.detail || 'Failed to send reply' }))
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
      setReplyErrors(prev => ({ ...prev, [notif.id]: e.response?.data?.detail || 'Failed to quote tweet' }))
    } finally {
      setQuoting(prev => ({ ...prev, [notif.id]: false }))
    }
  }

  const handleRetweet = async (notif: Notification) => {
    if (!confirm(`确定转发 @${notif.author_username} 的推文？`)) return
    setRetweeting(prev => ({ ...prev, [notif.id]: true }))
    setReplyErrors(prev => ({ ...prev, [notif.id]: '' }))
    try {
      await api.post(`/engage/retweet/${notif.tweet_id}`)
      await handleMarkCommented(notif.id, '[转发]')
    } catch (e: any) {
      setReplyErrors(prev => ({ ...prev, [notif.id]: e.response?.data?.detail || 'Failed to retweet' }))
    } finally {
      setRetweeting(prev => ({ ...prev, [notif.id]: false }))
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
              <div key={account.id} className="flex items-center justify-between p-3 border rounded-lg">
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
                    onClick={() => handleToggleAccount(account.id)}
                  >
                    {account.is_active ? <PowerOff className="h-4 w-4" /> : <Power className="h-4 w-4" />}
                  </Button>
                  <Button
                    size="sm"
                    variant="destructive"
                    onClick={() => handleDeleteAccount(account.id)}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
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
                          <button
                            onClick={() => handleRetweet(notif)}
                            disabled={retweeting[notif.id]}
                            className="flex items-center gap-1.5 px-3 py-1.5 text-sm border rounded-md hover:bg-accent disabled:opacity-50"
                          >
                            {retweeting[notif.id] ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Repeat2 className="h-3.5 w-3.5 text-green-600" />}
                            转发
                          </button>
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
                                <button
                                  onClick={() => handleSendReply(notif)}
                                  disabled={sending[notif.id] || !replyDrafts[notif.id]?.trim()}
                                  className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-primary text-primary-foreground rounded-md hover:bg-primary/90 disabled:opacity-50"
                                >
                                  {sending[notif.id] ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Send className="h-3.5 w-3.5" />}
                                  发送评论
                                </button>
                              ) : (
                                <button
                                  onClick={() => handleQuoteTweet(notif)}
                                  disabled={quoting[notif.id] || !replyDrafts[notif.id]?.trim()}
                                  className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-primary text-primary-foreground rounded-md hover:bg-primary/90 disabled:opacity-50"
                                >
                                  {quoting[notif.id] ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Repeat2 className="h-3.5 w-3.5" />}
                                  发送引用
                                </button>
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
