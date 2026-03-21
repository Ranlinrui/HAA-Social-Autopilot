import { useEffect, useState } from 'react'
import { Plus, Trash2, Send, Clock, Sparkles, ImagePlus, X, Check, Video } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Textarea } from '@/components/ui/textarea'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { tweetsApi, llmApi, mediaApi } from '@/services/api'
import { useTweetStore } from '@/stores'
import { formatDate, getStatusColor, getStatusText } from '@/lib/utils'
import type { LLMTemplate, Media } from '@/types'

const getMediaUrl = (filepath: string) => `/uploads/${filepath.split('/').slice(-3).join('/')}`

export default function Tweets() {
  const { tweets, loading, setTweets, setLoading, addTweet, updateTweet, removeTweet } =
    useTweetStore()

  const [showCreate, setShowCreate] = useState(false)
  const [content, setContent] = useState('')
  const [templates, setTemplates] = useState<LLMTemplate[]>([])
  const [selectedTemplate, setSelectedTemplate] = useState('')
  const [topic, setTopic] = useState('')
  const [generating, setGenerating] = useState(false)
  const [scheduling, setScheduling] = useState<number | null>(null)
  const [scheduleTime, setScheduleTime] = useState('')

  const [showMediaPicker, setShowMediaPicker] = useState(false)
  const [mediaList, setMediaList] = useState<Media[]>([])
  const [selectedMediaIds, setSelectedMediaIds] = useState<number[]>([])

  const selectedMedia = selectedMediaIds
    .map((id) => mediaList.find((item) => item.id === id))
    .filter((item): item is Media => Boolean(item))
  const hasSelectedVideo = selectedMedia.some((item) => item.media_type === 'video')

  useEffect(() => {
    loadTweets()
    loadTemplates()
  }, [])

  const loadTweets = async () => {
    setLoading(true)
    try {
      const res = await tweetsApi.list()
      setTweets(res.items, res.total)
    } catch (error) {
      console.error('Failed to load tweets:', error)
    } finally {
      setLoading(false)
    }
  }

  const loadTemplates = async () => {
    try {
      const res = await llmApi.getTemplates()
      setTemplates(res)
    } catch (error) {
      console.error('Failed to load templates:', error)
    }
  }

  const loadMediaList = async () => {
    try {
      const res = await mediaApi.list()
      setMediaList(res.items)
    } catch (error) {
      console.error('Failed to load media:', error)
    }
  }

  const toggleMediaSelect = (media: Media) => {
    setSelectedMediaIds((prev) => {
      if (prev.includes(media.id)) {
        return prev.filter((id) => id !== media.id)
      }

      const selectedItems = prev
        .map((id) => mediaList.find((item) => item.id === id))
        .filter((item): item is Media => Boolean(item))
      const alreadyHasVideo = selectedItems.some((item) => item.media_type === 'video')

      if (media.media_type === 'video') {
        if (selectedItems.length > 0) {
          alert('视频推文当前仅支持单个视频，已替换掉之前选择的素材。')
        }
        return [media.id]
      }

      if (alreadyHasVideo) {
        alert('单条推文不能同时混用视频和图片，请先移除已选视频。')
        return prev
      }

      if (prev.length >= 4) {
        alert('图片素材最多选择 4 张。')
        return prev
      }

      return [...prev, media.id]
    })
  }

  const handleCreate = async () => {
    if (!content.trim()) return

    try {
      const tweetType = hasSelectedVideo ? 'video' : selectedMediaIds.length > 0 ? 'image' : 'text'
      const tweet = await tweetsApi.create({
        content,
        tweet_type: tweetType,
        media_ids: selectedMediaIds.length > 0 ? selectedMediaIds : undefined,
      })
      addTweet(tweet)
      setContent('')
      setSelectedMediaIds([])
      setShowMediaPicker(false)
      setShowCreate(false)
    } catch (error) {
      console.error('Failed to create tweet:', error)
    }
  }

  const handleDelete = async (id: number) => {
    if (!confirm('确定要删除这条推文吗?')) return

    try {
      await tweetsApi.delete(id)
      removeTweet(id)
    } catch (error) {
      console.error('Failed to delete tweet:', error)
    }
  }

  const handlePublish = async (id: number) => {
    try {
      const tweet = await tweetsApi.publish(id)
      updateTweet(tweet)
    } catch (error) {
      console.error('Failed to publish tweet:', error)
    }
  }

  const handleSchedule = async (id: number) => {
    if (!scheduleTime) return

    try {
      const tweet = await tweetsApi.schedule(id, new Date(scheduleTime).toISOString())
      updateTweet(tweet)
      setScheduling(null)
      setScheduleTime('')
    } catch (error) {
      console.error('Failed to schedule tweet:', error)
    }
  }

  const handleGenerate = async () => {
    if (!topic.trim()) return

    setGenerating(true)
    try {
      const res = await llmApi.generate({
        topic,
        template_id: selectedTemplate || undefined,
      })
      setContent(res.content)
    } catch (error) {
      console.error('Failed to generate content:', error)
    } finally {
      setGenerating(false)
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
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">推文管理</h2>
          <p className="text-muted-foreground">管理和发布你的推文内容</p>
        </div>
        <Button onClick={() => setShowCreate(true)}>
          <Plus className="h-4 w-4 mr-2" />
          新建推文
        </Button>
      </div>

      {showCreate && (
        <Card>
          <CardHeader>
            <CardTitle>创建新推文</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <Input
                placeholder="粘贴素材内容（AI 推理、交易数据、故事细节...）"
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
              />
              <select
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={selectedTemplate}
                onChange={(e) => setSelectedTemplate(e.target.value)}
              >
                <option value="">选择素材类型...</option>
                {templates.map((t) => (
                  <option key={t.id} value={t.id} title={t.description}>
                    {t.name}
                  </option>
                ))}
              </select>
              <Button onClick={handleGenerate} disabled={generating || !topic.trim()}>
                <Sparkles className="h-4 w-4 mr-2" />
                {generating ? '生成中...' : 'AI生成'}
              </Button>
            </div>

            <Textarea
              placeholder="输入推文内容..."
              value={content}
              onChange={(e) => setContent(e.target.value)}
              rows={4}
            />

            {selectedMediaIds.length > 0 && (
              <div className="flex gap-2 flex-wrap">
                {selectedMedia.map((media) => (
                  <div key={media.id} className="relative group">
                    {media.media_type === 'image' ? (
                      <img
                        src={getMediaUrl(media.filepath)}
                        alt={media.original_filename}
                        className="h-16 w-16 object-cover rounded border"
                      />
                    ) : (
                      <video
                        src={getMediaUrl(media.filepath)}
                        className="h-16 w-16 object-cover rounded border bg-black"
                        preload="metadata"
                        muted
                        playsInline
                      />
                    )}
                    <button
                      onClick={() => toggleMediaSelect(media)}
                      className="absolute -top-1.5 -right-1.5 bg-destructive text-white rounded-full p-0.5 opacity-0 group-hover:opacity-100 transition-opacity"
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </div>
                ))}
              </div>
            )}

            {showMediaPicker && (
              <div className="border rounded-lg p-3 bg-muted/30 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium">选择素材（最多 4 张图片或 1 个视频）</span>
                  <button
                    onClick={() => setShowMediaPicker(false)}
                    className="text-muted-foreground hover:text-foreground"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>
                {mediaList.length === 0 ? (
                  <p className="text-sm text-muted-foreground py-4 text-center">
                    素材库为空，请先到素材库上传图片或视频
                  </p>
                ) : (
                  <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-2 max-h-72 overflow-y-auto">
                    {mediaList.map((media) => (
                      <button
                        key={media.id}
                        onClick={() => toggleMediaSelect(media)}
                        className={`relative aspect-square rounded border-2 overflow-hidden transition-colors ${
                          selectedMediaIds.includes(media.id)
                            ? 'border-primary'
                            : 'border-transparent hover:border-muted-foreground'
                        }`}
                        title={media.original_filename}
                      >
                        {media.media_type === 'image' ? (
                          <img
                            src={getMediaUrl(media.filepath)}
                            alt={media.original_filename}
                            className="w-full h-full object-cover"
                          />
                        ) : (
                          <video
                            src={getMediaUrl(media.filepath)}
                            className="w-full h-full object-cover bg-black"
                            preload="metadata"
                            muted
                            playsInline
                          />
                        )}
                        <div className="absolute left-1 top-1 rounded bg-black/65 px-1.5 py-0.5 text-[10px] text-white flex items-center gap-1">
                          {media.media_type === 'video' ? <Video className="h-3 w-3" /> : null}
                          <span>{media.media_type === 'video' ? '视频' : '图片'}</span>
                        </div>
                        {selectedMediaIds.includes(media.id) && (
                          <div className="absolute inset-0 bg-primary/20 flex items-center justify-center">
                            <Check className="h-5 w-5 text-primary" />
                          </div>
                        )}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}

            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3 flex-wrap">
                <span className="text-sm text-muted-foreground">{content.length}/280</span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setShowMediaPicker((v) => !v)
                    if (!showMediaPicker) loadMediaList()
                  }}
                >
                  <ImagePlus className="h-4 w-4 mr-1" />
                  {hasSelectedVideo
                    ? '已选 1 个视频'
                    : selectedMediaIds.length > 0
                      ? `已选 ${selectedMediaIds.length} 个素材`
                      : '选择素材'}
                </Button>
                {hasSelectedVideo ? (
                  <span className="text-xs text-muted-foreground">视频模式下仅支持单个视频</span>
                ) : (
                  <span className="text-xs text-muted-foreground">图片模式最多可选 4 张</span>
                )}
              </div>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  onClick={() => {
                    setShowCreate(false)
                    setShowMediaPicker(false)
                    setSelectedMediaIds([])
                  }}
                >
                  取消
                </Button>
                <Button onClick={handleCreate} disabled={!content.trim() || content.length > 280}>
                  保存草稿
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      <div className="space-y-4">
        {tweets.length === 0 ? (
          <Card>
            <CardContent className="py-12 text-center">
              <p className="text-muted-foreground">暂无推文，点击"新建推文"开始创建</p>
            </CardContent>
          </Card>
        ) : (
          tweets.map((tweet) => (
            <Card key={tweet.id}>
              <CardContent className="p-4">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <p className="whitespace-pre-wrap">{tweet.content}</p>
                    {tweet.media_items.length > 0 && (
                      <div className="mt-3 flex flex-wrap gap-2">
                        {tweet.media_items.map((media) => (
                          <div key={media.id} className="relative">
                            {media.media_type === 'image' ? (
                              <img
                                src={getMediaUrl(media.filepath)}
                                alt={media.filename}
                                className="h-20 w-20 object-cover rounded border"
                              />
                            ) : (
                              <video
                                src={getMediaUrl(media.filepath)}
                                className="h-20 w-20 object-cover rounded border bg-black"
                                preload="metadata"
                                muted
                                playsInline
                              />
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                    <div className="flex items-center gap-4 mt-2 text-sm text-muted-foreground">
                      <span>创建于 {formatDate(tweet.created_at)}</span>
                      {tweet.scheduled_at && <span>排期: {formatDate(tweet.scheduled_at)}</span>}
                      {tweet.published_at && <span>发布于 {formatDate(tweet.published_at)}</span>}
                    </div>
                    {tweet.error_message && (
                      <p className="text-sm text-red-500 mt-1">{tweet.error_message}</p>
                    )}
                  </div>

                  <div className="flex items-center gap-2">
                    <Badge className={getStatusColor(tweet.status)}>{getStatusText(tweet.status)}</Badge>

                    {tweet.status === 'draft' && (
                      <>
                        {scheduling === tweet.id ? (
                          <div className="flex items-center gap-2">
                            <Input
                              type="datetime-local"
                              value={scheduleTime}
                              onChange={(e) => setScheduleTime(e.target.value)}
                              className="w-48"
                            />
                            <Button size="sm" onClick={() => handleSchedule(tweet.id)}>
                              确定
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => setScheduling(null)}
                            >
                              取消
                            </Button>
                          </div>
                        ) : (
                          <>
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => setScheduling(tweet.id)}
                            >
                              <Clock className="h-4 w-4" />
                            </Button>
                            <Button size="sm" onClick={() => handlePublish(tweet.id)}>
                              <Send className="h-4 w-4" />
                            </Button>
                          </>
                        )}
                      </>
                    )}

                    {(tweet.status === 'draft' || tweet.status === 'failed') && (
                      <Button size="sm" variant="ghost" onClick={() => handleDelete(tweet.id)}>
                        <Trash2 className="h-4 w-4 text-red-500" />
                      </Button>
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>
          ))
        )}
      </div>
    </div>
  )
}
