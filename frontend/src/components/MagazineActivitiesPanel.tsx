/**
 * Compact "Activities" widget embeddable dans la page d'un
 * magazine ou d'une issue. Liste les activités asynchrones (imports,
 * analyses IA, scans, downloads) filtrées par le contexte donné,
 * avec polling léger pour rester à jour.
 */
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { AlertCircle, Check, Loader2 } from 'lucide-react'

import { listActivities, type Activity } from '@/api/activity'

interface Props {
  magazineId?: number
  issueId?: number
  packId?: number
  /** Nombre max d'items à afficher (défaut 5). */
  limit?: number
}

const KIND_LABEL: Record<string, string> = {
  download: 'Téléchargement',
  direct_download: 'Téléchargement direct',
  import: 'Import + IA',
  analyze: 'Analyse IA',
  scan: 'Scan',
  scheduled: 'Planifiée',
}

export function MagazineActivitiesPanel({ magazineId, issueId, packId, limit = 5 }: Props) {
  const q = useQuery({
    queryKey: ['activities-panel', { magazineId, issueId, packId, limit }],
    queryFn: () =>
      listActivities({
        magazineId,
        issueId,
        packId,
        limit,
        // status omis → renvoie « en cours + terminées récentes »
      }),
    refetchInterval: 5000,
    refetchIntervalInBackground: false,
  })

  const items: Activity[] = q.data ?? []

  const contextLabel = packId ? 'ce pack' : 'ce magazine'

  return (
    <div className="rounded border border-zinc-800 bg-zinc-900/40 p-3">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs uppercase tracking-wide text-zinc-500">
          Activités récentes
        </span>
        <Link
          to="/activity"
          className="text-xs text-violet-400 hover:text-violet-300"
        >
          Tout voir →
        </Link>
      </div>
      {q.isLoading ? (
        <div className="flex items-center gap-2 text-xs text-zinc-500 py-4 justify-center">
          <Loader2 className="size-3 animate-spin" />
          Chargement…
        </div>
      ) : items.length === 0 ? (
        <p className="text-xs text-zinc-500 italic py-2">
          Aucune activité récente pour {contextLabel}.
        </p>
      ) : (
        <ul className="divide-y divide-zinc-800/60">
          {items.map((a) => (
            <ActivityLine key={a.id} act={a} />
          ))}
        </ul>
      )}
    </div>
  )
}

function ActivityLine({ act }: { act: Activity }) {
  const isRunning = act.status === 'queued' || act.status === 'running'
  const isFailed = act.status === 'failed' || act.status === 'cancelled'
  const Icon = isFailed ? AlertCircle : isRunning ? Loader2 : Check
  const iconClass = isFailed
    ? 'text-red-400'
    : isRunning
      ? 'text-violet-300 animate-spin'
      : 'text-emerald-400'
  return (
    <li className="py-1.5 flex items-start gap-2">
      <Icon className={'size-3.5 mt-0.5 shrink-0 ' + iconClass} />
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline gap-1.5 flex-wrap">
          <span className="text-[10px] uppercase text-zinc-500 font-mono">
            {KIND_LABEL[act.kind] ?? act.kind}
          </span>
          <span className="text-xs text-zinc-100 truncate">{act.title}</span>
        </div>
        {act.statusMessage && (
          <div className="text-[11px] text-zinc-400 truncate mt-0.5">
            {act.statusMessage}
          </div>
        )}
      </div>
      {isRunning && (
        <span className="text-[10px] text-zinc-500 shrink-0 mt-0.5">
          {act.progress.toFixed(0)}%
        </span>
      )}
    </li>
  )
}
