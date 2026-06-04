import { useState, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation } from '@tanstack/react-query'
import { X, Trash2, Inbox } from 'lucide-react'
import { toast } from 'sonner'

import { removeFromQueue, bulkRemove, triggerImport } from '@/api/queue'
import { useQueue } from '@/hooks/useQueue'
import JDownloaderPanel from '@/components/JDownloaderPanel'
import { QueueItem } from '@/components/QueueItem'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Switch } from '@/components/ui/switch'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'

export default function Queue() {
  const { t } = useTranslation()
  const { queue, isLoading, invalidate } = useQueue()
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set())
  const [removeDialog, setRemoveDialog] = useState<{
    open: boolean
    id: number | null
    title: string
    blocklist: boolean
  }>({ open: false, id: null, title: '', blocklist: false })
  const [removeFromClient, setRemoveFromClient] = useState(false)

  const removeMutation = useMutation({
    mutationFn: ({ id, blocklist, removeFromClient: rfc }: { id: number; blocklist?: boolean; removeFromClient?: boolean }) =>
      removeFromQueue(id, { blocklist, removeFromClient: rfc }),
    onSuccess: () => {
      invalidate()
      setRemoveDialog({ open: false, id: null, title: '', blocklist: false })
      setRemoveFromClient(false)
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

  const importMutation = useMutation({
    mutationFn: (id: number) => triggerImport(id),
    onSuccess: (data) => {
      invalidate()
      if (data.success) {
        toast.success(t('queue.importSuccess'))
      } else {
        toast.error(data.message || t('queue.importError'))
      }
    },
    onError: () => toast.error(t('queue.importError')),
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

  function openRemoveDialog(id: number, blocklist: boolean) {
    const entry = queue.find((e) => e.id === id)
    setRemoveFromClient(false)
    setRemoveDialog({
      open: true,
      id,
      title: entry?.title ?? '',
      blocklist,
    })
  }

  function confirmRemove() {
    if (removeDialog.id === null) return
    removeMutation.mutate({
      id: removeDialog.id,
      blocklist: removeDialog.blocklist,
      removeFromClient,
    })
  }

  if (isLoading) {
    return (
      <div className="p-4 lg:p-8">
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
    <div className="p-4 lg:p-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-zinc-100">{t('queue.title')}</h1>
      </div>

      <Tabs defaultValue="downloads" className="space-y-4">
        <TabsList className="bg-zinc-900 border-zinc-800">
          <TabsTrigger value="downloads">Torrent / NZB queue</TabsTrigger>
          <TabsTrigger value="jdownloader">JDownloader 2</TabsTrigger>
        </TabsList>

        <TabsContent value="jdownloader">
          <JDownloaderPanel />
        </TabsContent>

        <TabsContent value="downloads" className="space-y-4">
        {queue.length > 0 && (
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={selectedIds.size === queue.length && queue.length > 0}
              onChange={(e) => handleSelectAll(e.target.checked)}
              className="size-4 rounded border-zinc-600 bg-zinc-900 accent-[#7C3AED]"
            />
            <span className="text-sm text-zinc-400">{t('queue.selectAll')}</span>
          </div>
        )}

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
              onCancel={(id) => openRemoveDialog(id, false)}
              onRemove={(id) => openRemoveDialog(id, false)}
              onBlocklist={(id) => openRemoveDialog(id, true)}
              onImport={(id) => importMutation.mutate(id)}
            />
          ))}
        </div>
      )}
        </TabsContent>
      </Tabs>

      {/* Remove Confirmation Dialog */}
      <Dialog open={removeDialog.open} onOpenChange={(open) => {
        if (!open) setRemoveDialog({ open: false, id: null, title: '', blocklist: false })
      }}>
        <DialogContent className="sm:max-w-md bg-zinc-950 border-zinc-800">
          <DialogHeader>
            <DialogTitle className="text-zinc-100">
              {removeDialog.blocklist
                ? t('queue.blocklistTitle')
                : t('queue.removeTitle')}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <p className="text-sm text-zinc-400">
              {t('queue.removeConfirm', { title: removeDialog.title })}
            </p>
            <div className="flex items-center justify-between">
              <label className="text-sm font-medium text-zinc-300">
                {t('queue.removeFromClient')}
              </label>
              <Switch
                checked={removeFromClient}
                onCheckedChange={(checked) => setRemoveFromClient(checked === true)}
              />
            </div>
            <p className="text-xs text-zinc-500">
              {t('queue.removeFromClientHelp')}
            </p>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setRemoveDialog({ open: false, id: null, title: '', blocklist: false })}
            >
              {t('common.cancel')}
            </Button>
            <Button
              variant="destructive"
              disabled={removeMutation.isPending}
              onClick={confirmRemove}
            >
              {t('common.confirm')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
