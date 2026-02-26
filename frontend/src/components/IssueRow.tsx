import { useTranslation } from 'react-i18next'
import { Eye, EyeOff, Trash2, Search, Loader2, Download } from 'lucide-react'

import { type Issue } from '@/api/issues'
import { type QueueEntry } from '@/api/queue'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  TableCell,
  TableRow,
} from '@/components/ui/table'

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(1024))
  return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${units[i]}`
}

function formatSpeed(bytesPerSecond: number): string {
  if (bytesPerSecond === 0) return ''
  return `${formatBytes(bytesPerSecond)}/s`
}

function statusVariant(status: string): 'default' | 'secondary' | 'destructive' | 'outline' {
  switch (status) {
    case 'available':
      return 'default'
    case 'wanted':
      return 'secondary'
    case 'missing':
      return 'destructive'
    default:
      return 'outline'
  }
}

interface IssueRowProps {
  issue: Issue
  selected: boolean
  queueItem?: QueueEntry
  onSelect: (id: number, checked: boolean) => void
  onToggleMonitor: (id: number, monitored: boolean) => void
  onDeleteFile: (id: number) => void
  onSearch: (id: number) => void
}

export function IssueRow({
  issue,
  selected,
  queueItem,
  onSelect,
  onToggleMonitor,
  onDeleteFile,
  onSearch,
}: IssueRowProps) {
  const { t } = useTranslation()

  const displayNumber = issue.isSpecial
    ? t('issues.special')
    : issue.number !== null
      ? `#${issue.number}`
      : '-'

  const displayDate = issue.year
    ? issue.month
      ? `${String(issue.month).padStart(2, '0')}/${issue.year}`
      : String(issue.year)
    : issue.publicationDate
      ? new Date(issue.publicationDate).toLocaleDateString()
      : '-'

  // Queue progress
  const isInQueue = !!queueItem
  const queueProgress = queueItem
    ? queueItem.size > 0
      ? Math.round(((queueItem.size - queueItem.sizeLeft) / queueItem.size) * 100)
      : 0
    : 0

  return (
    <TableRow className="border-zinc-800 hover:bg-zinc-900/50">
      <TableCell className="w-10">
        <input
          type="checkbox"
          checked={selected}
          onChange={(e) => onSelect(issue.id, e.target.checked)}
          className="size-4 rounded border-zinc-600 bg-zinc-900 text-[#E85D04] focus:ring-[#E85D04] accent-[#E85D04]"
        />
      </TableCell>
      <TableCell className="text-zinc-100 font-medium">
        {displayNumber}
      </TableCell>
      <TableCell className="text-zinc-400">
        {displayDate}
      </TableCell>
      <TableCell>
        {issue.title && (
          <span className="text-zinc-300 text-sm">{issue.title}</span>
        )}
      </TableCell>
      <TableCell>
        {isInQueue ? (
          <div className="flex flex-col gap-1">
            <div className="flex items-center gap-1.5">
              <Loader2 className="size-3 animate-spin text-[#E85D04]" />
              <Badge variant="outline" className="border-[#E85D04] text-[#E85D04]">
                {t(`queue.status_${queueItem.status}`, queueItem.status)}
              </Badge>
            </div>
            {/* Progress bar */}
            <div className="flex items-center gap-2">
              <div className="flex-1 h-1 rounded-full bg-zinc-800 overflow-hidden max-w-[120px]">
                <div
                  className="h-full rounded-full bg-[#E85D04] transition-all"
                  style={{ width: `${queueProgress}%` }}
                />
              </div>
              <span className="text-[10px] text-zinc-500">{queueProgress}%</span>
              {queueItem.speed > 0 && (
                <span className="text-[10px] text-zinc-500">{formatSpeed(queueItem.speed)}</span>
              )}
            </div>
          </div>
        ) : (
          <>
            <Badge variant={statusVariant(issue.status)}>
              {t(`status.${issue.status}`, issue.status)}
            </Badge>
            {issue.isForecast && (
              <Badge variant="outline" className="ml-1 text-xs">
                {t('issues.forecast')}
              </Badge>
            )}
          </>
        )}
      </TableCell>
      <TableCell className="text-zinc-400 text-sm">
        {issue.file ? (
          <div className="flex items-center gap-2">
            <span className="uppercase text-zinc-300">{issue.file.format}</span>
            <span className="text-zinc-500">|</span>
            <span>{issue.file.quality}</span>
            <span className="text-zinc-500">|</span>
            <span>{formatBytes(issue.file.size)}</span>
            {issue.file.releaseGroup && (
              <>
                <span className="text-zinc-500">|</span>
                <span className="text-zinc-500">{issue.file.releaseGroup}</span>
              </>
            )}
          </div>
        ) : isInQueue ? (
          <span className="text-zinc-500 text-xs">
            {queueItem.downloadClient}
            {queueItem.size > 0 && ` — ${formatBytes(queueItem.size)}`}
          </span>
        ) : (
          <span className="text-zinc-600">{t('issues.noFile')}</span>
        )}
      </TableCell>
      <TableCell>
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon-xs"
            onClick={() => onToggleMonitor(issue.id, !issue.monitored)}
            title={issue.monitored ? t('issues.unmonitor') : t('issues.monitor')}
          >
            {issue.monitored ? (
              <Eye className="size-3.5 text-[#E85D04]" />
            ) : (
              <EyeOff className="size-3.5 text-zinc-500" />
            )}
          </Button>
          <Button
            variant="ghost"
            size="icon-xs"
            onClick={() => onSearch(issue.id)}
            title={t('issues.searchRelease')}
          >
            <Search className="size-3.5 text-zinc-400" />
          </Button>
          {issue.file && (
            <>
              <Button
                variant="ghost"
                size="icon-xs"
                onClick={() => window.open(`/api/v1/issue/${issue.id}/file`, '_blank')}
                title={t('issues.downloadFile')}
              >
                <Download className="size-3.5 text-zinc-400" />
              </Button>
              <Button
                variant="ghost"
                size="icon-xs"
                onClick={() => onDeleteFile(issue.id)}
                title={t('issues.deleteFile')}
              >
                <Trash2 className="size-3.5 text-destructive" />
              </Button>
            </>
          )}
        </div>
      </TableCell>
    </TableRow>
  )
}
