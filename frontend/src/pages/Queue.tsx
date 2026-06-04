import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, FileText, Inbox, Loader2, Trash2, X } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'

import { bulkRemove, removeFromQueue, triggerImport, type QueueEntry } from '@/api/queue'
import {
  clearAllCrawljobs,
  deleteCompletedFolder,
  deleteCrawljob,
  getJDownloaderState,
  type CompletedFile,
  type CompletedFolder,
  type CrawljobItem,
  type JDownloaderState,
} from '@/api/system'
import { useQueue } from '@/hooks/useQueue'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'

// Single unified queue: pressarr-side qBittorrent / NZB items
// AND JDownloader 2 crawljobs / completed folders rendered in
// the same list with a per-row source badge. Operators don't
// have to remember which tab a release lives in.

interface UnifiedRow {
  key: string
  /** Visible source label rendered as the leading badge.
   *  Drives the colour treatment too. */
  source: 'qbit' | 'jd2-pending' | 'jd2-completed'
  sourceLabel: string
  title: string
  subtitle?: string
  status: string
  /** 0-100 when meaningful (qBit downloading), otherwise null. */
  progress: number | null
  sizeBytes?: number
  speedBytesPerSec?: number
  errorMessage?: string
  /** Tag chips after the title (issue number, hoster, file count). */
  chips?: string[]
  /** Action callbacks rendered as trailing icon buttons.
   *  Only the ones that make sense for the row appear. */
  onRemove?: () => void
  onImport?: () => void
  onCancel?: () => void
  busy?: boolean
}

function formatBytes(b: number): string {
  if (!b) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  const i = Math.min(units.length - 1, Math.floor(Math.log(b) / Math.log(1024)))
  return `${(b / Math.pow(1024, i)).toFixed(1)} ${units[i]}`
}

function formatSpeed(bps: number): string {
  if (!bps) return ''
  return `${formatBytes(bps)}/s`
}

function hostFromUrl(url: string | null): string {
  if (!url) return ''
  try {
    return new URL(url).hostname.replace(/^www\d?\./, '')
  } catch {
    return url
  }
}

function qbitToRow(
  entry: QueueEntry,
  onRemove: () => void,
  onCancel: () => void,
  onImport: () => void,
): UnifiedRow {
  const progress =
    entry.size > 0
      ? Math.round(((entry.size - entry.sizeLeft) / entry.size) * 100)
      : entry.progress * 100 || null
  const chips: string[] = []
  if (entry.issueNumber !== null) chips.push(`#${entry.issueNumber}`)
  if (entry.protocol) chips.push(entry.protocol)
  return {
    key: `qbit-${entry.id}`,
    source: 'qbit',
    sourceLabel: entry.downloadClient || 'qBittorrent',
    title: entry.magazineTitle || entry.title,
    subtitle: entry.magazineTitle ? entry.title : undefined,
    status: entry.status,
    progress: typeof progress === 'number' ? progress : null,
    sizeBytes: entry.size,
    speedBytesPerSec: entry.speed,
    errorMessage:
      entry.status === 'failed' && entry.errorMessage
        ? entry.errorMessage
        : undefined,
    chips,
    onRemove,
    onCancel,
    onImport: entry.status === 'completed' ? onImport : undefined,
  }
}

function pendingCrawljobToRow(
  c: CrawljobItem,
  onRemove: () => void,
  busy: boolean,
): UnifiedRow {
  const chips = [hostFromUrl(c.primaryUrl)].filter(Boolean)
  if (c.textUrlCount > 1) chips.push(`${c.textUrlCount} URLs (legacy)`)
  return {
    key: `jd2-pending-${c.filename}`,
    source: 'jd2-pending',
    sourceLabel: 'JDownloader 2',
    title: c.packageName || c.filename,
    subtitle: c.releaseId ? `Release #${c.releaseId}` : c.filename,
    status: 'queued',
    progress: null,
    chips,
    onRemove,
    busy,
  }
}

function completedFolderToRow(
  f: CompletedFolder,
  onRemove: () => void,
  busy: boolean,
): UnifiedRow {
  const inProgress = f.files.some((x: CompletedFile) => x.isPart)
  const chips = [`${f.fileCount} file${f.fileCount > 1 ? 's' : ''}`]
  return {
    key: `jd2-completed-${f.folderName}`,
    source: 'jd2-completed',
    sourceLabel: 'JDownloader 2',
    title: f.folderName,
    subtitle:
      f.files
        .map((x) => x.name)
        .slice(0, 3)
        .join(', ') || undefined,
    status: inProgress ? 'downloading' : 'downloaded',
    progress: inProgress ? null : 100,
    sizeBytes: f.totalSizeBytes,
    chips,
    onRemove,
    busy,
  }
}

