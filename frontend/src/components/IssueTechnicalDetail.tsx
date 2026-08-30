/**
 * Fiche technique d'une issue — timeline workflow.
 *
 * Fetch history events + issue detail (file source) et rend chronologie
 * complète : création → recherche(s) → grab → download (client) →
 * import → complet. Chaque étape affiche timestamp, type, liens
 * (torrent/pack), status, données spécifiques.
 *
 * Utilisé dans le tab "Fiche technique" du modal Edit Issue.
 */
import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Calendar,
  Search,
  Download,
  Package,
  Import as ImportIcon,
  Sparkles,
  ShieldAlert,
  Check,
  AlertCircle,
  Loader2,
  ExternalLink,
  FileText,
  Clock,
} from 'lucide-react'

import { getHistory, type HistoryEntry } from '@/api/history'
import { getIssue, type Issue } from '@/api/issues'
import { Badge } from '@/components/ui/badge'

interface Props {
  issueId: number | null
}

// ─── Timeline event mapper ────────────────────────────────────────────

interface TimelineStep {
  at: string
  icon: typeof Calendar
  iconColor: string
  title: string
  subtitle?: string
  details?: React.ReactNode
  raw?: HistoryEntry
}

function formatDate(iso: string | null): string {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString('fr-FR', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return iso
  }
}

