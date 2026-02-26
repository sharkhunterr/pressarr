import { useState, useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ChevronLeft, ChevronRight, LayoutGrid, List } from 'lucide-react'
import { toast } from 'sonner'

import { getCalendar, skipForecast, type CalendarEntry } from '@/api/calendar'
import { getMagazines, type Magazine } from '@/api/magazines'
import { CalendarGrid } from '@/components/CalendarGrid'
import { CalendarAgenda } from '@/components/CalendarAgenda'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

type ViewMode = 'grid' | 'agenda'

export default function Calendar() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()

  const now = new Date()
  const [year, setYear] = useState(now.getFullYear())
  const [month, setMonth] = useState(now.getMonth())
  const [view, setView] = useState<ViewMode>('grid')
  const [magazineFilter, setMagazineFilter] = useState<string>('all')
  const [statusFilter, setStatusFilter] = useState<string>('all')

  const start = new Date(year, month, 1).toISOString().slice(0, 10)
  const end = new Date(year, month + 1, 0).toISOString().slice(0, 10)

  const { data: entries = [], isLoading } = useQuery({
    queryKey: ['calendar', start, end],
    queryFn: () => getCalendar(start, end, undefined, true),
  })

  const { data: magazines = [] } = useQuery({
    queryKey: ['magazines'],
    queryFn: getMagazines,
  })

  const skipMutation = useMutation({
    mutationFn: (issueId: number) => skipForecast(issueId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['calendar'] })
      toast.success(t('calendar.skipped'))
    },
    onError: () => toast.error(t('calendar.skipError')),
  })

  const filteredEntries = useMemo(() => {
    let result: CalendarEntry[] = [...entries]
    if (magazineFilter !== 'all') {
      result = result.filter((e) => String(e.magazineId) === magazineFilter)
    }
    if (statusFilter !== 'all') {
      result = result.filter((e) => e.status === statusFilter)
    }
    return result.sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
  }, [entries, magazineFilter, statusFilter])

  function prevMonth() {
    if (month === 0) {
      setMonth(11)
      setYear(year - 1)
    } else {
      setMonth(month - 1)
    }
  }

  function nextMonth() {
    if (month === 11) {
      setMonth(0)
      setYear(year + 1)
    } else {
      setMonth(month + 1)
    }
  }

  const monthLabel = new Date(year, month, 1).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'long',
  })

  if (isLoading) {
    return (
      <div className="p-8">
        <Skeleton className="h-8 w-48 bg-zinc-800 mb-6" />
        <Skeleton className="h-96 bg-zinc-800 rounded-lg" />
      </div>
    )
  }

  return (
    <div className="p-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-zinc-100">{t('calendar.title')}</h1>

        <div className="flex items-center gap-2">
          {/* View toggle */}
          <Button
            variant={view === 'grid' ? 'default' : 'outline'}
            size="icon-sm"
            onClick={() => setView('grid')}
            className={view === 'grid' ? 'bg-[#E85D04] hover:bg-[#E85D04]/90' : ''}
          >
            <LayoutGrid className="size-4" />
          </Button>
          <Button
            variant={view === 'agenda' ? 'default' : 'outline'}
            size="icon-sm"
            onClick={() => setView('agenda')}
            className={view === 'agenda' ? 'bg-[#E85D04] hover:bg-[#E85D04]/90' : ''}
          >
            <List className="size-4" />
          </Button>
        </div>
      </div>

      {/* Month navigation */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Button variant="outline" size="icon-sm" onClick={prevMonth}>
            <ChevronLeft className="size-4" />
          </Button>
          <span className="text-lg font-medium text-zinc-100 min-w-48 text-center">
            {monthLabel}
          </span>
          <Button variant="outline" size="icon-sm" onClick={nextMonth}>
            <ChevronRight className="size-4" />
          </Button>
        </div>

        {/* Filters */}
        <div className="flex items-center gap-2">
          <Select value={magazineFilter} onValueChange={setMagazineFilter}>
            <SelectTrigger className="w-44 bg-zinc-900 border-zinc-700 text-zinc-100">
              <SelectValue placeholder={t('calendar.allMagazines')} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{t('calendar.allMagazines')}</SelectItem>
              {magazines.map((m: Magazine) => (
                <SelectItem key={m.id} value={String(m.id)}>
                  {m.title}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select value={statusFilter} onValueChange={setStatusFilter}>
            <SelectTrigger className="w-36 bg-zinc-900 border-zinc-700 text-zinc-100">
              <SelectValue placeholder={t('calendar.allStatuses')} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{t('calendar.allStatuses')}</SelectItem>
              <SelectItem value="available">{t('status.available')}</SelectItem>
              <SelectItem value="wanted">{t('status.wanted')}</SelectItem>
              <SelectItem value="missing">{t('status.missing')}</SelectItem>
              <SelectItem value="upcoming">{t('status.upcoming')}</SelectItem>
              <SelectItem value="skipped">{t('status.skipped')}</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Content */}
      {view === 'grid' ? (
        <CalendarGrid year={year} month={month} entries={filteredEntries} />
      ) : (
        <CalendarAgenda
          entries={filteredEntries}
          onSkip={(issueId) => skipMutation.mutate(issueId)}
        />
      )}
    </div>
  )
}