const SOURCE_STYLE: Record<UnifiedRow['source'], string> = {
  qbit: 'bg-amber-500/15 text-amber-200 ring-amber-500/30',
  'jd2-pending': 'bg-sky-500/15 text-sky-200 ring-sky-500/30',
  'jd2-completed': 'bg-emerald-500/15 text-emerald-200 ring-emerald-500/30',
}

const STATUS_STYLE: Record<string, string> = {
  downloading: 'bg-indigo-500/20 text-indigo-200',
  queued: 'bg-zinc-700/40 text-zinc-300',
  paused: 'bg-zinc-700/40 text-zinc-300',
  completed: 'bg-emerald-500/20 text-emerald-200',
  downloaded: 'bg-emerald-500/20 text-emerald-200',
  imported: 'bg-emerald-500/20 text-emerald-200',
  failed: 'bg-red-500/20 text-red-300',
}

function UnifiedRow({ row }: { row: UnifiedRow }) {
  const statusKey = row.status.toLowerCase()
  return (
    <div className="rounded-md border border-zinc-800 bg-zinc-950 px-3 py-2.5">
      <div className="flex flex-wrap items-start gap-2">
        <Badge
          className={`text-[10px] uppercase tracking-wider ring-1 ${SOURCE_STYLE[row.source]}`}
        >
          {row.sourceLabel}
        </Badge>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
            <span className="truncate text-sm font-medium text-zinc-100">
              {row.title}
            </span>
            <span
              className={`rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase ${STATUS_STYLE[statusKey] || 'bg-zinc-700/40 text-zinc-300'}`}
            >
              {row.status}
            </span>
            {row.chips?.map((c) => (
              <span
                key={c}
                className="rounded bg-zinc-800/60 px-1.5 py-0.5 text-[10px] font-mono text-zinc-400"
              >
                {c}
              </span>
            ))}
          </div>
          {row.subtitle && (
            <p className="mt-0.5 truncate text-xs text-zinc-500">{row.subtitle}</p>
          )}
          {row.errorMessage && (
            <p className="mt-0.5 truncate text-xs text-red-400">
              {row.errorMessage}
            </p>
          )}

          {row.progress !== null && (
            <div className="mt-2 flex items-center gap-3">
              <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-zinc-800">
                <div
                  className="h-full rounded-full bg-[#7C3AED] transition-all"
                  style={{ width: `${row.progress}%` }}
                />
              </div>
              <span className="w-9 text-right text-xs text-zinc-400">
                {row.progress}%
              </span>
            </div>
          )}

          {(row.sizeBytes || row.speedBytesPerSec) && (
            <div className="mt-1 flex items-center gap-2 text-xs text-zinc-500">
              {row.sizeBytes ? <span>{formatBytes(row.sizeBytes)}</span> : null}
              {row.speedBytesPerSec ? (
                <>
                  <span className="text-zinc-700">·</span>
                  <span>{formatSpeed(row.speedBytesPerSec)}</span>
                </>
              ) : null}
            </div>
          )}
        </div>

        <div className="flex flex-shrink-0 items-center gap-1">
          {row.onImport && (
            <Button
              variant="ghost"
              size="icon-sm"
              onClick={row.onImport}
              title="Import"
              disabled={row.busy}
            >
              <CheckCircle2 className="size-4 text-emerald-400" />
            </Button>
          )}
          {row.onCancel && (
            <Button
              variant="ghost"
              size="icon-sm"
              onClick={row.onCancel}
              title="Cancel"
              disabled={row.busy}
            >
              <X className="size-4 text-zinc-400" />
            </Button>
          )}
          {row.onRemove && (
            <Button
              variant="ghost"
              size="icon-sm"
              onClick={row.onRemove}
              title="Remove"
              disabled={row.busy}
            >
              {row.busy ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <Trash2 className="size-4 text-zinc-400" />
              )}
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}

export default function Queue() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const { queue: qbitQueue, isLoading: qbitLoading, invalidate: invalidateQbit } = useQueue()

  const { data: jd2State, isLoading: jd2Loading } = useQuery({
    queryKey: ['jdownloader-state'],
    queryFn: getJDownloaderState,
    // Poll the same JD2 file-system state every 5s so the unified
    // queue stays in sync while JD2 chews through its work.
    refetchInterval: 5000,
  })

  const invalidateJd2 = () =>
    queryClient.invalidateQueries({ queryKey: ['jdownloader-state'] })

  // qBit-side mutations reuse the existing API surface.
  const qbitRemove = useMutation({
    mutationFn: (id: number) => removeFromQueue(id),
    onSuccess: () => invalidateQbit(),
    onError: (e) => toast.error((e as Error).message),
  })
  const qbitCancel = useMutation({
    mutationFn: (id: number) =>
      removeFromQueue(id, { removeFromClient: true }),
    onSuccess: () => invalidateQbit(),
    onError: (e) => toast.error((e as Error).message),
  })
  const qbitImport = useMutation({
    mutationFn: (id: number) => triggerImport(id),
    onSuccess: () => {
      toast.success(t('queue.imported'))
      invalidateQbit()
    },
    onError: (e) => toast.error((e as Error).message),
  })
  const qbitBulkRemove = useMutation({
    mutationFn: () => bulkRemove(qbitQueue.map((q) => q.id), false),
    onSuccess: () => invalidateQbit(),
    onError: (e) => toast.error((e as Error).message),
  })

  // JD2 mutations
  const jd2DeleteCrawljob = useMutation({
    mutationFn: (filename: string) => deleteCrawljob(filename),
    onSuccess: () => invalidateJd2(),
    onError: (e) => toast.error((e as Error).message),
  })
  const jd2ClearAll = useMutation({
    mutationFn: () => clearAllCrawljobs(),
    onSuccess: (d) => {
      toast.success(`Cleared ${d.deleted} queued JD2 job(s)`)
      invalidateJd2()
    },
    onError: (e) => toast.error((e as Error).message),
  })
  const jd2DeleteFolder = useMutation({
    mutationFn: (name: string) => deleteCompletedFolder(name),
    onSuccess: () => invalidateJd2(),
    onError: (e) => toast.error((e as Error).message),
  })

  if (qbitLoading || jd2Loading) {
    return (
      <div className="p-4 lg:p-8">
        <Skeleton className="mb-6 h-8 w-48 bg-zinc-800" />
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-20 rounded-md bg-zinc-800" />
          ))}
        </div>
      </div>
    )
  }

  const rows: UnifiedRow[] = []

  // qBit rows first so an active download is visible at the top
  // (most relevant to the operator).
  for (const e of qbitQueue) {
    rows.push(
      qbitToRow(
        e,
        () => qbitRemove.mutate(e.id),
        () => qbitCancel.mutate(e.id),
        () => qbitImport.mutate(e.id),
      ),
    )
  }
  // Then JD2 pending — these are the in-flight grabs JD2 is
  // expected to pick up next.
  const jd2: JDownloaderState | undefined = jd2State
  if (jd2?.enabled) {
    for (const c of jd2.pendingJobs || []) {
      const busy =
        jd2DeleteCrawljob.isPending &&
        jd2DeleteCrawljob.variables === c.filename
      rows.push(
        pendingCrawljobToRow(
          c,
          () => jd2DeleteCrawljob.mutate(c.filename),
          !!busy,
        ),
      )
    }
    // Then JD2 completed — terminal state, helps the operator
    // confirm what's actually landed.
    for (const f of jd2.completedFolders || []) {
      const busy =
        jd2DeleteFolder.isPending &&
        jd2DeleteFolder.variables === f.folderName
      rows.push(
        completedFolderToRow(
          f,
          () => jd2DeleteFolder.mutate(f.folderName),
          !!busy,
        ),
      )
    }
  }

  const totalQbit = qbitQueue.length
  const totalJd2Pending = jd2?.pendingJobs?.length || 0
  const totalJd2Done = jd2?.completedFolders?.length || 0

  return (
    <div className="p-4 lg:p-8 space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-zinc-100">
            {t('queue.title')}
          </h1>
          <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-zinc-400">
            <Badge
              className={`text-[10px] uppercase ring-1 ${SOURCE_STYLE.qbit}`}
            >
              qBit · {totalQbit}
            </Badge>
            {jd2?.enabled && (
              <>
                <Badge
                  className={`text-[10px] uppercase ring-1 ${SOURCE_STYLE['jd2-pending']}`}
                >
                  JD2 queued · {totalJd2Pending}
                </Badge>
                <Badge
                  className={`text-[10px] uppercase ring-1 ${SOURCE_STYLE['jd2-completed']}`}
                >
                  JD2 done · {totalJd2Done}
                </Badge>
              </>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          {totalJd2Pending > 0 && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => jd2ClearAll.mutate()}
              disabled={jd2ClearAll.isPending}
            >
              {jd2ClearAll.isPending ? (
                <Loader2 className="size-3 animate-spin" />
              ) : (
                <FileText className="size-3" />
              )}
              Clear JD2 queue
            </Button>
          )}
          {totalQbit > 0 && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => qbitBulkRemove.mutate()}
              disabled={qbitBulkRemove.isPending}
            >
              {qbitBulkRemove.isPending ? (
                <Loader2 className="size-3 animate-spin" />
              ) : (
                <Trash2 className="size-3" />
              )}
              Clear qBit
            </Button>
          )}
        </div>
      </div>

      {rows.length === 0 ? (
        <div className="rounded-lg border border-dashed border-zinc-700 bg-zinc-900/40 p-12 text-center text-zinc-400">
          <Inbox className="mx-auto mb-3 size-8" />
          <p className="text-sm">{t('queue.empty')}</p>
        </div>
      ) : (
        <div className="space-y-2">
          {rows.map((r) => (
            <UnifiedRow key={r.key} row={r} />
          ))}
        </div>
      )}
    </div>
  )
}
