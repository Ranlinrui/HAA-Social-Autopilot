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
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})


export function formatTwitterActionError(error: any, fallback = '操作失败，请稍后重试'): string {
  const detail = String(error?.response?.data?.detail || error?.message || '').trim()
  const normalized = detail.toLowerCase()
  const status = Number(error?.response?.status || error?.status || 0)

  if (!detail) return fallback
  if (normalized.includes('timeout of 30000ms exceeded') || normalized.includes('timeout exceeded') || normalized.includes('ecconnaborted')) {
    return '请求已发出，但后端或上游服务在 30 秒内未返回结果，请稍后重试并检查代理或容器状态。'
  }
  if (status === 502) {
    return '后端当前无法连通 Twitter 或 Browser 服务，接口暂时返回 502。请先检查容器、代理和浏览器执行层是否正常。'
  }
  if (status === 503) {
    return '服务当前暂时不可用，通常是后端任务或浏览器执行层尚未就绪，请稍后再试。'
  }
  if (status === 500) {
    return detail && detail !== 'Internal Server Error' ? detail : '后端处理请求时发生内部错误，请查看后端日志定位具体原因。'
  }
  if (normalized.includes('network error') || normalized.includes('failed to fetch') || normalized.includes('load failed')) {
    return '请求未到达后端，请检查前端与后端连接、反向代理以及容器状态。'
  }
  if (normalized.includes('browser 登录未进入密码输入步骤')) {
    return 'Browser 登录停留在用户名/邮箱步骤，未进入密码输入。通常是 X 额外校验、页面结构变化或当前代理环境触发拦截。'
  }
  if (normalized.includes('browser 模式未登录') || normalized.includes('当前未处于已登录状态')) {
    return '当前 Browser 会话未登录或登录态已失效，请先重新导入 Cookie，必要时再重新登录。'
  }
  if (normalized.includes('javascript 错误页')) {
    return 'X 当前返回了异常浏览器页，通常是会话损坏、浏览器环境异常或代理导致资源加载不完整。建议重置 Browser 会话并重新导入 Cookie。'
  }
  if (normalized.includes('could not log you in now') || normalized.includes('[399]')) {
    return '当前 X/Twitter 拒绝了本次 Browser 密码登录（399）。建议优先导入 Cookie，不要继续频繁尝试账号密码登录。'
  }
  if (normalized.includes('missing twitterusernotsuspended') || normalized.includes('denied by access control') || normalized.includes('[37]') || normalized.includes('code":37') || normalized.includes("code': 37")) {
    return '当前 X/Twitter 账号状态受限或异常，暂时无法发帖互动，请先到网页端确认账号是否被限制。'
  }
  if (normalized.includes('your account is suspended') || normalized.includes('账号状态受限')) {
    return '当前 X/Twitter 账号已受限或被暂停，Browser 模式暂时无法执行搜索、发帖和回复。'
  }
  if (normalized.includes('目标账号不存在') || normalized.includes('读取用户资料失败') || normalized.includes('读取用户时间线失败')) {
    return '目标账号不存在、页面不可访问，或当前账号无权查看该资料页。'
  }
  if (normalized.includes('目标推文不存在') || normalized.includes('未找到推文') || normalized.includes('读取推文失败')) {
    return '目标推文不存在、已删除，或当前账号暂时无权访问该推文页面。'
  }
  if (normalized.includes('读取提及失败')) {
    return '提及页当前无法读取，通常是 Cookie 失效、账号受限，或 X 返回异常页面。'
  }
  if (normalized.includes('something went wrong. try reloading') || normalized.includes('搜索页加载失败') || normalized.includes('提及页加载失败')) {
    return 'X 页面当前返回异常结果，通常与账号限制或会话状态有关，请先在网页端确认账号状态。'
  }
  if (normalized.includes('automated') || normalized.includes('[226]') || normalized.includes('code":226') || normalized.includes("code': 226")) {
    return '当前账号已触发 X/Twitter 自动化风控（226），请先降低频率并等待一段时间后再试。'
  }
  if (normalized.includes('could not authenticate you') || normalized.includes('status: 401') || normalized.includes('code":32') || normalized.includes("code': 32")) {
    return '当前 Twitter 登录态已失效，请重新导入 Cookie 或重新登录。'
  }
  if (normalized.includes('readtimeout') || normalized.includes('timeout') || normalized.includes('524')) {
    return '请求已发出，但在代理或 X 侧超时，请稍后重试。'
  }
  return detail
}

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

  getTwitterAuthState: async (): Promise<{
    feature: string
    selected_mode: string
    default_mode: string
    cookie_configured: boolean
    cookie_validation_mode?: string
    cookie_username?: string
    configured_username?: string
    active_username?: string
    risk_stage?: string
    write_blocked: boolean
    write_block_reason?: string
    write_resume_seconds?: number
    auth_backoff_until?: string
    read_only_until?: string
    recovery_until?: string
    last_risk_error?: string
    last_risk_event_at?: string
  }> => {
    const res = await api.get('/settings/twitter-auth-state')
    return res.data
  },

  getTwitterRiskAccounts: async (): Promise<Array<{
    risk_account_key: string
    risk_stage: string
    is_persisted: boolean
    is_active_display_only: boolean
    write_blocked: boolean
    write_block_reason?: string
    write_resume_seconds?: number
    auth_backoff_until?: string
    read_only_until?: string
    recovery_until?: string
    last_risk_error?: string
    last_risk_event_at?: string
  }>> => {
    const res = await api.get('/settings/twitter-risk-accounts')
    return res.data
  },

  resetTwitterRiskAccount: async (accountKey: string): Promise<{ success: boolean; message: string; removed: boolean }> => {
    const res = await api.delete(`/settings/twitter-risk-accounts/${encodeURIComponent(accountKey)}`)
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
