import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  FileText,
  Calendar,
  Image,
  Settings,
  ChevronLeft,
  ChevronRight,
  Twitter,
  MessageCircle,
} from 'lucide-react'
import { useUIStore } from '@/stores'
import { cn } from '@/lib/utils'

const navItems = [
  { icon: LayoutDashboard, label: '数据看板', path: '/' },
  { icon: FileText, label: '推文管理', path: '/tweets' },
  { icon: Calendar, label: '排期日历', path: '/calendar' },
  { icon: Image, label: '素材库', path: '/media' },
  { icon: MessageCircle, label: '互动引流', path: '/engage' },
  { icon: Settings, label: '系统设置', path: '/settings' },
]

export default function Sidebar() {
  const { sidebarOpen, toggleSidebar } = useUIStore()

  return (
    <aside
      className={cn(
        'fixed left-0 top-0 z-40 h-screen bg-card border-r transition-all duration-300',
        sidebarOpen ? 'w-64' : 'w-16'
      )}
    >
      <div className="flex h-16 items-center justify-between px-4 border-b">
        {sidebarOpen && (
          <div className="flex items-center gap-2">
            <Twitter className="h-6 w-6 text-primary" />
            <span className="font-bold text-lg">HAA Autopilot</span>
          </div>
        )}
        <button
          onClick={toggleSidebar}
          className="p-2 rounded-md hover:bg-accent transition-colors"
        >
          {sidebarOpen ? (
            <ChevronLeft className="h-5 w-5" />
          ) : (
            <ChevronRight className="h-5 w-5" />
          )}
        </button>
      </div>

      <nav className="p-2 space-y-1">
        {navItems.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-3 px-3 py-2 rounded-md transition-colors',
                isActive
                  ? 'bg-primary text-primary-foreground'
                  : 'hover:bg-accent text-muted-foreground hover:text-foreground'
              )
            }
          >
            <item.icon className="h-5 w-5 flex-shrink-0" />
            {sidebarOpen && <span>{item.label}</span>}
          </NavLink>
        ))}
      </nav>
    </aside>
  )
}
