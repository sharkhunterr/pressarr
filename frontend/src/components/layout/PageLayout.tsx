import { useState } from 'react'
import { Menu } from 'lucide-react'
import { Sidebar } from './Sidebar'

interface PageLayoutProps {
  children: React.ReactNode
}

export function PageLayout({ children }: PageLayoutProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false)

  return (
    <div className="flex h-screen bg-zinc-900 text-zinc-100">
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      <div className="flex-1 flex flex-col min-w-0">
        {/* Mobile top bar */}
        <header className="flex items-center gap-3 px-4 py-3 border-b border-zinc-800 bg-zinc-950 lg:hidden">
          <button
            onClick={() => setSidebarOpen(true)}
            className="p-1.5 rounded-md text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800"
          >
            <Menu className="size-5" />
          </button>
          <img src="/logo.svg" alt="Pressarr" className="size-6 rounded" />
          <span className="text-lg font-bold text-[#7C3AED]">Pressarr</span>
        </header>

        <main className="flex-1 overflow-auto">{children}</main>
      </div>
    </div>
  )
}
