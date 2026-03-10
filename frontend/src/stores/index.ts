import { create } from 'zustand'
import type { Tweet, Media, TweetStatus } from '@/types'

interface TweetStore {
  tweets: Tweet[]
  total: number
  loading: boolean
  currentTweet: Tweet | null
  filter: TweetStatus | null
  setTweets: (tweets: Tweet[], total: number) => void
  setLoading: (loading: boolean) => void
  setCurrentTweet: (tweet: Tweet | null) => void
  setFilter: (filter: TweetStatus | null) => void
  addTweet: (tweet: Tweet) => void
  updateTweet: (tweet: Tweet) => void
  removeTweet: (id: number) => void
}

export const useTweetStore = create<TweetStore>((set) => ({
  tweets: [],
  total: 0,
  loading: false,
  currentTweet: null,
  filter: null,
  setTweets: (tweets, total) => set({ tweets, total }),
  setLoading: (loading) => set({ loading }),
  setCurrentTweet: (currentTweet) => set({ currentTweet }),
  setFilter: (filter) => set({ filter }),
  addTweet: (tweet) => set((state) => ({
    tweets: [tweet, ...state.tweets],
    total: state.total + 1
  })),
  updateTweet: (tweet) => set((state) => ({
    tweets: state.tweets.map((t) => (t.id === tweet.id ? tweet : t)),
  })),
  removeTweet: (id) => set((state) => ({
    tweets: state.tweets.filter((t) => t.id !== id),
    total: state.total - 1
  })),
}))

interface MediaStore {
  mediaList: Media[]
  total: number
  loading: boolean
  selectedMedia: Media[]
  setMediaList: (mediaList: Media[], total: number) => void
  setLoading: (loading: boolean) => void
  setSelectedMedia: (media: Media[]) => void
  addMedia: (media: Media) => void
  removeMedia: (id: number) => void
  toggleSelectMedia: (media: Media) => void
  clearSelection: () => void
}

export const useMediaStore = create<MediaStore>((set) => ({
  mediaList: [],
  total: 0,
  loading: false,
  selectedMedia: [],
  setMediaList: (mediaList, total) => set({ mediaList, total }),
  setLoading: (loading) => set({ loading }),
  setSelectedMedia: (selectedMedia) => set({ selectedMedia }),
  addMedia: (media) => set((state) => ({
    mediaList: [media, ...state.mediaList],
    total: state.total + 1
  })),
  removeMedia: (id) => set((state) => ({
    mediaList: state.mediaList.filter((m) => m.id !== id),
    total: state.total - 1
  })),
  toggleSelectMedia: (media) => set((state) => {
    const exists = state.selectedMedia.find((m) => m.id === media.id)
    if (exists) {
      return { selectedMedia: state.selectedMedia.filter((m) => m.id !== media.id) }
    }
    return { selectedMedia: [...state.selectedMedia, media] }
  }),
  clearSelection: () => set({ selectedMedia: [] }),
}))

interface UIStore {
  sidebarOpen: boolean
  theme: 'light' | 'dark'
  toggleSidebar: () => void
  setTheme: (theme: 'light' | 'dark') => void
}

export const useUIStore = create<UIStore>((set) => ({
  sidebarOpen: true,
  theme: 'light',
  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
  setTheme: (theme) => set({ theme }),
}))
