import { useState } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import {
  BookOpen,
  PlusCircle,
  CalendarDays,
  Download,
  Clock,
  ShieldBan,
  Settings,
  ChevronDown,
  ChevronRight,
  X,
  HardDrive,
  Search,
  Bell,
  Layers,
  FolderOpen,
  FileText,
  Database,
  Monitor,
  Wrench,
} from 'lucide-react'

const MAIN_NAV = [
  { path: '/', labelKey: 'nav.library', icon: BookOpen },
  { path: '/add', labelKey: 'nav.addMagazine', icon: PlusCircle },
  { path: '/calendar', labelKey: 'nav.calendar', icon: CalendarDays },
  { path: '/queue', labelKey: 'nav.queue', icon: Download },
  { path: '/history', labelKey: 'nav.history', icon: Clock },
  { path: '/blocklist', labelKey: 'nav.blocklist', icon: ShieldBan },
]

const SETTINGS_NAV = [
  { path: '/settings/general', labelKey: 'nav.settingsGeneral', icon: Wrench },
  { path: '/settings/download-clients', labelKey: 'nav.settingsDownloadClients', icon: HardDrive },
  { path: '/settings/indexers', labelKey: 'nav.settingsIndexers', icon: Search },
  { path: '/settings/notifications', labelKey: 'nav.settingsNotifications', icon: Bell },
  { path: '/settings/quality-profiles', labelKey: 'nav.settingsQuality', icon: Layers },
  { path: '/settings/root-folders', labelKey: 'nav.settingsRootFolders', icon: FolderOpen },
  { path: '/settings/naming', labelKey: 'nav.settingsNaming', icon: FileText },
  { path: '/settings/metadata', labelKey: 'nav.settingsMetadata', icon: Database },
  { path: '/settings/system', labelKey: 'nav.settingsSystem', icon: Monitor },
]

interface SidebarProps {
  open: boolean
  onClose: () => void
}

export function Sidebar({ open, onClose }: SidebarProps) {
  const { t } = useTranslation()
  const location = useLocation()
  const isSettingsPage = location.pathname.startsWith('/settings')
  const [settingsOpen, setSettingsOpen] = useState(isSettingsPage)

  return (
    <>
      {/* Overlay on mobile */}
      {open && (
        <div
          className="fixed inset-0 bg-black/60 z-40 lg:hidden"
          onClick={onClose}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`
          fixed top-0 left-0 z-50 h-screen w-60 bg-zinc-950 border-r border-zinc-800
          flex flex-col transition-transform duration-200 ease-in-out
          lg:static lg:translate-x-0
          ${open ? 'translate-x-0' : '-translate-x-full'}
        `}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-800">
          <NavLink to="/" onClick={onClose} className="flex items-center gap-2">
            <img src="/logo.svg" alt="Pressarr" className="size-7 rounded" />
            <span className="text-xl font-bold text-[#7C3AED]">Pressarr</span>
          </NavLink>
          <button
            onClick={onClose}
            className="p-1 rounded text-zinc-400 hover:text-zinc-100 lg:hidden"
          >
            <X className="size-5" />
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto py-2">
          {/* Main nav */}
          {MAIN_NAV.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.path === '/'}
              onClick={onClose}
              className={({ isActive }) =>
                `flex items-center gap-3 px-4 py-2.5 text-sm transition-colors ${
                  isActive
                    ? 'text-[#7C3AED] bg-zinc-900/80'
                    : 'text-zinc-400 hover:text-zinc-100 hover:bg-zinc-900/50'
                }`
              }
            >
              <item.icon className="size-4 shrink-0" />
              {t(item.labelKey)}
            </NavLink>
          ))}

          {/* Settings section */}
          <div className="mt-2 pt-2 border-t border-zinc-800/60">
            <button
              onClick={() => setSettingsOpen(!settingsOpen)}
              className={`flex items-center gap-3 px-4 py-2.5 text-sm w-full transition-colors ${
                isSettingsPage
                  ? 'text-[#7C3AED]'
                  : 'text-zinc-400 hover:text-zinc-100 hover:bg-zinc-900/50'
              }`}
            >
              <Settings className="size-4 shrink-0" />
              <span className="flex-1 text-left">{t('nav.settings')}</span>
              {settingsOpen ? (
                <ChevronDown className="size-3.5" />
              ) : (
                <ChevronRight className="size-3.5" />
              )}
            </button>

            {settingsOpen && (
              <div className="ml-3 border-l border-zinc-800/60">
                {SETTINGS_NAV.map((item) => (
                  <NavLink
                    key={item.path}
                    to={item.path}
                    onClick={onClose}
                    className={({ isActive }) =>
                      `flex items-center gap-3 pl-5 pr-4 py-2 text-sm transition-colors ${
                        isActive
                          ? 'text-[#7C3AED] bg-zinc-900/80'
                          : 'text-zinc-500 hover:text-zinc-100 hover:bg-zinc-900/50'
                      }`
                    }
                  >
                    <item.icon className="size-3.5 shrink-0" />
                    {t(item.labelKey)}
                  </NavLink>
                ))}
              </div>
            )}
          </div>
        </nav>
      </aside>
    </>
  )
}
