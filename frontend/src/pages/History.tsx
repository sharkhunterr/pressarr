import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import { ChevronLeft, ChevronRight } from 'lucide-react'

import { getHistory } from '@/api/history'
import { getMagazines } from '@/api/magazines'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
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

const EVENT_TYPES = ['grab', 'download_completed', 'import', 'upgrade', 'searched', 'unmatched', 'error']

function eventVariant(eventType: string): 'default' | 'secondary' | 'destructive' | 'outline' {
  switch (eventType) {
    case 'grab':
      return 'default'
    case 'download_completed':
    case 'import':
    case 'upgrade':
      return 'secondary'
    case 'searched':
      return 'outline'
    case 'error':
    case 'unmatched':
      return 'destructive'
    default:
      return 'outline'
  }
}

export default function History() {
  const { t } = useTranslation()

  const [page, setPage] = useState(1)
  const [pageSize] = useState(25)
  const [eventType, setEventType] = useState<string>('all')
  const [magazineFilter, setMagazineFilter] = useState<string>('all')

  const { data: magazines = [] } = useQuery({
    queryKey: ['magazines'],
    queryFn: getMagazines,
  })

  const { data, isLoading } = useQuery({
    queryKey: ['history', page, pageSize, eventType, magazineFilter],
    queryFn: () =>
      getHistory({
        page,
        pageSize,
        eventType: eventType !== 'all' ? eventType : undefined,
        magazineId: magazineFilter !== 'all' ? Number(magazineFilter) : undefined,
      }),
  })

  const items = data?.records ?? []
  const totalPages = data ? Math.max(1, Math.ceil(data.totalRecords / pageSize)) : 1

  if (isLoading) {
    return (
      <div className="p-4 lg:p-8">
        <Skeleton className="h-8 w-48 bg-zinc-800 mb-6" />
        <div className="space-y-2">
          {[1, 2, 3, 4, 5].map((i) => (
            <Skeleton key={i} className="h-12 bg-zinc-800" />
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="p-4 lg:p-8">
      <h1 className="text-2xl font-bold text-zinc-100 mb-6">{t('history.title')}</h1>

      {/* Filters */}
      <div className="flex items-center gap-3 mb-6">
        <Select value={eventType} onValueChange={(v) => { setEventType(v); setPage(1) }}>
          <SelectTrigger className="w-40 bg-zinc-900 border-zinc-700 text-zinc-100">
            <SelectValue placeholder={t('history.allEvents')} />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{t('history.allEvents')}</SelectItem>
            {EVENT_TYPES.map((type) => (
              <SelectItem key={type} value={type}>
                {t(`history.event_${type}`, type)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select value={magazineFilter} onValueChange={(v) => { setMagazineFilter(v); setPage(1) }}>
          <SelectTrigger className="w-44 bg-zinc-900 border-zinc-700 text-zinc-100">
            <SelectValue placeholder={t('history.allMagazines')} />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{t('history.allMagazines')}</SelectItem>
            {magazines.map((m) => (
              <SelectItem key={m.id} value={String(m.id)}>
                {m.title}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Table */}
      {items.length === 0 ? (
        <p className="text-zinc-500 text-center py-8">{t('history.empty')}</p>
      ) : (
        <>
          <Table>
            <TableHeader>
              <TableRow className="border-zinc-800 hover:bg-transparent">
                <TableHead className="text-zinc-400">{t('history.date')}</TableHead>
                <TableHead className="text-zinc-400">{t('history.eventType')}</TableHead>
                <TableHead className="text-zinc-400">{t('history.magazine')}</TableHead>
                <TableHead className="text-zinc-400">{t('history.issue')}</TableHead>
                <TableHead className="text-zinc-400">{t('history.issueDate')}</TableHead>
                <TableHead className="text-zinc-400">{t('history.details')}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((entry) => (
                <TableRow key={entry.id} className="border-zinc-800 hover:bg-zinc-900/50">
                  <TableCell className="text-zinc-400 text-sm">
                    {new Date(entry.date).toLocaleString()}
                  </TableCell>
                  <TableCell>
                    <Badge variant={eventVariant(entry.eventType)}>
                      {t(`history.event_${entry.eventType}`, entry.eventType)}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-zinc-100 text-sm">
                    {entry.magazineTitle}
                  </TableCell>
                  <TableCell className="text-zinc-400 text-sm">
                    {entry.issueNumber !== null ? `#${entry.issueNumber}` : '-'}
                  </TableCell>
                  <TableCell className="text-zinc-400 text-sm">
                    {entry.issueDate ? new Date(entry.issueDate + 'T00:00:00').toLocaleDateString() : '-'}
                  </TableCell>
                  <TableCell className="text-zinc-500 text-sm max-w-xs truncate">
                    {entry.details}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>

          {/* Pagination */}
          <div className="flex items-center justify-between mt-4">
            <span className="text-sm text-zinc-500">
              {t('history.page', { page, totalPages })}
            </span>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="icon-sm"
                disabled={page <= 1}
                onClick={() => setPage(page - 1)}
              >
                <ChevronLeft className="size-4" />
              </Button>
              <Button
                variant="outline"
                size="icon-sm"
                disabled={page >= totalPages}
                onClick={() => setPage(page + 1)}
              >
                <ChevronRight className="size-4" />
              </Button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
