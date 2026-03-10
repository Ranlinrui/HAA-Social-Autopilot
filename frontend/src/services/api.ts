import axios from 'axios'
import type {
  Tweet,
  TweetListResponse,
  Media,
  MediaListResponse,
  LLMTemplate,
  GenerateRequest,
  GenerateResponse,
  Settings,
  TweetStatus,
} from '@/types'

const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
})

// Tweets API
export const tweetsApi = {
  list: async (status?: TweetStatus, skip = 0, limit = 20): Promise<TweetListResponse> => {
    const params = new URLSearchParams()
    if (status) params.append('status', status)
    params.append('skip', String(skip))
    params.append('limit', String(limit))
    const res = await api.get(`/tweets?${params}`)
    return res.data
  },

  get: async (id: number): Promise<Tweet> => {
    const res = await api.get(`/tweets/${id}`)
    return res.data
  },

  create: async (data: { content: string; tweet_type?: string; media_ids?: number[] }): Promise<Tweet> => {
    const res = await api.post('/tweets', data)
    return res.data
  },

  update: async (id: number, data: { content?: string; tweet_type?: string; media_ids?: number[] }): Promise<Tweet> => {
    const res = await api.put(`/tweets/${id}`, data)
    return res.data
  },

  delete: async (id: number): Promise<void> => {
    await api.delete(`/tweets/${id}`)
  },

  schedule: async (id: number, scheduled_at: string): Promise<Tweet> => {
    const res = await api.post(`/tweets/${id}/schedule`, { scheduled_at })
    return res.data
  },

  publish: async (id: number): Promise<Tweet> => {
    const res = await api.post(`/tweets/${id}/publish`)
    return res.data
  },
}

// Media API
export const mediaApi = {
  list: async (mediaType?: string, skip = 0, limit = 20): Promise<MediaListResponse> => {
    const params = new URLSearchParams()
    if (mediaType) params.append('media_type', mediaType)
    params.append('skip', String(skip))
    params.append('limit', String(limit))
    const res = await api.get(`/media?${params}`)
    return res.data
  },

  upload: async (file: File, tags?: string): Promise<Media> => {
    const formData = new FormData()
    formData.append('file', file)
    if (tags) formData.append('tags', tags)
    const res = await api.post('/media/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return res.data
  },

  delete: async (id: number): Promise<void> => {
    await api.delete(`/media/${id}`)
  },
}

// LLM API
export const llmApi = {
  getTemplates: async (): Promise<LLMTemplate[]> => {
    const res = await api.get('/llm/templates')
    return res.data
  },

  generate: async (data: GenerateRequest): Promise<GenerateResponse> => {
    const res = await api.post('/llm/generate', data)
    return res.data
  },
}

// Settings API
export const settingsApi = {
  get: async (): Promise<{ settings: Settings }> => {
    const res = await api.get('/settings')
    return res.data
  },

  update: async (key: string, value: string): Promise<void> => {
    await api.put(`/settings/${key}`, { value })
  },

  testTwitter: async (): Promise<{ success: boolean; message: string; username?: string }> => {
    const res = await api.post('/settings/test-twitter')
    return res.data
  },

  twitterLogin: async (username: string, email: string, password?: string): Promise<{ success: boolean; message: string; username?: string }> => {
    const res = await api.post('/settings/twitter-login', { username, email, password })
    return res.data
  },

  testLLM: async (): Promise<{ success: boolean; message: string; model?: string }> => {
    const res = await api.post('/settings/test-llm')
    return res.data
  },
}

export default api
