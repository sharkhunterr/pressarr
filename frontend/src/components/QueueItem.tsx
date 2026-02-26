import { useTranslation } from 'react-i18next'
import { X, Trash2, Ban } from 'lucide-react'

import { type QueueEntry } from '@/api/queue'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(1024))
  return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${units[i]}`
}

function formatSpeed(bytesPerSecond: number): string {
  if (bytesPerSecond === 0) return '-'
  return `${formatBytes(bytesPerSecond)}/s`
}

function statusVariant(status: string): 'default' | 'secondary' | 'destructive' | 'outline' {
  switch (status) {
    case 'downloading':
      return 'default'
    case 'paused':
      return 'secondary'
    case 'failed':
      return 'destructive'
    default:
      return 'outline'
  }
}

interface QueueItemProps {
  entry: QueueEntry
  selected: boolean
  onSelect: (id: number, checked: boolean) => void
  onCancel: (id: number) => void
  onRemove: (id: number) => void
  onBlocklist: (id: number) => void
}

export function QueueItem({
  entry,
  selected,
  onSelect,
  onCancel,
  onRemove,
  onBlocklist,
}: QueueItemProps) {
  const { t } = useTranslation()

  const progress = entry.size > 0
    ? Math.round(((entry.size - entry.sizeLeft) / entry.size) * 100)
    : 0

  return (
    <div className="flex items-center gap-3 rounded-md border border-zinc-800 bg-zinc-950 px-4 py-3">
      {/* Checkbox */}
      <input
        type="checkbox"
        checked={selected}
        onChange={(e) => onSelect(entry.id, e.target.checked)}
        className="size-4 rounded border-zinc-600 bg-zinc-900 accent-[#E85D04]"
      />

      {/* Info */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-zinc-100 truncate">
            {entry.magazineTitle}
          </span>
          {entry.issueNumber !== null && (
            <span className="text-xs text-zinc-500">#{entry.issueNumber}</span>
          )}
        </div>
        <p className="text-xs text-zinc-500 truncate mt-0.5">{entry.title}</p>

        {/* Progress bar */}
        <div className="mt-2 flex items-center gap-3">
          <div className="flex-1 h-1.5 rounded-full bg-zinc-800 overflow-hidden">
            <div
              className="h-full rounded-full bg-[#E85D04] transition-all"
              style={{ width: `${progress}%` }}
            />
          </div>
          <span className="text-xs text-zinc-400 w-8 text-right">{progress}%</span>
        </div>

        {/* Stats */}
        <div className="flex items-center gap-3 mt-1 text-xs text-zinc-500">
          <span>{formatBytes(entry.size - entry.sizeLeft)} / {formatBytes(entry.size)}</span>
          <span className="text-zinc-700">|</span>
          <span>{formatSpeed(entry.speed)}</span>
          {entry.eta && (
            <>
              <span className="text-zinc-700">|</span>
              <span>{t('queue.eta')}: {entry.eta}</span>
            </>
          )}
        </div>
      </div>

      {/* Status */}
      <Badge variant={statusVariant(entry.status)}>
        {t(`queue.status_${entry.status}`, entry.status)}
      </Badge>

      {/* Actions */}
      <div className="flex items-center gap-1">
        <Button
          variant="ghost"
          size="icon-xs"
          onClick={() => onCancel(entry.id)}
          title={t('queue.cancel')}
        >
          <X className="size-3.5 text-zinc-400" />
        </Button>
        <Button
          variant="ghost"
          size="icon-xs"
          onClick={() => onRemove(entry.id)}
          title={t('queue.remove')}
        >
          <Trash2 className="size-3.5 text-zinc-400" />
        </Button>
        <Button
          variant="ghost"
          size="icon-xs"
          onClick={() => onBlocklist(entry.id)}
          title={t('queue.blocklist')}
        >
          <Ban className="size-3.5 text-zinc-400" />
        </Button>
      </div>
    </div>
  )
}
