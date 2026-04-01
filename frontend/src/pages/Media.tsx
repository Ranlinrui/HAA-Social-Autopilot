import { AxiosError } from 'axios'
import { useEffect, useState, useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import { Upload, Trash2, Image as ImageIcon, Video } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { InlineConfirm } from '@/components/InlineConfirm'
import { InlineNotice } from '@/components/InlineNotice'
import { Badge } from '@/components/ui/badge'
import { mediaApi, formatTwitterActionError, logClientError } from '@/services/api'
import { useMediaStore } from '@/stores'
import { formatFileSize } from '@/lib/utils'

const getMediaUrl = (filepath: string) => `/uploads/${filepath.split('/').slice(-3).join('/')}`

export default function Media() {
  const { mediaList, total, loading, setMediaList, setLoading, addMedia, removeMedia } =
    useMediaStore()

  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState('')
  const [loadError, setLoadError] = useState('')
  const [actionMessage, setActionMessage] = useState<{ tone: 'error' | 'success' | 'info'; title: string; message: string } | null>(null)
  const [pendingDeleteId, setPendingDeleteId] = useState<number | null>(null)

  const loadMedia = useCallback(async () => {
    setLoading(true)
    try {
      setLoadError('')
      const res = await mediaApi.list()
      setMediaList(res.items, res.total)
    } catch (error) {
      logClientError('Media.loadMedia', error)
      setLoadError(formatTwitterActionError(error, '素材列表加载失败'))
    } finally {
      setLoading(false)
    }
  }, [setLoading, setMediaList])

  useEffect(() => {
    loadMedia()
  }, [loadMedia])

  const onDrop = useCallback(
    async (acceptedFiles: File[]) => {
      setUploadError('')
      setUploading(true)
      try {
        const uploadedMedia = await Promise.all(acceptedFiles.map((file) => mediaApi.upload(file)))
        uploadedMedia.forEach((media) => addMedia(media))
      } catch (error) {
        logClientError('Media.onDrop', error)
        const message = error instanceof AxiosError
          ? formatTwitterActionError({ response: error.response, message: error.message }, '上传失败，请稍后重试')
          : formatTwitterActionError({ message: error instanceof Error ? error.message : String(error || '') }, '上传失败，请稍后重试')
        setUploadError(String(message))
      } finally {
        setUploading(false)
      }
    },
    [addMedia]
  )

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    onDropRejected: (fileRejections) => {
      const firstError = fileRejections[0]?.errors[0]
      if (firstError?.code === 'file-too-large') {
        setUploadError('文件过大，当前素材库单文件上限为 100MB。')
        return
      }
      if (firstError?.code === 'file-invalid-type') {
        setUploadError('文件格式不支持，目前仅支持 JPG、PNG、GIF、WebP、MP4、MOV。')
        return
      }
      setUploadError(firstError?.message || '文件校验失败，请检查后重试。')
    },
    accept: {
      'image/*': ['.jpg', '.jpeg', '.png', '.gif', '.webp'],
      'video/*': ['.mp4', '.mov'],
    },
    maxSize: 100 * 1024 * 1024,
  })

  const handleDelete = async (id: number) => {
    try {
      await mediaApi.delete(id)
      removeMedia(id)
      setPendingDeleteId(null)
      setActionMessage({ tone: 'success', title: '素材已删除', message: '该素材已从素材库移除。' })
    } catch (error) {
      logClientError('Media.handleDelete', error)
      setActionMessage({ tone: 'error', title: '删除素材失败', message: formatTwitterActionError(error, '删除素材失败') })
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
      <div>
        <h2 className="text-2xl font-bold">素材库</h2>
        <p className="text-muted-foreground">管理图片和视频素材</p>
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

      {pendingDeleteId !== null && (
        <InlineConfirm
          title="确认删除素材"
          message="删除后该图片或视频将从素材库移除，相关草稿里也无法再继续引用它。"
          confirmLabel="确认删除"
          onConfirm={() => handleDelete(pendingDeleteId)}
          onCancel={() => setPendingDeleteId(null)}
        />
      )}

      {loadError && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900">
          <div className="font-medium">素材页加载失败</div>
          <div className="mt-1">{loadError}</div>
          <div className="mt-2">
            <Button type="button" variant="outline" size="sm" onClick={loadMedia}>
              重新加载
            </Button>
          </div>
        </div>
      )}

      <Card>
        <CardContent className="p-6">
          <div
            {...getRootProps()}
            className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
              isDragActive
                ? 'border-primary bg-primary/5'
                : 'border-border hover:border-primary/50'
            }`}
          >
            <input {...getInputProps()} />
            <Upload className="h-12 w-12 mx-auto mb-4 text-muted-foreground" />
            {uploading ? (
              <p className="text-muted-foreground">上传中...</p>
            ) : isDragActive ? (
              <p className="text-primary">释放文件以上传</p>
            ) : (
              <>
                <p className="text-muted-foreground">拖放文件到这里，或点击选择文件</p>
                <p className="text-sm text-muted-foreground mt-2">
                  支持 JPG, PNG, GIF, WebP, MP4, MOV (最大 100MB)
                </p>
              </>
            )}
          </div>
          {uploadError ? (
            <p className="mt-3 text-sm text-red-500">{uploadError}</p>
          ) : null}
        </CardContent>
      </Card>

      <div className="flex items-center justify-between">
        <p className="text-muted-foreground">共 {total} 个素材</p>
      </div>

      {mediaList.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-muted-foreground">暂无素材，上传一些图片或视频吧</p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
          {mediaList.map((media) => (
            <Card key={media.id} className="group relative overflow-hidden">
              <div className="aspect-square relative bg-muted">
                {media.media_type === 'image' ? (
                  <img
                    src={getMediaUrl(media.filepath)}
                    alt={media.original_filename}
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <video
                    src={getMediaUrl(media.filepath)}
                    className="w-full h-full object-cover"
                    preload="metadata"
                    controls
                    muted
                    playsInline
                  />
                )}

                <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center pointer-events-none group-hover:pointer-events-auto">
                  <Button
                    size="icon"
                    variant="destructive"
                    onClick={() => setPendingDeleteId(media.id)}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>

                <Badge className="absolute top-2 left-2" variant="secondary">
                  {media.media_type === 'image' ? (
                    <ImageIcon className="h-3 w-3 mr-1" />
                  ) : (
                    <Video className="h-3 w-3 mr-1" />
                  )}
                  {media.media_type}
                </Badge>
              </div>

              <CardContent className="p-3">
                <p className="text-sm truncate" title={media.original_filename}>
                  {media.original_filename}
                </p>
                <div className="flex items-center justify-between text-xs text-muted-foreground mt-1 gap-2">
                  <span>{media.file_size ? formatFileSize(media.file_size) : '-'}</span>
                  {media.width && media.height ? (
                    <span>
                      {media.width}x{media.height}
                    </span>
                  ) : (
                    <span>{media.media_type === 'video' ? '视频' : '-'}</span>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
