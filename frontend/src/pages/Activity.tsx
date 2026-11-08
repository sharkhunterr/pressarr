/**
 * Activity page — vue unifiée de toutes les actions asynchrones.
 *
 * Remplace l'ancienne page Queue. Sources agrégées :
 *  - downloads torrent/NZB (via download client polling)
 *  - direct downloads (Internet Archive, Anna's Archive)
 *  - imports (post-download → parse + IA + copy + cover)
 *  - analyses IA manuelles (Refresh IA)
 *  - scans auto-grab (search + auto-download)
 *  - actions planifiées (à venir)
 *
 * Chaque item affiche titre + sous-titre + progress + timeline
 * horizontale des steps + actions (cancel/remove).
 */
import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  AlertCircle,
  Ban,
  Check,
  ChevronDown,
  ChevronRight,
  Inbox,
  Loader2,
  Sparkles,
  X,
} from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'

import {
  cancelActivity,
  deleteActivity,
  listActivities,
  purgeActivityHistory,
  type Activity as ActivityRow,
  type ActivityKind,
  type ActivityStep,
} from '@/api/activity'
import { Trash2 } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'

const KIND_META: Record<
  string,
  { label: string; badge: string; short: string }
> = {
  download: {
    label: 'Téléchargement torrent/NZB',
    badge: 'bg-amber-500/15 text-amber-200 ring-amber-500/30',
    short: 'DL',
  },
  direct_download: {
    label: 'Téléchargement direct',
    badge: 'bg-sky-500/15 text-sky-200 ring-sky-500/30',
    short: 'AA/IA',
  },
  import: {
    label: 'Import + analyse IA',
    badge: 'bg-violet-500/15 text-violet-200 ring-violet-500/30',
    short: 'IMPORT',
  },
  analyze: {
    label: 'Analyse IA manuelle',
    badge: 'bg-purple-500/15 text-purple-200 ring-purple-500/30',
    short: 'IA',
  },
  ai_refresh: {
    label: 'Refresh IA',
    badge: 'bg-purple-500/15 text-purple-200 ring-purple-500/30',
    short: 'IA',
  },
  scan: {
    label: 'Scan auto-grab',
    badge: 'bg-emerald-500/15 text-emerald-200 ring-emerald-500/30',
    short: 'SCAN',
  },
  search: {
    label: 'Recherche',
    badge: 'bg-blue-500/15 text-blue-200 ring-blue-500/30',
    short: 'SEARCH',
  },
  grab: {
    label: 'Grab release',
    badge: 'bg-orange-500/15 text-orange-200 ring-orange-500/30',
    short: 'GRAB',
  },
  pack_grab: {
    label: 'Grab pack',
    badge: 'bg-fuchsia-500/15 text-fuchsia-200 ring-fuchsia-500/30',
    short: 'PACK',
  },
  pack_dispatch: {
    label: 'Dispatch pack',
    badge: 'bg-teal-500/15 text-teal-200 ring-teal-500/30',
    short: 'DISPATCH',
  },
  scheduled: {
    label: 'Tâche planifiée',
    badge: 'bg-blue-500/15 text-blue-200 ring-blue-500/30',
    short: 'CRON',
  },
}

const STATUS_STYLE: Record<string, string> = {
  queued: 'bg-zinc-700/40 text-zinc-300',
  running: 'bg-indigo-500/20 text-indigo-200',
  success: 'bg-emerald-500/20 text-emerald-200',
  failed: 'bg-red-500/20 text-red-300',
  cancelled: 'bg-zinc-600/40 text-zinc-400',
}

const KIND_TABS: Array<{ key: 'all' | ActivityKind; label: string }> = [
  { key: 'all', label: 'Tout' },
  { key: 'search', label: 'Recherches' },
  { key: 'grab', label: 'Grabs' },
  { key: 'pack_grab', label: 'Packs' },
  { key: 'pack_dispatch', label: 'Dispatch' },
  { key: 'download', label: 'Downloads' },
  { key: 'direct_download', label: 'AA / IA' },
  { key: 'import', label: 'Imports' },
  { key: 'ai_refresh', label: 'IA' },
  { key: 'scan', label: 'Scans' },
]

