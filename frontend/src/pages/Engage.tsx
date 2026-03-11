import { useState } from 'react'
import { Search, Send, Loader2, ExternalLink, RefreshCw } from 'lucide-react'
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
  const [sent, setSent] = useState<Record<string, boolean>>({})
  const [replyErrors, setReplyErrors] = useState<Record<string, string>>({})

  async function handleSearch(q?: string) {
    const searchQuery = q ?? query
    if (!searchQuery.trim()) return
    setSearching(true)
    setSearchError('')
    setResults([])
    setSent({})
    try {
      const res = await api.post('/engage/search', { query: searchQuery, count: 20 })
      setResults(res.data)
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

  async function handleSendReply(tweetId: string) {
    const content = replyDrafts[tweetId]
    if (!content?.trim()) return
    setSending(prev => ({ ...prev, [tweetId]: true }))
    setReplyErrors(prev => ({ ...prev, [tweetId]: '' }))
    try {
      await api.post(`/engage/reply/${tweetId}`, { content })
      setSent(prev => ({ ...prev, [tweetId]: true }))
      setReplyDrafts(prev => ({ ...prev, [tweetId]: '' }))
    } catch (e: any) {
      setReplyErrors(prev => ({ ...prev, [tweetId]: e.response?.data?.detail || '发送失败' }))
    } finally {
      setSending(prev => ({ ...prev, [tweetId]: false }))
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

      {/* 搜索结果 */}
      {results.length > 0 && (
        <div className="space-y-4">
          <p className="text-sm text-muted-foreground">找到 {results.length} 条推文</p>
          {results.map(tweet => (
            <TweetCard
              key={tweet.id}
              tweet={tweet}
              draft={replyDrafts[tweet.id] || ''}
              generating={generating[tweet.id] || false}
              sending={sending[tweet.id] || false}
              sent={sent[tweet.id] || false}
              error={replyErrors[tweet.id] || ''}
              onDraftChange={val => setReplyDrafts(prev => ({ ...prev, [tweet.id]: val }))}
              onGenerate={() => handleGenerateReply(tweet)}
              onSend={() => handleSendReply(tweet.id)}
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
  sent: boolean
  error: string
  onDraftChange: (val: string) => void
  onGenerate: () => void
  onSend: () => void
}

function TweetCard({ tweet, draft, generating, sending, sent, error, onDraftChange, onGenerate, onSend }: TweetCardProps) {
  const charCount = draft.length

  return (
    <div className="border rounded-lg p-4 space-y-3 bg-card">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="font-medium text-sm">{tweet.author_name}</span>
            <span className="text-muted-foreground text-sm">@{tweet.author_username}</span>
            {tweet.author_verified && (
              <span className="text-xs bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded">蓝V</span>
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

      {sent ? (
        <div className="p-2 rounded bg-green-50 text-green-700 text-sm">已发送回复</div>
      ) : (
        <div className="space-y-2">
          <div className="relative">
            <textarea
              className="w-full px-3 py-2 text-sm rounded-md border bg-background focus:outline-none focus:ring-2 focus:ring-primary resize-none"
              rows={3}
              placeholder="点击「AI 生成」获取回复草稿，或直接输入..."
              value={draft}
              onChange={e => onDraftChange(e.target.value)}
              maxLength={280}
            />
            <span className={`absolute bottom-2 right-2 text-xs ${charCount > 260 ? 'text-destructive' : 'text-muted-foreground'}`}>
              {charCount}/280
            </span>
          </div>
          {error && <p className="text-xs text-destructive">{error}</p>}
          <div className="flex gap-2">
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
              发送回复
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