function formatBytes(bytes: number | null | undefined): string {
  if (!bytes) return '—'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`
  return `${(bytes / 1024 / 1024 / 1024).toFixed(2)} GB`
}

function eventToStep(e: HistoryEntry): TimelineStep {
  const d = (e.data ?? {}) as Record<string, unknown>
  const at = e.date
  switch (e.eventType) {
    case 'searched': {
      const w = d.winner as { title?: string; confidence?: number } | null | undefined
      const totals = d.totals as { raw?: number; after_date_match?: number } | undefined
      const ag = d.auto_grab as { attempted?: boolean; success?: boolean | null; message?: string | null } | undefined
      return {
        at, icon: Search, iconColor: 'text-blue-400',
        title: 'Recherche wanted',
        subtitle: (d.query as string) ?? undefined,
        details: (
          <div className="space-y-1 text-xs">
            <div className="text-zinc-400">
              {totals?.raw ?? '?'} candidats bruts · {totals?.after_date_match ?? '?'} après filtre date
            </div>
            {w ? (
              <div className="rounded border border-purple-500/30 bg-purple-500/5 p-2">
                <div className="text-purple-300 font-medium">Winner ({w.confidence?.toFixed(1)}%)</div>
                <div className="text-zinc-200 break-all">{w.title}</div>
              </div>
            ) : (
              <div className="text-zinc-500 italic">Aucun winner</div>
            )}
            {ag?.attempted && (
              <div className={ag.success ? 'text-emerald-400' : 'text-red-400'}>
                Auto-grab : {ag.success ? '✓ envoyé' : `✕ ${ag.message ?? 'échec'}`}
              </div>
            )}
          </div>
        ),
        raw: e,
      }
    }
    case 'ai_ranker': {
      const conf = d.confidence as number | null | undefined
      const pick = d.ai_picked_index as number | null | undefined
      const mode = d.applied_mode as string | undefined
      return {
        at, icon: Sparkles, iconColor: 'text-purple-400',
        title: 'IA ranker',
        subtitle: `${mode ?? '?'} · pick=${pick ?? 'refusé'} · conf=${conf ? (conf * 100).toFixed(0) + '%' : '?'}`,
        details: d.reason ? (
          <div className="text-xs text-zinc-400 italic">{String(d.reason)}</div>
        ) : undefined,
        raw: e,
      }
    }
    case 'grab': {
      const title = d.release_title as string | undefined
      const proto = d.protocol as string | undefined
      const client = d.download_client as string | undefined
      const url = d.download_url as string | undefined
      return {
        at, icon: Download, iconColor: 'text-amber-400',
        title: 'Grab envoyé',
        subtitle: `${proto ?? '?'} → ${client ?? '?'}`,
        details: (
          <div className="space-y-1 text-xs">
            {title && <div className="text-zinc-200 break-all">{title}</div>}
            {url && (
              <a href={url} target="_blank" rel="noreferrer"
                 className="inline-flex items-center gap-1 text-blue-400 hover:text-blue-300 break-all">
                <ExternalLink className="size-3 shrink-0" />
                <span className="truncate max-w-xs">{url}</span>
              </a>
            )}
            {d.match_score != null && (
              <div className="text-zinc-400">Score : {String(d.match_score)}%</div>
            )}
          </div>
        ),
        raw: e,
      }
    }
    case 'download_completed': {
      return {
        at, icon: Download, iconColor: 'text-emerald-400',
        title: 'Download terminé',
        subtitle: (d.download_id as string) ?? undefined,
        raw: e,
      }
    }
    case 'import': {
      const path = d.imported_to as string | undefined
      return {
        at, icon: ImportIcon, iconColor: 'text-emerald-400',
        title: 'Import réussi',
        subtitle: e.details ?? undefined,
        details: path ? (
          <div className="text-xs text-zinc-400 break-all font-mono">{path}</div>
        ) : undefined,
        raw: e,
      }
    }
    case 'ai_enrichment': {
      const status = d.status as string | undefined
      const steps = (d.steps as unknown[] | undefined)?.length ?? 0
      const elapsed = d.total_elapsed_ms as number | undefined
      return {
        at, icon: Sparkles, iconColor: 'text-purple-400',
        title: 'Enrichissement IA',
        subtitle: `${status ?? '?'} · ${steps} étapes · ${elapsed ? (elapsed / 1000).toFixed(1) + 's' : '?'}`,
        raw: e,
      }
    }
    case 'error': {
      return {
        at, icon: AlertCircle, iconColor: 'text-red-400',
        title: 'Erreur',
        subtitle: e.details ?? undefined,
        raw: e,
      }
    }
    default:
      return {
        at, icon: Clock, iconColor: 'text-zinc-500',
        title: e.eventType,
        subtitle: e.details ?? undefined,
        raw: e,
      }
  }
}

// ─── Component ────────────────────────────────────────────────────────

export function IssueTechnicalDetail({ issueId }: Props) {
  const issueQ = useQuery({
    queryKey: ['issue', issueId],
    queryFn: () => getIssue(issueId!),
    enabled: issueId != null,
  })

  const histQ = useQuery({
    queryKey: ['history', 'issue', issueId],
    queryFn: () => getHistory({ issueId: issueId!, pageSize: 100 }),
    enabled: issueId != null,
  })

  const timeline = useMemo(() => {
    const events = histQ.data?.records ?? []
    const steps = events.map(eventToStep)
    // Ordre chronologique croissant (plus vieux en haut)
    steps.sort((a, b) => new Date(a.at).getTime() - new Date(b.at).getTime())
    return steps
  }, [histQ.data])

  if (issueId == null) return null

  const issue = issueQ.data as Issue | undefined
  const file = issue?.file

  return (
    <div className="space-y-4 max-h-[65vh] overflow-y-auto pr-1">
      {/* Résumé issue */}
      <div className="rounded border border-zinc-800 bg-zinc-900/40 p-3 space-y-1.5">
        <div className="flex items-center gap-2">
          <FileText className="size-4 text-zinc-400" />
          <span className="text-sm text-zinc-200 font-medium">Issue</span>
          {issue?.status && (
            <Badge variant="outline" className="text-xs">{issue.status}</Badge>
          )}
        </div>
        <div className="grid grid-cols-2 gap-2 text-xs">
          <KV label="Numéro" value={issue?.number != null ? `#${issue.number}` : '—'} />
          <KV label="Date" value={issue?.publicationDate ?? '—'} />
          <KV label="Créé" value={formatDate(issue?.addedAt ?? null)} />
          <KV label="Dernier scan" value={formatDate(issue?.lastSearchedAt ?? null)} />
        </div>
      </div>

      {/* Fichier source si présent */}
      {file && (
        <div className="rounded border border-zinc-800 bg-zinc-900/40 p-3 space-y-1.5">
          <div className="flex items-center gap-2">
            {file.sourceType === 'pack' ? (
              <Package className="size-4 text-purple-400" />
            ) : (
              <Download className="size-4 text-amber-400" />
            )}
            <span className="text-sm text-zinc-200 font-medium">
              Fichier source
            </span>
            <Badge variant="outline" className="text-xs">
              {file.sourceType ?? 'torrent'}
            </Badge>
          </div>
          <div className="grid grid-cols-2 gap-2 text-xs">
            <KV label="Importé le" value={formatDate(file.importedAt)} />
            <KV label="Taille" value={formatBytes(file.size)} />
            <KV label="Qualité" value={file.quality} />
            <KV label="Format" value={file.format} />
          </div>
          {file.originalFilename && (
            <div className="text-xs">
              <span className="text-zinc-500">Nom original : </span>
              <span className="text-zinc-300 font-mono break-all">
                {file.originalFilename}
              </span>
            </div>
          )}
          {file.sourceType === 'pack' && file.sourcePackName && (
            <div className="text-xs">
              <span className="text-zinc-500">Pack : </span>
              <span className="text-purple-300">{file.sourcePackName}</span>
            </div>
          )}
          {file.sourceReleaseTitle && (
            <div className="text-xs">
              <span className="text-zinc-500">Release : </span>
              <span className="text-zinc-300 break-all">
                {file.sourceReleaseTitle}
              </span>
            </div>
          )}
          {file.relativePath && (
            <div className="text-xs">
              <span className="text-zinc-500">Chemin : </span>
              <span className="text-zinc-400 font-mono break-all">
                {file.relativePath}
              </span>
            </div>
          )}
        </div>
      )}

      {/* Timeline workflow */}
      <div>
        <div className="text-xs uppercase tracking-wide text-zinc-500 mb-2">
          Timeline workflow ({timeline.length})
        </div>
        {histQ.isLoading ? (
          <div className="flex items-center gap-2 text-zinc-500 text-sm py-6 justify-center">
            <Loader2 className="size-4 animate-spin" />
            Chargement de l'historique…
          </div>
        ) : timeline.length === 0 ? (
          <div className="rounded border border-dashed border-zinc-800 py-6 text-center text-xs text-zinc-500">
            Aucun événement — l'issue n'a encore rien déclenché.
          </div>
        ) : (
          <div className="relative pl-6 space-y-3">
            <div className="absolute left-2 top-2 bottom-2 w-px bg-zinc-800" />
            {timeline.map((s, i) => {
              const Icon = s.icon
              return (
                <div key={i} className="relative">
                  <div className="absolute -left-6 top-0.5 w-4 h-4 rounded-full bg-zinc-950 border border-zinc-700 flex items-center justify-center">
                    <Icon className={`size-2.5 ${s.iconColor}`} />
                  </div>
                  <div className="text-[10px] text-zinc-500 tabular-nums">
                    {formatDate(s.at)}
                  </div>
                  <div className="text-sm text-zinc-200 font-medium">{s.title}</div>
                  {s.subtitle && (
                    <div className="text-xs text-zinc-400 break-all">{s.subtitle}</div>
                  )}
                  {s.details && <div className="mt-1">{s.details}</div>}
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* Avertissement si status wanted sans event */}
      {issue?.status === 'wanted' && timeline.length === 0 && (
        <div className="rounded border border-amber-500/30 bg-amber-500/5 p-3 text-xs text-amber-200 flex items-start gap-2">
          <ShieldAlert className="size-4 shrink-0 mt-0.5" />
          <div>
            L'issue est <strong>wanted</strong> mais aucune recherche n'a
            été loggée. Clique le bouton <strong>Recherche</strong> (⭐)
            sur la row pour lancer un cycle manuel, ou attends le prochain
            passage du scheduler (~4h par défaut).
          </div>
        </div>
      )}
    </div>
  )
}

function KV({ label, value }: { label: string; value: string | number | null | undefined }) {
  return (
    <div className="flex items-baseline gap-2">
      <span className="text-zinc-500 shrink-0">{label} :</span>
      <span className="text-zinc-200 truncate">
        {value == null || value === '' ? '—' : String(value)}
      </span>
    </div>
  )
}
