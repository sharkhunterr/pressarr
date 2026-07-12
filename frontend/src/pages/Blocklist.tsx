import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ChevronLeft, ChevronRight, Trash2, Unlock } from 'lucide-react'
import { toast } from 'sonner'

import { apiFetch } from '@/api/client'
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

interface BlocklistEntry {
  id: number
  releaseTitle: string
  magazineTitle: string
  indexer: string
  date: string
  reason: string
}

interface BlocklistPage {
  items: BlocklistEntry[]
  page: number
  pageSize: number
  totalItems: number
  totalPages: number
}

const getBlocklist = (page: number, pageSize: number) =>
  apiFetch<BlocklistPage>(`/blocklist?page=${page}&pageSize=${pageSize}`)

const unblockEntry = (id: number) =>
  apiFetch<void>(`/blocklist/${id}`, { method: 'DELETE' })

const bulkUnblock = (ids: number[]) =>
  apiFetch<void>('/blocklist/bulk', {
    method: 'DELETE',
    body: JSON.stringify({ ids }),
  })

export default function Blocklist() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()

  const [page, setPage] = useState(1)
  const [pageSize] = useState(25)
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set())

  const { data, isLoading } = useQuery({
    queryKey: ['blocklist', page, pageSize],
    queryFn: () => getBlocklist(page, pageSize),
  })

  const items = data?.items ?? []
  const totalPages = data?.totalPages ?? 1

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ['blocklist'] })

  const unblockMutation = useMutation({
    mutationFn: (id: number) => unblockEntry(id),
    onSuccess: () => {
      invalidate()
      toast.success(t('blocklist.unblocked'))
    },
    onError: () => toast.error(t('blocklist.unblockError')),
  })

  const bulkUnblockMutation = useMutation({
    mutationFn: (ids: number[]) => bulkUnblock(ids),
    onSuccess: () => {
      invalidate()
      setSelectedIds(new Set())
      toast.success(t('blocklist.bulkUnblocked'))
    },
    onError: () => toast.error(t('blocklist.unblockError')),
  })

  function handleSelect(id: number, checked: boolean) {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (checked) next.add(id)
      else next.delete(id)
      return next
    })
  }

  function handleSelectAll(checked: boolean) {
    if (checked) {
      setSelectedIds(new Set(items.map((e) => e.id)))
    } else {
      setSelectedIds(new Set())
    }
  }

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
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-zinc-100">{t('blocklist.title')}</h1>
      </div>

      {/* Bulk actions */}
      {selectedIds.size > 0 && (
        <div className="flex items-center gap-3 mb-4 px-3 py-2 rounded-md bg-zinc-900 border border-zinc-800">
          <span className="text-sm text-zinc-400">
            {t('blocklist.selected', { count: selectedIds.size })}
          </span>
          <Button
            variant="outline"
            size="sm"
            onClick={() => bulkUnblockMutation.mutate(Array.from(selectedIds))}
            disabled={bulkUnblockMutation.isPending}
          >
            <Trash2 className="size-3.5" />
            {t('blocklist.removeSelected')}
          </Button>
        </div>
      )}

      {/* Table */}
      {items.length === 0 ? (
        <p className="text-zinc-500 text-center py-8">{t('blocklist.empty')}</p>
      ) : (
        <>
          <Table>
            <TableHeader>
              <TableRow className="border-zinc-800 hover:bg-transparent">
                <TableHead className="w-10 text-zinc-400">
                  <input
                    type="checkbox"
                    checked={selectedIds.size === items.length && items.length > 0}
                    onChange={(e) => handleSelectAll(e.target.checked)}
                    className="size-4 rounded border-zinc-600 bg-zinc-900 accent-[#7C3AED]"
                  />
                </TableHead>
                <TableHead className="text-zinc-400">{t('blocklist.releaseTitle')}</TableHead>
                <TableHead className="text-zinc-400">{t('blocklist.magazine')}</TableHead>
                <TableHead className="text-zinc-400">{t('blocklist.indexer')}</TableHead>
                <TableHead className="text-zinc-400">{t('blocklist.date')}</TableHead>
                <TableHead className="text-zinc-400">{t('blocklist.reason')}</TableHead>
                <TableHead className="text-zinc-400">{t('blocklist.actions')}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((entry) => (
                <TableRow key={entry.id} className="border-zinc-800 hover:bg-zinc-900/50">
                  <TableCell>
                    <input
                      type="checkbox"
                      checked={selectedIds.has(entry.id)}
                      onChange={(e) => handleSelect(entry.id, e.target.checked)}
                      className="size-4 rounded border-zinc-600 bg-zinc-900 accent-[#7C3AED]"
                    />
                  </TableCell>
                  <TableCell className="text-zinc-100 text-sm max-w-xs truncate">
                    {entry.releaseTitle}
                  </TableCell>
                  <TableCell className="text-zinc-300 text-sm">{entry.magazineTitle}</TableCell>
                  <TableCell className="text-zinc-400 text-sm">{entry.indexer}</TableCell>
                  <TableCell className="text-zinc-400 text-sm">
                    {new Date(entry.date).toLocaleString()}
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline" className="text-xs">
                      {entry.reason}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <Button
                      variant="ghost"
                      size="icon-xs"
                      onClick={() => unblockMutation.mutate(entry.id)}
                      title={t('blocklist.unblock')}
                    >
                      <Unlock className="size-3.5 text-zinc-400" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>

          {/* Pagination */}
          <div className="flex items-center justify-between mt-4">
            <span className="text-sm text-zinc-500">
              {t('blocklist.page', { page, totalPages })}
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
