import { useState, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import { Plus, Search, LayoutGrid, List } from 'lucide-react'

import { getPacks, type Pack } from '@/api/packs'
import { PackCard } from '@/components/PackCard'
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

type SortOption = 'name' | 'added' | 'grabs'
type FilterOption = 'all' | 'monitored' | 'unmonitored'
type ViewMode = 'grid' | 'list'

function getStoredView(): ViewMode {
  try {
    const v = localStorage.getItem('pressarr-packs-view')
    if (v === 'grid' || v === 'list') return v
  } catch { /* ignore */ }
  return 'grid'
}

export default function Packs() {
  const { t } = useTranslation()
  const navigate = useNavigate()

  const [sort, setSort] = useState<SortOption>('name')
  const [filter, setFilter] = useState<FilterOption>('all')
  const [search, setSearch] = useState('')
  const [view, setView] = useState<ViewMode>(getStoredView)

  const handleViewChange = (v: ViewMode) => {
    setView(v)
    try { localStorage.setItem('pressarr-packs-view', v) } catch { /* ignore */ }
  }

  const { data: packs = [], isLoading } = useQuery({
    queryKey: ['packs'],
    queryFn: getPacks,
  })

  const filtered = useMemo(() => {
    let result: Pack[] = [...packs]

    if (search.trim()) {
      const q = search.toLowerCase()
      result = result.filter((p) => p.name.toLowerCase().includes(q))
    }

    switch (filter) {
      case 'monitored':
        result = result.filter((p) => p.monitored)
        break
      case 'unmonitored':
        result = result.filter((p) => !p.monitored)
        break
    }

    switch (sort) {
      case 'name':
        result.sort((a, b) => a.name.localeCompare(b.name))
        break
      case 'added':
        result.sort((a, b) => new Date(b.addedAt).getTime() - new Date(a.addedAt).getTime())
        break
      case 'grabs':
        result.sort((a, b) => (b.statistics?.totalGrabs ?? 0) - (a.statistics?.totalGrabs ?? 0))
        break
    }

    return result
  }, [packs, sort, filter, search])

  if (isLoading) {
    return (
      <div className="p-4 lg:p-8">
        <Skeleton className="h-8 w-48 bg-zinc-800 mb-6" />
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="space-y-2">
              <Skeleton className="aspect-[4/3] bg-zinc-800 rounded-lg" />
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
        <h1 className="text-2xl font-bold text-zinc-100">{t('packs.title')}</h1>
        <Button onClick={() => navigate('/packs/add')}>
          <Plus className="size-4" />
          {t('packs.addPack')}
        </Button>
      </div>

      {/* Controls */}
      <div className="flex flex-col sm:flex-row gap-3 mb-6">
        <div className="relative flex-1 sm:max-w-xs">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-zinc-500" />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={t('packs.searchPlaceholder')}
            className="pl-9 bg-zinc-900 border-zinc-700 text-zinc-100"
          />
        </div>

        <div className="flex items-center gap-2">
          <Select value={sort} onValueChange={(v) => setSort(v as SortOption)}>
            <SelectTrigger className="w-full sm:w-44 bg-zinc-900 border-zinc-700 text-zinc-100">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="name">{t('packs.sortName')}</SelectItem>
              <SelectItem value="added">{t('packs.sortAdded')}</SelectItem>
              <SelectItem value="grabs">{t('packs.sortGrabs')}</SelectItem>
            </SelectContent>
          </Select>

          <Select value={filter} onValueChange={(v) => setFilter(v as FilterOption)}>
            <SelectTrigger className="w-full sm:w-40 bg-zinc-900 border-zinc-700 text-zinc-100">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{t('packs.filterAll')}</SelectItem>
              <SelectItem value="monitored">{t('packs.filterMonitored')}</SelectItem>
              <SelectItem value="unmonitored">{t('packs.filterUnmonitored')}</SelectItem>
            </SelectContent>
          </Select>

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
          <p className="text-zinc-500 mb-4">{search ? t('common.noResults') : t('packs.empty')}</p>
          {!search && (
            <Button onClick={() => navigate('/packs/add')}>
              <Plus className="size-4" />
              {t('packs.addPack')}
            </Button>
          )}
        </div>
      ) : view === 'grid' ? (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
          {filtered.map((pack) => (
            <PackCard key={pack.id} pack={pack} />
          ))}
        </div>
      ) : (
        <PacksTable packs={filtered} />
      )}
    </div>
  )
}

function PacksTable({ packs }: { packs: Pack[] }) {
  const { t } = useTranslation()
  const navigate = useNavigate()

  return (
    <Table>
      <TableHeader>
        <TableRow className="border-zinc-800 hover:bg-transparent">
          <TableHead className="text-zinc-400">{t('packs.name')}</TableHead>
          <TableHead className="text-zinc-400">{t('packs.searchQuery')}</TableHead>
          <TableHead className="text-zinc-400">{t('issues.status')}</TableHead>
          <TableHead className="text-zinc-400">{t('packs.tabPatterns')}</TableHead>
          <TableHead className="text-zinc-400">{t('packs.recurrence')}</TableHead>
          <TableHead className="text-zinc-400 hidden md:table-cell">{t('packs.grabs', { count: 0 }).replace('0 ', '')}</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {packs.map((p) => (
          <TableRow
            key={p.id}
            className="border-zinc-800 hover:bg-zinc-900/50 cursor-pointer"
            onClick={() => navigate(`/pack/${p.id}`)}
          >
            <TableCell className="text-zinc-100 text-sm font-medium">{p.name}</TableCell>
            <TableCell className="text-zinc-400 text-sm truncate max-w-[200px]">{p.searchQuery}</TableCell>
            <TableCell>
              <Badge variant={p.monitored ? 'default' : 'outline'} className={p.monitored ? 'bg-[#7C3AED]' : ''}>
                {p.monitored ? t('packs.monitored') : t('packs.unmonitored')}
              </Badge>
            </TableCell>
            <TableCell className="text-zinc-400 text-sm">{p.statistics?.patternCount ?? 0}</TableCell>
            <TableCell className="text-zinc-500 text-sm capitalize">
              {p.recurrence !== 'none' ? t(`packs.${p.recurrence}`) : '-'}
            </TableCell>
            <TableCell className="text-zinc-500 text-sm hidden md:table-cell">{p.statistics?.totalGrabs ?? 0}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
