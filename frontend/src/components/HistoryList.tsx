import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import { ChevronLeft, ChevronRight, Loader2 } from 'lucide-react'

import type { HistoryEntry } from '@/api/history'
import { getHistory } from '@/api/history'
import { HistoryDetailModal } from '@/components/HistoryDetailModal'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'

function eventVariant(eventType: string): 'default' | 'secondary' | 'destructive' | 'outline' {
  switch (eventType) {
    case 'grab':
      return 'default'
    case 'download_completed':
    case 'import':
    case 'upgrade':
      return 'secondary'
    case 'error':
    case 'unmatched':
      return 'destructive'
    default:
      return 'outline'
  }
}

interface HistoryListProps {
  magazineId?: number
  issueId?: number
  packId?: number
  /** Quand true (défaut), montre le sélecteur de page. Sinon liste
   *  seule (utile dans un tab intégré au layout parent). */
  pagination?: boolean
  pageSize?: number
  /** Contrôle le fetch — par défaut toujours actif. Sur un modal,
   *  passe ``open`` pour éviter les fetches quand caché. */
  enabled?: boolean
}

/** History table sans wrapper Dialog — utilisable inline dans un
 *  onglet ou embedded dans un modal. */
export function HistoryList({
  magazineId,
  issueId,
  packId,
  pagination = true,
  pageSize = 15,
  enabled = true,
}: HistoryListProps) {
  const { t } = useTranslation()
  const [page, setPage] = useState(1)
  const [selectedEntry, setSelectedEntry] = useState<HistoryEntry | null>(null)

  // Reset la pagination quand la cible change
  useEffect(() => {
    setPage(1)
  }, [magazineId, issueId, packId])

  const { data, isLoading } = useQuery({
    queryKey: ['history-list', magazineId, issueId, packId, page, pageSize],
    queryFn: () => getHistory({ page, pageSize, magazineId, issueId, packId }),
    enabled,
  })

  const items = data?.records ?? []
  const totalPages = data ? Math.max(1, Math.ceil(data.totalRecords / pageSize)) : 1

  return (
    <div className="flex flex-col">
      <div className="flex-1 overflow-y-auto">
        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="size-6 animate-spin text-[#7C3AED]" />
          </div>
        ) : items.length === 0 ? (
          <p className="text-zinc-500 text-center py-8">{t('history.empty')}</p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow className="border-zinc-800 hover:bg-transparent">
                <TableHead className="text-zinc-400">{t('history.date')}</TableHead>
                <TableHead className="text-zinc-400">{t('history.eventType')}</TableHead>
                {!issueId && (
                  <TableHead className="text-zinc-400">{t('history.issue')}</TableHead>
                )}
                <TableHead className="text-zinc-400">{t('history.details')}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((entry) => (
                <TableRow
                  key={entry.id}
                  className="border-zinc-800 hover:bg-zinc-900/50 cursor-pointer"
                  onClick={() => setSelectedEntry(entry)}
                >
                  <TableCell className="text-zinc-400 text-sm whitespace-nowrap">
                    {new Date(entry.date).toLocaleString()}
                  </TableCell>
                  <TableCell>
                    <Badge variant={eventVariant(entry.eventType)}>
                      {t(`history.event_${entry.eventType}`, entry.eventType)}
                    </Badge>
                  </TableCell>
                  {!issueId && (
                    <TableCell className="text-zinc-400 text-sm">
                      {entry.issueNumber != null ? `#${entry.issueNumber}` : '-'}
                    </TableCell>
                  )}
                  <TableCell className="text-zinc-500 text-sm max-w-xs truncate" title={entry.details ?? undefined}>
                    {entry.details}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </div>

      {pagination && totalPages > 1 && (
        <div className="flex items-center justify-between pt-2 border-t border-zinc-800 shrink-0">
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
      )}

      <HistoryDetailModal
        open={selectedEntry !== null}
        onOpenChange={(o) => { if (!o) setSelectedEntry(null) }}
        entry={selectedEntry}
      />
    </div>
  )
}
