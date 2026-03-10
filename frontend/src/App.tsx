import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from '@/components/Layout'
import Dashboard from '@/pages/Dashboard'
import Tweets from '@/pages/Tweets'
import CalendarPage from '@/pages/Calendar'
import Media from '@/pages/Media'
import Settings from '@/pages/Settings'
import Engage from '@/pages/Engage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/tweets" element={<Tweets />} />
          <Route path="/calendar" element={<CalendarPage />} />
          <Route path="/media" element={<Media />} />
          <Route path="/engage" element={<Engage />} />
          <Route path="/settings" element={<Settings />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
