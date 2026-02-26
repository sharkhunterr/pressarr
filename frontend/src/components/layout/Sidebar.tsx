import { NavLink } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

const NAV_ITEMS = [
  { path: '/', labelKey: 'nav.library' },
  { path: '/add', labelKey: 'nav.addMagazine' },
  { path: '/calendar', labelKey: 'nav.calendar' },
  { path: '/queue', labelKey: 'nav.queue' },
  { path: '/history', labelKey: 'nav.history' },
  { path: '/blocklist', labelKey: 'nav.blocklist' },
  { path: '/settings/general', labelKey: 'nav.settings' },
]

export function Sidebar() {
  const { t } = useTranslation()
  return (
    <aside className="w-56 bg-zinc-950 border-r border-zinc-800 h-screen flex flex-col">
      <div className="p-4 border-b border-zinc-800">
        <h1 className="text-xl font-bold text-[#E85D04]">Pressarr</h1>
      </div>
      <nav className="flex-1 py-2">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            end={item.path === '/'}
            className={({ isActive }) =>
              `block px-4 py-2 text-sm ${
                isActive
                  ? 'text-[#E85D04] bg-zinc-900'
                  : 'text-zinc-400 hover:text-zinc-100 hover:bg-zinc-900'
              }`
            }
          >
            {t(item.labelKey)}
          </NavLink>
        ))}
      </nav>
    </aside>
  )
}
