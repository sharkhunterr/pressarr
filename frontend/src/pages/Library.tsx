import { useState, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import { Plus, Search, LayoutGrid, List } from 'lucide-react'

import { getMagazines, getMagazineCoverUrl, type Magazine } from '@/api/magazines'
import { MagazineCard } from '@/components/MagazineCard'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

type SortOption = 'title' | 'added' | 'nextIssue' | 'missing' | 'completion'
type FilterOption = 'all' | 'monitored' | 'unmonitored' | 'complete' | 'incomplete'
type ViewMode = 'grid' | 'list'

function getStoredView(): ViewMode {
  try {
    const v = localStorage.getItem('pressarr-library-view')
    if (v === 'grid' || v === 'list') return v
  } catch { /* ignore */ }
  return 'grid'
}

export default function Library() {
  const { t } = useTranslation()
  const navigate = useNavigate()

  const [sort, setSort] = useState<SortOption>('title')
  const [filter, setFilter] = useState<FilterOption>('all')
  const [search, setSearch] = useState('')
  const [view, setView] = useState<ViewMode>(getStoredView)

  const handleViewChange = (v: ViewMode) => {
    setView(v)
    try { localStorage.setItem('pressarr-library-view', v) } catch { /* ignore */ }
  }

  const { data: magazines = [], isLoading } = useQuery({
    queryKey: ['magazines'],
    queryFn: getMagazines,
  })

  const filtered = useMemo(() => {
    let result: Magazine[] = [...magazines]

    // Text search
    if (search.trim()) {
      const q = search.toLowerCase()
      result = result.filter((m) => m.title.toLowerCase().includes(q))
    }

    // Filter
    switch (filter) {
      case 'monitored':
        result = result.filter((m) => m.monitored)
        break
      case 'unmonitored':
        result = result.filter((m) => !m.monitored)
        break
      case 'complete':
        result = result.filter(
          (m) => m.statistics.issueCount > 0 && m.statistics.availableCount === m.statistics.issueCount,
        )
        break
      case 'incomplete':
        result = result.filter(
          (m) => m.statistics.issueCount === 0 || m.statistics.availableCount < m.statistics.issueCount,
        )
        break
    }

    // Sort
    switch (sort) {
      case 'title':
        result.sort((a, b) => a.title.localeCompare(b.title))
        break
      case 'added':
        result.sort((a, b) => new Date(b.addedAt).getTime() - new Date(a.addedAt).getTime())
        break
      case 'nextIssue':
        result.sort((a, b) => {
          const aDate = a.statistics?.nextIssueDate ? new Date(a.statistics.nextIssueDate).getTime() : 0
          const bDate = b.statistics?.nextIssueDate ? new Date(b.statistics.nextIssueDate).getTime() : 0
          return bDate - aDate
        })
        break
      case 'missing':
        result.sort((a, b) => {
          const aMissing = (a.statistics?.issueCount ?? 0) - (a.statistics?.availableCount ?? 0)
          const bMissing = (b.statistics?.issueCount ?? 0) - (b.statistics?.availableCount ?? 0)
          return bMissing - aMissing
        })
        break
      case 'completion':
        result.sort((a, b) => {
          const aPct = a.statistics?.issueCount ? (a.statistics.availableCount / a.statistics.issueCount) : 0
          const bPct = b.statistics?.issueCount ? (b.statistics.availableCount / b.statistics.issueCount) : 0
          return aPct - bPct
        })
        break
    }

    return result
  }, [magazines, sort, filter, search])

  if (isLoading) {
    return (
      <div className="p-4 lg:p-8">
        <Skeleton className="h-8 w-48 bg-zinc-800 mb-6" />
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
          {[1, 2, 3, 4, 5, 6, 7, 8].map((i) => (
            <div key={i} className="space-y-2">
              <Skeleton className="aspect-[3/4] bg-zinc-800 rounded-lg" />
              <Skeleton className="h-4 w-3/4 bg-zinc-800" />
              <Skeleton className="h-3 w-1/2 bg-zinc-800" />
            </div>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="p-4 lg:p-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-bold text-zinc-100">{t('library.title')}</h1>
        <Button onClick={() => navigate('/add')}>
          <Plus className="size-4" />
          {t('library.addMagazine')}
        </Button>
      </div>

      {/* Controls */}
      <div className="flex flex-col sm:flex-row gap-3 mb-6">
        {/* Search */}
        <div className="relative flex-1 sm:max-w-xs">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-zinc-500" />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={t('library.searchPlaceholder')}
            className="pl-9 bg-zinc-900 border-zinc-700 text-zinc-100"
          />
        </div>

        <div className="flex items-center gap-2">
          <Select value={sort} onValueChange={(v) => setSort(v as SortOption)}>
            <SelectTrigger className="w-full sm:w-44 bg-zinc-900 border-zinc-700 text-zinc-100">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="title">{t('library.sortTitle')}</SelectItem>
              <SelectItem value="added">{t('library.sortAdded')}</SelectItem>
              <SelectItem value="nextIssue">{t('library.sortNextIssue')}</SelectItem>
              <SelectItem value="missing">{t('library.sortMissing')}</SelectItem>
              <SelectItem value="completion">{t('library.sortCompletion')}</SelectItem>
            </SelectContent>
          </Select>

          <Select value={filter} onValueChange={(v) => setFilter(v as FilterOption)}>
            <SelectTrigger className="w-full sm:w-40 bg-zinc-900 border-zinc-700 text-zinc-100">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{t('library.filterAll')}</SelectItem>
              <SelectItem value="monitored">{t('library.filterMonitored')}</SelectItem>
              <SelectItem value="unmonitored">{t('library.filterUnmonitored')}</SelectItem>
              <SelectItem value="complete">{t('library.filterComplete')}</SelectItem>
              <SelectItem value="incomplete">{t('library.filterIncomplete')}</SelectItem>
            </SelectContent>
          </Select>

          {/* View toggle */}
          <div className="flex border border-zinc-700 rounded-md overflow-hidden shrink-0">
            <button
              type="button"
              onClick={() => handleViewChange('grid')}
              className={`p-2 transition-colors ${view === 'grid' ? 'bg-zinc-700 text-zinc-100' : 'bg-zinc-900 text-zinc-500 hover:text-zinc-300'}`}
              title={t('library.viewGrid')}
            >
              <LayoutGrid className="size-4" />
            </button>
            <button
              type="button"
              onClick={() => handleViewChange('list')}
              className={`p-2 transition-colors ${view === 'list' ? 'bg-zinc-700 text-zinc-100' : 'bg-zinc-900 text-zinc-500 hover:text-zinc-300'}`}
              title={t('library.viewList')}
            >
              <List className="size-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Content */}
      {filtered.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16">
          <p className="text-zinc-500 mb-4">{search ? t('search.noResults') : t('library.empty')}</p>
          {!search && (
            <Button onClick={() => navigate('/add')}>
              <Plus className="size-4" />
              {t('library.addMagazine')}
            </Button>
          )}
        </div>
      ) : view === 'grid' ? (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
          {filtered.map((magazine) => (
            <MagazineCard key={magazine.id} magazine={magazine} />
          ))}
        </div>
      ) : (
        <LibraryTable magazines={filtered} />
      )}
    </div>
  )
}

function LibraryTable({ magazines }: { magazines: Magazine[] }) {
  const { t } = useTranslation()
  const navigate = useNavigate()

  return (
    <Table>
      <TableHeader>
        <TableRow className="border-zinc-800 hover:bg-transparent">
          <TableHead className="text-zinc-400 w-12" />
          <TableHead className="text-zinc-400">{t('library.title')}</TableHead>
          <TableHead className="text-zinc-400">{t('issues.status')}</TableHead>
          <TableHead className="text-zinc-400">{t('issues.title')}</TableHead>
          <TableHead className="text-zinc-400 w-32">{t('magazineDetail.completion')}</TableHead>
          <TableHead className="text-zinc-400 hidden md:table-cell">{t('addMagazine.frequency')}</TableHead>
          <TableHead className="text-zinc-400 hidden md:table-cell">{t('library.sortNextIssue')}</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {magazines.map((m) => {
          const stats = m.statistics
          const pct = stats?.issueCount ? Math.round((stats.availableCount / stats.issueCount) * 100) : 0
          const nextDate = stats?.nextIssueDate

          return (
            <TableRow
              key={m.id}
              className="border-zinc-800 hover:bg-zinc-900/50 cursor-pointer"
              onClick={() => navigate(`/magazine/${m.id}`)}
            >
              {/* Cover */}
              <TableCell className="p-2">
                <div className="w-10 h-[53px] rounded bg-zinc-900 overflow-hidden">
                  {m.coverPath ? (
                    <img
                      src={getMagazineCoverUrl(m.id, m.coverPath ?? undefined)}
                      alt=""
                      className="w-full h-full object-cover"
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center text-zinc-700 text-[8px]">?</div>
                  )}
                </div>
              </TableCell>

              {/* Title */}
              <TableCell className="text-zinc-100 text-sm font-medium">{m.title}</TableCell>

              {/* Status */}
              <TableCell>
                <Badge variant={m.monitored ? 'default' : 'outline'} className={m.monitored ? 'bg-[#7C3AED]' : ''}>
                  {m.monitored ? t('library.monitored') : t('library.unmonitored')}
                </Badge>
              </TableCell>

              {/* Issues */}
              <TableCell className="text-zinc-400 text-sm">
                {t('library.issueStats', {
                  available: stats?.availableCount ?? 0,
                  total: stats?.issueCount ?? 0,
                })}
              </TableCell>

              {/* Completion */}
              <TableCell>
                <div className="flex items-center gap-2">
                  <div className="flex-1 h-1.5 rounded-full bg-zinc-800 overflow-hidden">
                    <div className="h-full rounded-full bg-[#7C3AED]" style={{ width: `${pct}%` }} />
                  </div>
                  <span className="text-xs text-zinc-500 w-8 text-right">{pct}%</span>
                </div>
              </TableCell>

              {/* Frequency */}
              <TableCell className="text-zinc-500 text-sm hidden md:table-cell capitalize">
                {m.frequency && m.frequency !== 'irregular' ? t(`addMagazine.${m.frequency}`) : '-'}
              </TableCell>

              {/* Next issue */}
              <TableCell className="text-zinc-500 text-sm hidden md:table-cell">
                {nextDate ? new Date(nextDate + 'T00:00:00').toLocaleDateString() : '-'}
              </TableCell>
            </TableRow>
          )
        })}
      </TableBody>
    </Table>
  )
}
