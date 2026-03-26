export type TweetStatus = 'draft' | 'scheduled' | 'publishing' | 'published' | 'failed'
export type TweetType = 'text' | 'image' | 'video'
export type MediaType = 'image' | 'video'

export interface Media {
  id: number
  filename: string
  original_filename: string
  filepath: string
  media_type: MediaType
  mime_type?: string
  file_size?: number
  width?: number
  height?: number
  tags?: string
  created_at: string
}

export interface Tweet {
  id: number
  content: string
  tweet_type: TweetType
  status: TweetStatus
  scheduled_at?: string
  published_at?: string
  twitter_id?: string
  error_message?: string
  retry_count: number
  created_at: string
  updated_at: string
  media_items: Media[]
}

export interface TweetListResponse {
  total: number
  items: Tweet[]
}

export interface MediaListResponse {
  total: number
  items: Media[]
}

export interface LLMTemplate {
  id: string
  name: string
  description: string
  prompt: string
}

export interface GenerateRequest {
  topic: string
  style?: string
  language?: string
  max_length?: number
  template_id?: string
}

export interface GenerateResponse {
  content: string
  tokens_used?: number
}

export interface Settings {
  twitter_publish_mode: string
  twitter_mode_test_connection: string
  twitter_mode_publish: string
  twitter_mode_search: string
  twitter_mode_reply: string
  twitter_mode_retweet: string
  twitter_mode_quote: string
  twitter_mode_mentions: string
  twitter_mode_tweet_lookup: string
  llm_model: string
  llm_api_base: string
  [key: string]: string
}
