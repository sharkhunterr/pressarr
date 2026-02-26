import { useState, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation } from '@tanstack/react-query'
import { X, Trash2, Inbox } from 'lucide-react'
import { toast } from 'sonner'

import { removeFromQueue, bulkRemove } from '@/api/queue'
import { useQueue } from '@/hooks/useQueue'
import { QueueItem } from '@/components/QueueItem'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'

export default function Queue() {
  const { t } = useTranslation()
  const { queue, isLoading, invalidate } = useQueue()
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set())

  const removeMutation = useMutation({
    mutationFn: ({ id, blocklist }: { id: number; blocklist?: boolean }) =>
      removeFromQueue(id, blocklist),
    onSuccess: () => {
      invalidate()
      toast.success(t('queue.removed'))
    },
    onError: () => toast.error(t('queue.removeError')),
  })

  const bulkRemoveMutation = useMutation({
    mutationFn: ({ ids, blocklist }: { ids: number[]; blocklist?: boolean }) =>
      bulkRemove(ids, blocklist),
    onSuccess: () => {
      invalidate()
      setSelectedIds(new Set())
      toast.success(t('queue.bulkRemoved'))
    },
    onError: () => toast.error(t('queue.removeError')),
  })

  const handleSelect = useCallback((id: number, checked: boolean) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (checked) next.add(id)
      else next.delete(id)
      return next
    })
  }, [])

  function handleSelectAll(checked: boolean) {
    if (checked) {
      setSelectedIds(new Set(queue.map((e) => e.id)))
    } else {
      setSelectedIds(new Set())
    }
  }

  function handleCancelAll() {
    const ids = Array.from(selectedIds)
    if (ids.length === 0) return
    bulkRemoveMutation.mutate({ ids })
  }

  function handleRemoveAll() {
    const ids = Array.from(selectedIds)
    if (ids.length === 0) return
    bulkRemoveMutation.mutate({ ids })
  }

  if (isLoading) {
    return (
      <div className="p-8">
        <Skeleton className="h-8 w-48 bg-zinc-800 mb-6" />
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-24 bg-zinc-800 rounded-lg" />
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="p-8 max-w-4xl">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-zinc-100">{t('queue.title')}</h1>

        {queue.length > 0 && (
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={selectedIds.size === queue.length && queue.length > 0}
              onChange={(e) => handleSelectAll(e.target.checked)}
              className="size-4 rounded border-zinc-600 bg-zinc-900 accent-[#E85D04]"
            />
            <span className="text-sm text-zinc-400">{t('queue.selectAll')}</span>
          </div>
        )}
      </div>

      {/* Bulk actions */}
      {selectedIds.size > 0 && (
        <div className="flex items-center gap-3 mb-4 px-3 py-2 rounded-md bg-zinc-900 border border-zinc-800">
          <span className="text-sm text-zinc-400">
            {t('queue.selected', { count: selectedIds.size })}
          </span>
          <Button
            variant="outline"
            size="sm"
            onClick={handleCancelAll}
            disabled={bulkRemoveMutation.isPending}
          >
            <X className="size-3.5" />
            {t('queue.cancelAll')}
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={handleRemoveAll}
            disabled={bulkRemoveMutation.isPending}
          >
            <Trash2 className="size-3.5" />
            {t('queue.removeAll')}
          </Button>
        </div>
      )}

      {/* Queue items */}
      {queue.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16">
          <Inbox className="size-12 text-zinc-700 mb-4" />
          <p className="text-zinc-500">{t('queue.empty')}</p>
        </div>
      ) : (
        <div className="space-y-3">
          {queue.map((entry) => (
            <QueueItem
              key={entry.id}
              entry={entry}
              selected={selectedIds.has(entry.id)}
              onSelect={handleSelect}
              onCancel={(id) => removeMutation.mutate({ id })}
              onRemove={(id) => removeMutation.mutate({ id })}
              onBlocklist={(id) => removeMutation.mutate({ id, blocklist: true })}
            />
          ))}
        </div>
      )}
    </div>
  )
}