export default function ActivityPage() {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [kindFilter, setKindFilter] = useState<'all' | ActivityKind>('all')
  const [showHistory, setShowHistory] = useState(false)

  const listQ = useQuery({
    queryKey: ['activity-list', kindFilter, showHistory],
    queryFn: () =>
      listActivities({
        kind: kindFilter === 'all' ? undefined : (kindFilter as ActivityKind),
        status: showHistory ? 'history' : 'running',
        limit: 100,
      }),
    refetchInterval: 4000,
    // Ne re-fetch pas quand l'onglet est en background — sur mobile
    // le cache dure jusqu'au retour au premier plan.
    refetchIntervalInBackground: false,
  })

  const cancelMut = useMutation({
    mutationFn: (id: number) => cancelActivity(id),
    onSuccess: () => {
      toast.success('Activité annulée')
      qc.invalidateQueries({ queryKey: ['activity-list'] })
      qc.invalidateQueries({ queryKey: ['activity-counters'] })
    },
    onError: (e: Error) => toast.error(`Échec : ${e.message}`),
  })

  const deleteMut = useMutation({
    mutationFn: (id: number) => deleteActivity(id),
    onSuccess: () => {
      toast.success('Activité supprimée')
      qc.invalidateQueries({ queryKey: ['activity-list'] })
    },
    onError: (e: Error) => toast.error(`Échec : ${e.message}`),
  })

  const purgeMut = useMutation({
    mutationFn: () => purgeActivityHistory(),
    onSuccess: () => {
      toast.success('Historique purgé')
      qc.invalidateQueries({ queryKey: ['activity-list'] })
    },
    onError: (e: Error) => toast.error(`Échec : ${e.message}`),
  })

  const rows = listQ.data ?? []
  const total = rows.length
  const perKindCount = useMemo(() => {
    const counts: Record<string, number> = {}
    for (const r of rows) counts[r.kind] = (counts[r.kind] ?? 0) + 1
    return counts
  }, [rows])

  return (
    <div className="p-4 lg:p-8 space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-zinc-100">
            {t('nav.activity')}
          </h1>
          <p className="mt-1 text-xs text-zinc-500">
            Toutes les actions asynchrones — downloads, imports, analyses IA,
            scans, planifiées.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant={showHistory ? 'default' : 'outline'}
            size="sm"
            onClick={() => setShowHistory((v) => !v)}
          >
            {showHistory ? 'Voir en cours' : 'Voir historique'}
          </Button>
          {showHistory && rows.length > 0 && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                if (confirm(`Supprimer ${rows.length} activité(s) de l'historique ?`)) {
                  purgeMut.mutate()
                }
              }}
              disabled={purgeMut.isPending}
              className="text-destructive hover:text-destructive"
            >
              {purgeMut.isPending ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <Trash2 className="size-4" />
              )}
              Purger l'historique
            </Button>
          )}
        </div>
      </div>

      {/* Tabs / filters */}
      <div className="flex flex-wrap gap-1">
        {KIND_TABS.map((tab) => {
          const count = tab.key === 'all' ? total : (perKindCount[tab.key] ?? 0)
          const active = kindFilter === tab.key
          return (
            <button
              key={tab.key}
              type="button"
              onClick={() => setKindFilter(tab.key)}
              className={
                'px-2.5 py-1 text-xs rounded border ' +
                (active
                  ? 'bg-violet-500/20 border-violet-500/60 text-violet-200'
                  : 'bg-zinc-900 border-zinc-800 text-zinc-400 hover:text-zinc-200')
              }
            >
              {tab.label}
              {count > 0 && (
                <span className="ml-1.5 text-[10px] text-zinc-500">
                  ({count})
                </span>
              )}
            </button>
          )
        })}
      </div>

      {/* List */}
      {listQ.isLoading ? (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="size-6 animate-spin text-zinc-500" />
        </div>
      ) : rows.length === 0 ? (
        <div className="rounded-lg border border-dashed border-zinc-700 bg-zinc-900/40 p-12 text-center text-zinc-400">
          <Inbox className="mx-auto mb-3 size-8" />
          <p className="text-sm">
            {showHistory ? 'Aucune activité terminée.' : 'Aucune activité en cours.'}
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {rows.map((r) => (
            <ActivityCard
              key={r.id}
              row={r}
              onCancel={() => cancelMut.mutate(r.id)}
              cancelPending={cancelMut.isPending && cancelMut.variables === r.id}
              onDelete={() => {
                if (confirm(`Supprimer l'activité #${r.id} ?`)) deleteMut.mutate(r.id)
              }}
              deletePending={deleteMut.isPending && deleteMut.variables === r.id}
            />
          ))}
        </div>
      )}
    </div>
  )
}

