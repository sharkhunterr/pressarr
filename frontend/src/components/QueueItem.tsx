import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { X, Trash2, Ban, Import, Check, Loader2, AlertCircle } from 'lucide-react'

import { type QueueEntry } from '@/api/queue'
import { StatusBadge } from '@/components/StatusBadge'
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

/** Human "5m 23s" for import activity elapsed/ETA. */
function formatDuration(ms: number): string {
  if (ms < 0 || !Number.isFinite(ms)) return '-'
  const s = Math.floor(ms / 1000)
  if (s < 60) return `${s}s`
  const m = Math.floor(s / 60)
  const rem = s % 60
  return rem ? `${m}m ${rem}s` : `${m}m`
}

/** Total step budget expected for the pipeline — used to compute a
 *  best-effort ETA. Not exact (some steps skipped, some very fast),
 *  but gives the operator a realistic ballpark. */
const EXPECTED_TOTAL_STEPS = 12

interface QueueItemProps {
  entry: QueueEntry
  selected: boolean
  onSelect: (id: number, checked: boolean) => void
  onCancel: (id: number) => void
  onRemove: (id: number) => void
  onBlocklist: (id: number) => void
  onImport?: (id: number) => void
}

export function QueueItem({
  entry,
  selected,
  onSelect,
  onCancel,
  onRemove,
  onBlocklist,
  onImport,
}: QueueItemProps) {
  const { t } = useTranslation()

  // Post-download import activities (protocol === 'import') don't
  // have a byte-based size — use the progress field directly from the
  // backend which counts completed steps.
  const isImportActivity = entry.protocol === 'import'
  const progress = isImportActivity
    ? Math.round(entry.progress ?? 0)
    : entry.size > 0
      ? Math.round(((entry.size - entry.sizeLeft) / entry.size) * 100)
      : 0

  // Live-updating elapsed timer for import activities — re-render
  // every second so the operator sees the counter tick. Cheap : one
  // interval per import row, torn down on unmount / when done.
  const [now, setNow] = useState(Date.now())
  useEffect(() => {
    if (!isImportActivity || entry.status === 'completed' || entry.status === 'failed') {
      return
    }
    const id = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(id)
  }, [isImportActivity, entry.status])

  const startedMs = entry.added ? new Date(entry.added).getTime() : null
  const elapsedMs = startedMs ? now - startedMs : 0
  const stepsDone = entry.steps?.length ?? 0
  // ETA : linear extrapolation from steps done. Requires ≥ 2 steps
  // to be somewhat meaningful — before that we show "-".
  const etaMs =
    stepsDone >= 2 && stepsDone < EXPECTED_TOTAL_STEPS && elapsedMs > 0
      ? (elapsedMs / stepsDone) * (EXPECTED_TOTAL_STEPS - stepsDone)
      : null

  return (
    <div className="flex items-center gap-3 rounded-md border border-zinc-800 bg-zinc-950 px-4 py-3">
      {/* Checkbox */}
      <input
        type="checkbox"
        checked={selected}
        onChange={(e) => onSelect(entry.id, e.target.checked)}
        className="size-4 rounded border-zinc-600 bg-zinc-900 accent-[#7C3AED]"
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
        {entry.statusMessage && (
          <p className="text-xs text-violet-300 truncate mt-0.5">
            {entry.statusMessage}
          </p>
        )}
        {entry.status === 'failed' && entry.errorMessage && (
          <p className="text-xs text-red-400 truncate mt-0.5">{entry.errorMessage}</p>
        )}

        {/* Progress bar */}
        <div className="mt-2 flex items-center gap-3">
          <div className="flex-1 h-1.5 rounded-full bg-zinc-800 overflow-hidden">
            <div
              className="h-full rounded-full bg-[#7C3AED] transition-all"
              style={{ width: `${progress}%` }}
            />
          </div>
          <span className="text-xs text-zinc-400 w-8 text-right">{progress}%</span>
        </div>

        {/* Stats — bytes hidden for import activities (no meaningful
            size), replaced by elapsed / ETA / step count. */}
        <div className="flex items-center gap-3 mt-1 text-xs text-zinc-500">
          {isImportActivity ? (
            <>
              <span title={entry.added ? new Date(entry.added).toLocaleString('fr-FR') : ''}>
                ⏱ {formatDuration(elapsedMs)}
              </span>
              <span className="text-zinc-700">|</span>
              <span>ETA : {etaMs ? `~${formatDuration(etaMs)}` : '-'}</span>
              <span className="text-zinc-700">|</span>
              <span>{stepsDone}/{EXPECTED_TOTAL_STEPS} étapes</span>
              {entry.issueId && (
                <>
                  <span className="text-zinc-700">|</span>
                  <span>issue #{entry.issueId}</span>
                </>
              )}
            </>
          ) : (
            <>
              <span>{formatBytes(entry.size - entry.sizeLeft)} / {formatBytes(entry.size)}</span>
              <span className="text-zinc-700">|</span>
              <span>{formatSpeed(entry.speed)}</span>
              {entry.eta && (
                <>
                  <span className="text-zinc-700">|</span>
                  <span>{t('queue.eta')}: {entry.eta}</span>
                </>
              )}
            </>
          )}
        </div>

        {/* Step timeline for import activities — one pill per step,
            colour-coded (done = green, running = violet, error = red). */}
        {isImportActivity && entry.steps && entry.steps.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1">
            {entry.steps.map((s, idx) => {
              const isLast = idx === entry.steps!.length - 1
              const isRunning =
                isLast && entry.status !== 'completed' && entry.status !== 'failed'
              const isError = s.step === 'error'
              const bg = isError
                ? 'bg-red-500/15 text-red-300 border-red-500/40'
                : isRunning
                  ? 'bg-violet-500/20 text-violet-200 border-violet-500/60'
                  : 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30'
              const Icon = isError ? AlertCircle : isRunning ? Loader2 : Check
              return (
                <span
                  key={idx}
                  className={
                    'inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-[10px] leading-4 ' + bg
                  }
                  title={s.hint ? `${s.label} — ${s.hint}` : s.label}
                >
                  <Icon
                    className={
                      'size-3 ' + (isRunning ? 'animate-spin' : '')
                    }
                  />
                  {s.label}
                </span>
              )
            })}
          </div>
        )}
      </div>

      {/* Status */}
      <StatusBadge status={entry.status} tKey={`queue.status_${entry.status}`} />

      {/* Actions */}
      <div className="flex items-center gap-1">
        {entry.status === 'completed' && onImport && (
          <Button
            variant="ghost"
            size="icon-xs"
            onClick={() => onImport(entry.id)}
            title={t('queue.import')}
          >
            <Import className="size-3.5 text-[#7C3AED]" />
          </Button>
        )}
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
