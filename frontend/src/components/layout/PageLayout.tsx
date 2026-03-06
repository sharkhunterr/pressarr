import { useState, useEffect, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Menu, Search, X } from 'lucide-react'
import { Sidebar } from './Sidebar'
import { type Magazine, getMagazineCoverUrl } from '@/api/magazines'

interface PageLayoutProps {
  children: React.ReactNode
}

export function PageLayout({ children }: PageLayoutProps) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [searchActive, setSearchActive] = useState(false)
  const [query, setQuery] = useState('')
  const [selectedIndex, setSelectedIndex] = useState(0)
  const mobileInputRef = useRef<HTMLInputElement>(null)
  const desktopInputRef = useRef<HTMLInputElement>(null)

  const openSearch = useCallback(() => {
    setSearchActive(true)
    setQuery('')
    setSelectedIndex(0)
  }, [])

  const closeSearch = useCallback(() => {
    setSearchActive(false)
    setQuery('')
  }, [])

  // Ctrl+K / Cmd+K
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault()
        if (searchActive) {
          mobileInputRef.current?.focus()
          desktopInputRef.current?.focus()
        } else {
          openSearch()
        }
      }
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [searchActive, openSearch])

  // Auto-focus input when search opens
  useEffect(() => {
    if (searchActive) {
      setTimeout(() => {
        mobileInputRef.current?.focus()
        desktopInputRef.current?.focus()
      }, 50)
    }
  }, [searchActive])

  // Reset selection on query change
  useEffect(() => {
    setSelectedIndex(0)
  }, [query])

  const magazines: Magazine[] = queryClient.getQueryData(['magazines']) ?? []
  const results = query.trim()
    ? magazines
        .filter((m) => m.title.toLowerCase().includes(query.toLowerCase()))
        .slice(0, 10)
    : []

  const handleSelect = (magazine: Magazine) => {
    closeSearch()
    navigate(`/magazine/${magazine.id}`)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setSelectedIndex((i) => Math.min(i + 1, results.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setSelectedIndex((i) => Math.max(i - 1, 0))
    } else if (e.key === 'Enter' && results[selectedIndex]) {
      e.preventDefault()
      handleSelect(results[selectedIndex])
    } else if (e.key === 'Escape') {
      closeSearch()
    }
  }

  const searchResults = query.trim() && (
    <div className="absolute left-0 right-0 top-full z-50 bg-zinc-950 border-b border-zinc-800 max-h-80 overflow-y-auto shadow-lg">
      {results.length === 0 ? (
        <p className="text-sm text-zinc-500 text-center py-6">
          {t('search.noResults')}
        </p>
      ) : (
        results.map((magazine, index) => (
          <button
            key={magazine.id}
            type="button"
            onClick={() => handleSelect(magazine)}
            className={`w-full flex items-center gap-3 px-4 py-2.5 text-left transition-colors ${
              index === selectedIndex ? 'bg-zinc-800' : 'hover:bg-zinc-900/60'
            }`}
          >
            <div className="size-10 rounded bg-zinc-900 overflow-hidden shrink-0">
              {magazine.coverPath ? (
                <img
                  src={getMagazineCoverUrl(magazine.id, magazine.coverPath ?? undefined)}
                  alt=""
                  className="size-full object-cover"
                />
              ) : (
                <div className="size-full flex items-center justify-center text-zinc-700 text-[8px]">
                  ?
                </div>
              )}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm text-zinc-100 truncate">{magazine.title}</p>
              <p className="text-xs text-zinc-500">
                {t('library.issueStats', {
                  available: magazine.statistics?.availableCount ?? 0,
                  total: magazine.statistics?.issueCount ?? 0,
                })}
              </p>
            </div>
          </button>
        ))
      )}
    </div>
  )

  return (
    <div className="flex h-screen bg-zinc-900 text-zinc-100">
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      <div className="flex-1 flex flex-col min-w-0">
        {/* Mobile top bar */}
        <header className="relative z-50 flex items-center gap-3 px-4 py-3 border-b border-zinc-800 bg-zinc-950 lg:hidden">
          {searchActive ? (
            <>
              <button
                onClick={closeSearch}
                className="p-1.5 rounded-md text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800 shrink-0"
              >
                <ArrowLeft className="size-5" />
              </button>
              <input
                ref={mobileInputRef}
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={t('search.placeholder')}
                className="flex-1 bg-transparent text-zinc-100 placeholder:text-zinc-500 text-sm outline-none"
              />
            </>
          ) : (
            <>
              <button
                onClick={() => setSidebarOpen(true)}
                className="p-1.5 rounded-md text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800"
              >
                <Menu className="size-5" />
              </button>
              <img src="/logo.svg" alt="Pressarr" className="size-6 rounded" />
              <span className="text-lg font-bold text-[#7C3AED]">Pressarr</span>

              <button
                onClick={openSearch}
                className="ml-auto p-1.5 rounded-md text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800"
              >
                <Search className="size-5" />
              </button>
            </>
          )}

          {/* Mobile results */}
          {searchActive && searchResults}
        </header>

        {/* Desktop top bar */}
        <div className="hidden lg:flex relative z-50 items-center justify-end px-6 py-2">
          {searchActive ? (
            <div className="flex items-center gap-2 w-full max-w-md ml-auto px-3 py-1.5 rounded-md border border-zinc-700 bg-zinc-950">
              <Search className="size-3.5 text-zinc-500 shrink-0" />
              <input
                ref={desktopInputRef}
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={t('search.placeholder')}
                className="flex-1 bg-transparent text-zinc-100 placeholder:text-zinc-500 text-sm outline-none"
              />
              <button
                onClick={closeSearch}
                className="p-0.5 rounded text-zinc-500 hover:text-zinc-300"
              >
                <X className="size-3.5" />
              </button>
            </div>
          ) : (
            <button
              onClick={openSearch}
              className="flex items-center gap-2 px-3 py-1.5 rounded-md border border-zinc-800 bg-zinc-950 text-zinc-500 hover:text-zinc-300 hover:border-zinc-700 transition-colors text-sm"
            >
              <Search className="size-3.5" />
              <span>Search...</span>
              <kbd className="ml-2 text-[10px] font-mono bg-zinc-800 text-zinc-400 px-1.5 py-0.5 rounded">Ctrl+K</kbd>
            </button>
          )}

          {/* Desktop results */}
          {searchActive && searchResults}
        </div>

        <main className="flex-1 overflow-auto">{children}</main>
      </div>

      {/* Backdrop to close search */}
      {searchActive && (
        <div className="fixed inset-0 z-40" onClick={closeSearch} />
      )}
    </div>
  )
}