function ActivityCard({
  row,
  onCancel,
  cancelPending,
  onDelete,
  deletePending,
}: {
  row: ActivityRow
  onCancel: () => void
  cancelPending: boolean
  onDelete: () => void
  deletePending: boolean
}) {
  const meta = KIND_META[row.kind] ?? {
    label: row.kind,
    badge: 'bg-zinc-800 text-zinc-300 ring-zinc-700',
    short: row.kind,
  }
  const statusStyle = STATUS_STYLE[row.status] ?? STATUS_STYLE.queued
  const [expanded, setExpanded] = useState(false)

  const isRunning = row.status === 'queued' || row.status === 'running'
  const elapsedMs = useLiveElapsed(row.startedAt, row.completedAt, isRunning)
  const progressClamped = Math.min(100, Math.max(0, row.progress))

  return (
    <div
      className={
        'rounded-md border px-3 py-2.5 ' +
        (row.kind === 'import' || row.kind === 'analyze'
          ? 'border-violet-500/30 bg-violet-500/[0.03]'
          : 'border-zinc-800 bg-zinc-950')
      }
    >
      <div className="flex flex-wrap items-start gap-2">
        <Badge
          className={`text-[10px] uppercase tracking-wider ring-1 ${meta.badge}`}
          title={meta.label}
        >
          {meta.short}
        </Badge>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
            <span className="truncate text-sm font-medium text-zinc-100">
              {row.title}
            </span>
            <span
              className={`rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase ${statusStyle}`}
            >
              {row.status}
            </span>
            {row.magazineId != null && (
              <span className="rounded bg-zinc-800/60 px-1.5 py-0.5 text-[10px] font-mono text-zinc-400">
                mag #{row.magazineId}
              </span>
            )}
            {row.issueId != null && (
              <span className="rounded bg-zinc-800/60 px-1.5 py-0.5 text-[10px] font-mono text-zinc-400">
                issue #{row.issueId}
              </span>
            )}
          </div>
          {row.subtitle && (
            <p className="mt-0.5 truncate text-xs text-zinc-500">
              {row.subtitle}
            </p>
          )}
          {row.statusMessage && (
            <p className="mt-0.5 text-xs text-violet-300 break-words">
              {row.statusMessage}
            </p>
          )}
          {row.errorMessage && (
            <p className="mt-0.5 truncate text-xs text-red-400">
              {row.errorMessage}
            </p>
          )}

          {/* Progress bar */}
          {(isRunning || progressClamped > 0) && (
            <div className="mt-2 flex items-center gap-3">
              <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-zinc-800">
                <div
                  className="h-full rounded-full bg-[#7C3AED] transition-all"
                  style={{ width: `${progressClamped}%` }}
                />
              </div>
              <span className="w-9 text-right text-xs text-zinc-400">
                {progressClamped.toFixed(0)}%
              </span>
            </div>
          )}

          {/* Stats line */}
          <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs text-zinc-500">
            <span title={row.startedAt ?? ''}>
              ⏱ {formatDuration(elapsedMs)}
            </span>
            <span className="text-zinc-700">·</span>
            <span>{row.steps.length} étape{row.steps.length > 1 ? 's' : ''}</span>
            {row.steps.length > 0 && (
              <>
                <span className="text-zinc-700">·</span>
                <button
                  type="button"
                  onClick={() => setExpanded((v) => !v)}
                  className="inline-flex items-center gap-0.5 hover:text-zinc-300"
                >
                  {expanded ? <ChevronDown className="size-3" /> : <ChevronRight className="size-3" />}
                  {expanded ? 'Masquer' : 'Détails'}
                </button>
              </>
            )}
          </div>

          {/* Step timeline (always shown if steps > 0) */}
          {row.steps.length > 0 && (
            <StepTimeline
              steps={row.steps}
              isDone={row.status === 'success'}
              isFailed={row.status === 'failed' || row.status === 'cancelled'}
            />
          )}

          {expanded && row.steps.length > 0 && (
            <div className="mt-3 space-y-2 border-t border-zinc-800 pt-3">
              {row.steps.map((s, idx) => (
                <StepDetail key={idx} step={s} />
              ))}
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="flex flex-shrink-0 items-center gap-1">
          {isRunning ? (
            <Button
              variant="ghost"
              size="icon-sm"
              onClick={onCancel}
              title="Annuler"
              disabled={cancelPending}
            >
              {cancelPending ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <X className="size-4 text-zinc-400" />
              )}
            </Button>
          ) : (
            <Button
              variant="ghost"
              size="icon-sm"
              onClick={onDelete}
              title="Supprimer"
              disabled={deletePending}
            >
              {deletePending ? (
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

function StepTimeline({
  steps,
  isDone,
  isFailed,
}: {
  steps: ActivityStep[]
  isDone: boolean
  isFailed: boolean
}) {
  return (
    <div className="mt-2 flex flex-wrap gap-1">
      {steps.map((s, idx) => {
        const isLast = idx === steps.length - 1
        const isRunning = isLast && !isDone && !isFailed
        const isError = s.step === 'error' || !!s.error
        const bg = isError
          ? 'bg-red-500/15 text-red-300 border-red-500/40'
          : isRunning
            ? 'bg-violet-500/20 text-violet-200 border-violet-500/60'
            : 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30'
        const Icon = isError ? AlertCircle : isRunning ? Loader2 : Check
        return (
          <span
            key={`${idx}-${s.step}`}
            className={
              'inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-[10px] leading-4 ' +
              bg
            }
            title={s.hint ? `${s.label} — ${s.hint}` : s.label}
          >
            <Icon className={'size-3 ' + (isRunning ? 'animate-spin' : '')} />
            <span className="max-w-[180px] truncate">{s.label}</span>
          </span>
        )
      })}
    </div>
  )
}

function StepDetail({ step }: { step: ActivityStep }) {
  const hasBody = Boolean(step.hint || step.error || step.elapsed_ms || step.output != null)
  return (
    <div className="rounded border border-zinc-800 bg-zinc-900/40 p-2 text-xs">
      <div className="flex items-baseline gap-2">
        <span className="font-mono text-violet-300">{step.step}</span>
        <span className="text-zinc-400">{step.label}</span>
        {step.at && (
          <span className="ml-auto text-[10px] text-zinc-600">
            {new Date(step.at).toLocaleTimeString('fr-FR')}
          </span>
        )}
      </div>
      {hasBody && (
        <div className="mt-1 space-y-1">
          {step.hint && (
            <div className="text-zinc-400">
              <span className="text-zinc-500">hint : </span>
              {step.hint}
            </div>
          )}
          {step.elapsed_ms != null && (
            <div className="text-zinc-500 text-[10px]">
              elapsed : {step.elapsed_ms} ms
            </div>
          )}
          {step.error && (
            <div className="text-red-400 break-all">
              <span className="text-zinc-500">error : </span>
              {step.error}
            </div>
          )}
          {step.output != null && (
            <pre className="mt-1 overflow-x-auto rounded bg-zinc-900 p-2 text-[10px] text-zinc-300">
              {typeof step.output === 'string'
                ? step.output.slice(0, 500)
                : JSON.stringify(step.output, null, 2).slice(0, 500)}
            </pre>
          )}
        </div>
      )}
    </div>
  )
}

function formatDuration(ms: number): string {
  if (ms < 0 || !Number.isFinite(ms)) return '-'
  const s = Math.floor(ms / 1000)
  if (s < 60) return `${s}s`
  const m = Math.floor(s / 60)
  const rem = s % 60
  return rem ? `${m}m ${rem}s` : `${m}m`
}

function useLiveElapsed(
  startedIso: string | null,
  completedIso: string | null,
  isRunning: boolean,
): number {
  const [now, setNow] = useState(Date.now())
  useEffect(() => {
    if (!isRunning) return
    const id = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(id)
  }, [isRunning])
  if (!startedIso) return 0
  // A finished activity lasted until it completed, not until now.
  const end = !isRunning && completedIso ? new Date(completedIso).getTime() : now
  return Math.max(0, end - new Date(startedIso).getTime())
}


// Empty-export sink for the Sparkles icon that might be needed later.
// Kept to prevent tree-shaking accidents when adding kinds in Phase 3.
void Sparkles
void Ban
