import { BrowserRouter, Navigate, Routes, Route } from 'react-router-dom'
import Layout from '@/components/Layout'
import Tweets from '@/pages/Tweets'
import CalendarPage from '@/pages/Calendar'
import Media from '@/pages/Media'
import Settings from '@/pages/Settings'
import Engage from '@/pages/Engage'
import Monitor from '@/pages/Monitor'
import Conversations from '@/pages/Conversations'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Navigate to="/tweets" replace />} />
          <Route path="/tweets" element={<Tweets />} />
          <Route path="/calendar" element={<CalendarPage />} />
          <Route path="/media" element={<Media />} />
          <Route path="/engage" element={<Engage />} />
          <Route path="/monitor" element={<Monitor />} />
          <Route path="/conversations" element={<Conversations />} />
          <Route path="/settings" element={<Settings />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
