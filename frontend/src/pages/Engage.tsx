import { useState } from 'react'
import { Search, Send, Loader2, ExternalLink, RefreshCw, CheckCircle2, Repeat2, CheckSquare, Square, Layers } from 'lucide-react'
import api from '@/services/api'

interface SearchResult {
  id: string
  text: string
  author_name: string
  author_username: string
  author_verified: boolean
  like_count: number
  retweet_count: number
  reply_count: number
  view_count?: string
  created_at: string
  url: string
}

const PRESET_QUERIES = [
  'AI crypto trading',
  'Hyperliquid trading bot',
  'crypto trading AI agent',
  'perpetual futures AI',
  'DeepSeek trading',
  'AI量化真的能赚钱吗',
  '量化交易靠谱吗',
  'AI交易机器人有用吗',
  '加密货币自动交易怎么样',
  'crypto bot worth it',
  'is AI trading profitable',
  'automated trading reliable',
]

export default function Engage() {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<SearchResult[]>([])
  const [searching, setSearching] = useState(false)
  const [searchError, setSearchError] = useState('')

  const [replyDrafts, setReplyDrafts] = useState<Record<string, string>>({})
  const [generating, setGenerating] = useState<Record<string, boolean>>({})
  const [sending, setSending] = useState<Record<string, boolean>>({})
  const [quoting, setQuoting] = useState<Record<string, boolean>>({})
  const [sent, setSent] = useState<Record<string, boolean>>({})
  const [repliedBefore, setRepliedBefore] = useState<Set<string>>(new Set())
  const [replyErrors, setReplyErrors] = useState<Record<string, string>>({})

  // Batch mode state
  const [batchMode, setBatchMode] = useState(false)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [batchGenerating, setBatchGenerating] = useState(false)
  const [batchSending, setBatchSending] = useState(false)
  const [batchProgress, setBatchProgress] = useState<{ done: number; total: number } | null>(null)
  const [batchResults, setBatchResults] = useState<Record<string, { success: boolean; error?: string }>>({})

  async function handleSearch(q?: string) {
    const searchQuery = q ?? query
    if (!searchQuery.trim()) return
    setSearching(true)
    setSearchError('')
    setResults([])
    setSent({})
    setSelected(new Set())
    setBatchResults({})
    try {
      const [searchRes, repliedRes] = await Promise.all([
        api.post('/engage/search', { query: searchQuery, count: 20 }),
        api.get('/engage/replied-ids'),
      ])
      setResults(searchRes.data)
      setRepliedBefore(new Set(repliedRes.data.ids))
    } catch (e: any) {
      setSearchError(e.response?.data?.detail || '搜索失败，请检查 Twitter 连接')
    } finally {
      setSearching(false)
    }
  }

  async function handleGenerateReply(tweet: SearchResult) {
    setGenerating(prev => ({ ...prev, [tweet.id]: true }))
    setReplyErrors(prev => ({ ...prev, [tweet.id]: '' }))
    try {
      const res = await api.post('/engage/generate-reply', {
        tweet_text: tweet.text,
        author_username: tweet.author_username,
      })
      setReplyDrafts(prev => ({ ...prev, [tweet.id]: res.data.content }))
    } catch (e: any) {
      setReplyErrors(prev => ({ ...prev, [tweet.id]: e.response?.data?.detail || '生成失败' }))
    } finally {
      setGenerating(prev => ({ ...prev, [tweet.id]: false }))
    }
  }

  async function handleSendReply(tweet: SearchResult) {
    const content = replyDrafts[tweet.id]
    if (!content?.trim()) return
    setSending(prev => ({ ...prev, [tweet.id]: true }))
    setReplyErrors(prev => ({ ...prev, [tweet.id]: '' }))
    try {
      await api.post(`/engage/reply/${tweet.id}`, {
        content,
        tweet_text: tweet.text,
        author_username: tweet.author_username,
      })
      setSent(prev => ({ ...prev, [tweet.id]: true }))
      setRepliedBefore(prev => new Set([...prev, tweet.id]))
      setReplyDrafts(prev => ({ ...prev, [tweet.id]: '' }))
    } catch (e: any) {
      setReplyErrors(prev => ({ ...prev, [tweet.id]: e.response?.data?.detail || '发送失败' }))
    } finally {
      setSending(prev => ({ ...prev, [tweet.id]: false }))
    }
  }

  async function handleQuote(tweet: SearchResult) {
    const content = replyDrafts[tweet.id]
    if (!content?.trim()) return
    setQuoting(prev => ({ ...prev, [tweet.id]: true }))
    setReplyErrors(prev => ({ ...prev, [tweet.id]: '' }))
    try {
      await api.post('/engage/quote', { tweet_url: tweet.url, content })
      setSent(prev => ({ ...prev, [tweet.id]: true }))
      setRepliedBefore(prev => new Set([...prev, tweet.id]))
      setReplyDrafts(prev => ({ ...prev, [tweet.id]: '' }))
    } catch (e: any) {
      setReplyErrors(prev => ({ ...prev, [tweet.id]: e.response?.data?.detail || '引用转发失败' }))
    } finally {
      setQuoting(prev => ({ ...prev, [tweet.id]: false }))
    }
  }

  function toggleSelect(id: string) {
    setSelected(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  function toggleSelectAll() {
    const eligible = results.filter(t => !sent[t.id] && !repliedBefore.has(t.id))
    if (eligible.every(t => selected.has(t.id))) {
      setSelected(new Set())
    } else {
      setSelected(new Set(eligible.map(t => t.id)))
    }
  }

  async function handleBatchGenerate() {
    const targets = results.filter(t => selected.has(t.id) && !replyDrafts[t.id]?.trim())
    if (!targets.length) return
    setBatchGenerating(true)
    await Promise.all(targets.map(tweet => handleGenerateReply(tweet)))
    setBatchGenerating(false)
  }

  async function handleBatchSend() {
    const targets = results.filter(t => selected.has(t.id) && replyDrafts[t.id]?.trim() && !sent[t.id])
    if (!targets.length) return
    setBatchSending(true)
    setBatchProgress({ done: 0, total: targets.length })
    setBatchResults({})
    try {
      const items = targets.map(t => ({
        tweet_id: t.id,
        content: replyDrafts[t.id],
        tweet_text: t.text,
        author_username: t.author_username,
      }))
      const res = await api.post('/engage/batch-reply', { items, delay_min: 45, delay_max: 90 })
      const resultList: { tweet_id: string; success: boolean; error?: string }[] = res.data
      const newBatchResults: Record<string, { success: boolean; error?: string }> = {}
      resultList.forEach((r, idx) => {
        newBatchResults[r.tweet_id] = { success: r.success, error: r.error }
        if (r.success) {
          setSent(prev => ({ ...prev, [r.tweet_id]: true }))
          setRepliedBefore(prev => new Set([...prev, r.tweet_id]))
          setReplyDrafts(prev => ({ ...prev, [r.tweet_id]: '' }))
        }
        setBatchProgress({ done: idx + 1, total: targets.length })
      })
      setBatchResults(newBatchResults)
    } catch (e: any) {
      // Network-level failure
      targets.forEach(t => {
        setBatchResults(prev => ({ ...prev, [t.id]: { success: false, error: e.response?.data?.detail || '批量发送失败' } }))
      })
    } finally {
      setBatchSending(false)
    }
  }

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold">互动引流</h1>
        <p className="text-muted-foreground mt-1">搜索热门话题，用 AI 生成回复草稿，手动确认后发送</p>
      </div>

      {/* 搜索区 */}
      <div className="space-y-3">
        <div className="flex gap-2">
          <input
            className="flex-1 px-4 py-2 rounded-md border bg-background focus:outline-none focus:ring-2 focus:ring-primary"
            placeholder="输入关键词，如 AI crypto trading..."
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleSearch()}
          />
          <button
            onClick={() => handleSearch()}
            disabled={searching || !query.trim()}
            className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 disabled:opacity-50"
          >
            {searching ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
            搜索
          </button>
        </div>

        {/* 预设关键词 */}
        <div className="flex flex-wrap gap-2">
          {PRESET_QUERIES.map(q => (
            <button
              key={q}
              onClick={() => { setQuery(q); handleSearch(q) }}
              className="px-3 py-1 text-sm rounded-full border hover:bg-accent transition-colors"
            >
              {q}
            </button>
          ))}
        </div>
      </div>

      {searchError && (
        <div className="p-3 rounded-md bg-destructive/10 text-destructive text-sm">{searchError}</div>
      )}

      {/* Search results */}
      {results.length > 0 && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-sm text-muted-foreground">找到 {results.length} 条推文</p>
            <button
              onClick={() => { setBatchMode(v => !v); setSelected(new Set()) }}
              className={`flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-md border transition-colors ${batchMode ? 'bg-primary text-primary-foreground border-primary' : 'hover:bg-accent'}`}
            >
              <Layers className="h-3.5 w-3.5" />
              批量模式
            </button>
          </div>

          {/* Batch action bar */}
          {batchMode && (
            <div className="flex flex-wrap items-center gap-2 p-3 rounded-md bg-muted/50 border">
              <button onClick={toggleSelectAll} className="flex items-center gap-1.5 text-sm hover:text-primary">
                {results.filter(t => !sent[t.id] && !repliedBefore.has(t.id)).every(t => selected.has(t.id)) && results.filter(t => !sent[t.id] && !repliedBefore.has(t.id)).length > 0
                  ? <CheckSquare className="h-4 w-4" />
                  : <Square className="h-4 w-4" />}
                全选
              </button>
              <span className="text-sm text-muted-foreground">已选 {selected.size} 条</span>
              <button
                onClick={handleBatchGenerate}
                disabled={batchGenerating || selected.size === 0}
                className="flex items-center gap-1.5 px-3 py-1.5 text-sm border rounded-md hover:bg-accent disabled:opacity-50"
              >
                {batchGenerating ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
                批量生成草稿
              </button>
              <button
                onClick={handleBatchSend}
                disabled={batchSending || selected.size === 0}
                className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-primary text-primary-foreground rounded-md hover:bg-primary/90 disabled:opacity-50"
              >
                {batchSending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Send className="h-3.5 w-3.5" />}
                批量发送
              </button>
              {batchProgress && (
                <span className="text-sm text-muted-foreground ml-auto">
                  {batchProgress.done} / {batchProgress.total} 已发送
                </span>
              )}
            </div>
          )}

          {results.map(tweet => (
            <TweetCard
              key={tweet.id}
              tweet={tweet}
              draft={replyDrafts[tweet.id] || ''}
              generating={generating[tweet.id] || false}
              sending={sending[tweet.id] || false}
              quoting={quoting[tweet.id] || false}
              sent={sent[tweet.id] || false}
              repliedBefore={repliedBefore.has(tweet.id)}
              error={replyErrors[tweet.id] || ''}
              batchMode={batchMode}
              isSelected={selected.has(tweet.id)}
              batchResult={batchResults[tweet.id]}
              onDraftChange={val => setReplyDrafts(prev => ({ ...prev, [tweet.id]: val }))}
              onGenerate={() => handleGenerateReply(tweet)}
              onSend={() => handleSendReply(tweet)}
              onQuote={() => handleQuote(tweet)}
              onToggleSelect={() => toggleSelect(tweet.id)}
            />
          ))}
        </div>
      )}
    </div>
  )
}

interface TweetCardProps {
  tweet: SearchResult
  draft: string
  generating: boolean
  sending: boolean
  quoting: boolean
  sent: boolean
  repliedBefore: boolean
  error: string
  batchMode: boolean
  isSelected: boolean
  batchResult?: { success: boolean; error?: string; aborted?: boolean }
  onDraftChange: (val: string) => void
  onGenerate: () => void
  onSend: () => void
  onQuote: () => void
  onToggleSelect: () => void
}

function TweetCard({ tweet, draft, generating, sending, quoting, sent, repliedBefore, error, batchMode, isSelected, batchResult, onDraftChange, onGenerate, onSend, onQuote, onToggleSelect }: TweetCardProps) {
  const charCount = draft.length

  return (
    <div className={`border rounded-lg p-4 space-y-3 bg-card ${repliedBefore && !sent ? 'opacity-60' : ''} ${batchMode && isSelected ? 'ring-2 ring-primary' : ''}`}>
      <div className="flex items-start gap-3">
        {batchMode && (
          <button onClick={onToggleSelect} className="mt-0.5 flex-shrink-0 text-muted-foreground hover:text-primary">
            {isSelected ? <CheckSquare className="h-4 w-4 text-primary" /> : <Square className="h-4 w-4" />}
          </button>
        )}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="font-medium text-sm">{tweet.author_name}</span>
            <span className="text-muted-foreground text-sm">@{tweet.author_username}</span>
            {tweet.author_verified && (
              <span className="text-xs bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded">蓝V</span>
            )}
            {repliedBefore && !sent && (
              <span className="flex items-center gap-1 text-xs text-green-600">
                <CheckCircle2 className="h-3.5 w-3.5" />
                已回复过
              </span>
            )}
          </div>
          <p className="text-sm leading-relaxed">{tweet.text}</p>
          <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground">
            <span>赞 {tweet.like_count?.toLocaleString()}</span>
            <span>转推 {tweet.retweet_count?.toLocaleString()}</span>
            <span>回复 {tweet.reply_count?.toLocaleString()}</span>
            {tweet.view_count && <span>浏览 {tweet.view_count}</span>}
          </div>
        </div>
        <a href={tweet.url} target="_blank" rel="noopener noreferrer" className="text-muted-foreground hover:text-foreground flex-shrink-0">
          <ExternalLink className="h-4 w-4" />
        </a>
      </div>

      {/* Batch result indicator */}
      {batchResult && (
        <div className={`p-2 rounded text-sm ${batchResult.success ? 'bg-green-50 text-green-700' : batchResult.aborted ? 'bg-yellow-50 text-yellow-700' : 'bg-destructive/10 text-destructive'}`}>
          {batchResult.success ? '批量发送成功' : batchResult.aborted ? '已跳过：检测到频率限制，批次已中止' : `发送失败: ${batchResult.error}`}
        </div>
      )}

      {sent ? (
        <div className="p-2 rounded bg-green-50 text-green-700 text-sm">已发送</div>
      ) : (
        <div className="space-y-2">
          <div className="relative">
            <textarea
              className="w-full px-3 py-2 text-sm rounded-md border bg-background focus:outline-none focus:ring-2 focus:ring-primary resize-none"
              rows={3}
              placeholder="点击「AI 生成」获取草稿，或直接输入..."
              value={draft}
              onChange={e => onDraftChange(e.target.value)}
              maxLength={280}
            />
            <span className={`absolute bottom-2 right-2 text-xs ${charCount > 260 ? 'text-destructive' : 'text-muted-foreground'}`}>
              {charCount}/280
            </span>
          </div>
          {error && <p className="text-xs text-destructive">{error}</p>}
          <div className="flex gap-2 flex-wrap">
            <button
              onClick={onGenerate}
              disabled={generating}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm border rounded-md hover:bg-accent disabled:opacity-50"
            >
              {generating ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
              AI 生成
            </button>
            <button
              onClick={onSend}
              disabled={sending || !draft.trim()}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-primary text-primary-foreground rounded-md hover:bg-primary/90 disabled:opacity-50"
            >
              {sending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Send className="h-3.5 w-3.5" />}
              回复
            </button>
            <button
              onClick={onQuote}
              disabled={quoting || !draft.trim()}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm border border-primary text-primary rounded-md hover:bg-primary/10 disabled:opacity-50"
            >
              {quoting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Repeat2 className="h-3.5 w-3.5" />}
              引用转发
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
