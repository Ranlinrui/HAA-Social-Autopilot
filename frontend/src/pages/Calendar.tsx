import { useEffect, useState } from 'react'
import { Calendar as CalendarIcon, ChevronLeft, ChevronRight } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { tweetsApi } from '@/services/api'
import type { Tweet } from '@/types'
import { getStatusColor, getStatusText } from '@/lib/utils'

export default function CalendarPage() {
  const [tweets, setTweets] = useState<Tweet[]>([])
  const [currentDate, setCurrentDate] = useState(new Date())
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadTweets()
  }, [])

  const loadTweets = async () => {
    try {
      const res = await tweetsApi.list('scheduled', 0, 100)
      setTweets(res.items)
    } catch (error) {
      console.error('Failed to load scheduled tweets:', error)
    } finally {
      setLoading(false)
    }
  }

  const getDaysInMonth = (date: Date) => {
    const year = date.getFullYear()
    const month = date.getMonth()
    const firstDay = new Date(year, month, 1)
    const lastDay = new Date(year, month + 1, 0)
    const daysInMonth = lastDay.getDate()
    const startingDay = firstDay.getDay()

    return { daysInMonth, startingDay }
  }

  const getTweetsForDay = (day: number) => {
    const year = currentDate.getFullYear()
    const month = currentDate.getMonth()

    return tweets.filter((tweet) => {
      if (!tweet.scheduled_at) return false
      const tweetDate = new Date(tweet.scheduled_at)
      return (
        tweetDate.getFullYear() === year &&
        tweetDate.getMonth() === month &&
        tweetDate.getDate() === day
      )
    })
  }

  const { daysInMonth, startingDay } = getDaysInMonth(currentDate)

  const prevMonth = () => {
    setCurrentDate(new Date(currentDate.getFullYear(), currentDate.getMonth() - 1, 1))
  }

  const nextMonth = () => {
    setCurrentDate(new Date(currentDate.getFullYear(), currentDate.getMonth() + 1, 1))
  }

  const monthNames = [
    '一月', '二月', '三月', '四月', '五月', '六月',
    '七月', '八月', '九月', '十月', '十一月', '十二月'
  ]

  const dayNames = ['日', '一', '二', '三', '四', '五', '六']

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">排期日历</h2>
          <p className="text-muted-foreground">查看和管理推文发布排期</p>
        </div>
        <div className="flex items-center gap-2">
          <CalendarIcon className="h-5 w-5 text-muted-foreground" />
          <span className="text-sm text-muted-foreground">
            {tweets.length} 条待发布推文
          </span>
        </div>
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>
              {currentDate.getFullYear()} {monthNames[currentDate.getMonth()]}
            </CardTitle>
            <div className="flex gap-2">
              <Button variant="outline" size="icon" onClick={prevMonth}>
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <Button variant="outline" size="icon" onClick={nextMonth}>
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-7 gap-px bg-border rounded-lg overflow-hidden">
            {dayNames.map((day) => (
              <div
                key={day}
                className="bg-muted p-2 text-center text-sm font-medium"
              >
                {day}
              </div>
            ))}

            {Array.from({ length: startingDay }).map((_, i) => (
              <div key={`empty-${i}`} className="bg-background p-2 min-h-[100px]" />
            ))}

            {Array.from({ length: daysInMonth }).map((_, i) => {
              const day = i + 1
              const dayTweets = getTweetsForDay(day)
              const isToday =
                new Date().toDateString() ===
                new Date(currentDate.getFullYear(), currentDate.getMonth(), day).toDateString()

              return (
                <div
                  key={day}
                  className={`bg-background p-2 min-h-[100px] border-t ${
                    isToday ? 'ring-2 ring-primary ring-inset' : ''
                  }`}
                >
                  <div className={`text-sm mb-1 ${isToday ? 'font-bold text-primary' : ''}`}>
                    {day}
                  </div>
                  <div className="space-y-1">
                    {dayTweets.slice(0, 3).map((tweet) => (
                      <div
                        key={tweet.id}
                        className="text-xs p-1 bg-primary/10 rounded truncate"
                        title={tweet.content}
                      >
                        {tweet.content.slice(0, 20)}...
                      </div>
                    ))}
                    {dayTweets.length > 3 && (
                      <div className="text-xs text-muted-foreground">
                        +{dayTweets.length - 3} 更多
                      </div>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </CardContent>
      </Card>

      {tweets.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>待发布列表</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {tweets.map((tweet) => (
                <div
                  key={tweet.id}
                  className="flex items-center justify-between p-3 border rounded-lg"
                >
                  <div className="flex-1 min-w-0">
                    <p className="text-sm truncate">{tweet.content}</p>
                    <p className="text-xs text-muted-foreground">
                      {tweet.scheduled_at && new Date(tweet.scheduled_at).toLocaleString('zh-CN')}
                    </p>
                  </div>
                  <Badge className={getStatusColor(tweet.status)}>
                    {getStatusText(tweet.status)}
                  </Badge>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
