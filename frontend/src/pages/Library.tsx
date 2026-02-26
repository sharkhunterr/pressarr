import { useState, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import { Plus } from 'lucide-react'

import { getMagazines, type Magazine } from '@/api/magazines'
import { MagazineCard } from '@/components/MagazineCard'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

type SortOption = 'title' | 'added' | 'nextIssue'
type FilterOption = 'all' | 'monitored' | 'unmonitored' | 'complete' | 'incomplete'

export default function Library() {
  const { t } = useTranslation()
  const navigate = useNavigate()

  const [sort, setSort] = useState<SortOption>('title')
  const [filter, setFilter] = useState<FilterOption>('all')

  const { data: magazines = [], isLoading } = useQuery({
    queryKey: ['magazines'],
    queryFn: getMagazines,
  })

  const filtered = useMemo(() => {
    let result: Magazine[] = [...magazines]

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
          (m) => m.issueCount > 0 && m.availableCount === m.issueCount,
        )
        break
      case 'incomplete':
        result = result.filter(
          (m) => m.issueCount === 0 || m.availableCount < m.issueCount,
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
          const aDate = a.lastRefreshed ? new Date(a.lastRefreshed).getTime() : 0
          const bDate = b.lastRefreshed ? new Date(b.lastRefreshed).getTime() : 0
          return bDate - aDate
        })
        break
    }

    return result
  }, [magazines, sort, filter])

  if (isLoading) {
    return (
      <div className="p-8">
        <Skeleton className="h-8 w-48 bg-zinc-800 mb-6" />
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-2 lg:grid-cols-4 gap-4">
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
    <div className="p-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-zinc-100">{t('library.title')}</h1>
        <Button onClick={() => navigate('/add')}>
          <Plus className="size-4" />
          {t('library.addMagazine')}
        </Button>
      </div>

      {/* Controls */}
      <div className="flex items-center gap-3 mb-6">
        <Select value={sort} onValueChange={(v) => setSort(v as SortOption)}>
          <SelectTrigger className="w-40 bg-zinc-900 border-zinc-700 text-zinc-100">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="title">{t('library.sortTitle')}</SelectItem>
            <SelectItem value="added">{t('library.sortAdded')}</SelectItem>
            <SelectItem value="nextIssue">{t('library.sortNextIssue')}</SelectItem>
          </SelectContent>
        </Select>

        <Select value={filter} onValueChange={(v) => setFilter(v as FilterOption)}>
          <SelectTrigger className="w-40 bg-zinc-900 border-zinc-700 text-zinc-100">
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
      </div>

      {/* Grid */}
      {filtered.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16">
          <p className="text-zinc-500 mb-4">{t('library.empty')}</p>
          <Button onClick={() => navigate('/add')}>
            <Plus className="size-4" />
            {t('library.addMagazine')}
          </Button>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {filtered.map((magazine) => (
            <MagazineCard key={magazine.id} magazine={magazine} />
          ))}
        </div>
      )}
    </div>
  )
}
