import { useEffect, useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { FileText, Clock, CheckCircle, XCircle, Send } from 'lucide-react'
import { tweetsApi } from '@/services/api'
import type { Tweet } from '@/types'
import { formatDate, getStatusColor, getStatusText } from '@/lib/utils'

interface Stats {
  total: number
  draft: number
  scheduled: number
  published: number
  failed: number
}

export default function Dashboard() {
  const [stats, setStats] = useState<Stats>({
    total: 0,
    draft: 0,
    scheduled: 0,
    published: 0,
    failed: 0,
  })
  const [recentTweets, setRecentTweets] = useState<Tweet[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    try {
      const [all, drafts, scheduled, published, failed] = await Promise.all([
        tweetsApi.list(undefined, 0, 5),
        tweetsApi.list('draft', 0, 1),
        tweetsApi.list('scheduled', 0, 1),
        tweetsApi.list('published', 0, 1),
        tweetsApi.list('failed', 0, 1),
      ])

      setStats({
        total: all.total,
        draft: drafts.total,
        scheduled: scheduled.total,
        published: published.total,
        failed: failed.total,
      })
      setRecentTweets(all.items)
    } catch (error) {
      console.error('Failed to load dashboard data:', error)
    } finally {
      setLoading(false)
    }
  }

  const statCards = [
    { label: '总推文', value: stats.total, icon: FileText, color: 'text-blue-500' },
    { label: '草稿', value: stats.draft, icon: Clock, color: 'text-gray-500' },
    { label: '已排期', value: stats.scheduled, icon: Send, color: 'text-yellow-500' },
    { label: '已发布', value: stats.published, icon: CheckCircle, color: 'text-green-500' },
    { label: '失败', value: stats.failed, icon: XCircle, color: 'text-red-500' },
  ]

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold">数据看板</h2>
        <p className="text-muted-foreground">查看推文发布统计和最近动态</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-4">
        {statCards.map((stat) => (
          <Card key={stat.label}>
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">{stat.label}</p>
                  <p className="text-3xl font-bold">{stat.value}</p>
                </div>
                <stat.icon className={`h-8 w-8 ${stat.color}`} />
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>最近推文</CardTitle>
        </CardHeader>
        <CardContent>
          {recentTweets.length === 0 ? (
            <p className="text-muted-foreground text-center py-8">暂无推文</p>
          ) : (
            <div className="space-y-4">
              {recentTweets.map((tweet) => (
                <div
                  key={tweet.id}
                  className="flex items-start justify-between p-4 border rounded-lg"
                >
                  <div className="flex-1 min-w-0">
                    <p className="text-sm line-clamp-2">{tweet.content}</p>
                    <p className="text-xs text-muted-foreground mt-1">
                      {formatDate(tweet.created_at)}
                    </p>
                  </div>
                  <Badge className={getStatusColor(tweet.status)}>
                    {getStatusText(tweet.status)}
                  </Badge>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
