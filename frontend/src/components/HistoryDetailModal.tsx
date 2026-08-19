import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import type { HistoryEntry } from '@/api/history'
import { WantedSearchDetail, type WantedSearchCandidate } from '@/components/WantedSearchDetail'
import { Badge } from '@/components/ui/badge'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'

function eventVariant(eventType: string): 'default' | 'secondary' | 'destructive' | 'outline' {
  switch (eventType) {
    case 'grab':
      return 'default'
    case 'download_completed':
    case 'import':
    case 'upgrade':
      return 'secondary'
    case 'error':
    case 'unmatched':
      return 'destructive'
    default:
      return 'outline'
  }
}

interface DetailRowProps {
  label: string
  value: string | number | null | undefined
}

function DetailRow({ label, value }: DetailRowProps) {
  if (value === null || value === undefined || value === '') return null
  return (
    <div className="flex items-start gap-3 py-1.5">
      <span className="text-zinc-500 text-sm min-w-[140px] shrink-0">{label}</span>
      <span className="text-zinc-200 text-sm break-all">{String(value)}</span>
    </div>
  )
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1073741824) return `${(bytes / 1048576).toFixed(1)} MB`
  return `${(bytes / 1073741824).toFixed(2)} GB`
}

interface SearchResult {
  title: string
  indexer: string
  size: number
  seeders: number | null
  quality: string
  language: string
  protocol: string
  score: number
  age: number
}

interface GrabbedItem {
  release_title: string
  magazine_title: string
  issue_number: number | null
  score: number
  matched_via: string
  indexer: string
}

interface IssueDetail {
  issue_id: number
  issue_number: number | null
  result_count: number
  best_result?: string
  best_score?: number
}

// Types WantedSearchCandidate / WantedSearchWinner définis dans
// ./WantedSearchDetail.tsx et importés en haut du fichier.

interface HistoryDetailModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  entry: HistoryEntry | null
}

export function HistoryDetailModal({ open, onOpenChange, entry }: HistoryDetailModalProps) {
  const { t } = useTranslation()

  if (!entry) return null

  const data = entry.data as Record<string, unknown> | null

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl bg-zinc-950 border-zinc-800 max-h-[80vh] flex flex-col overflow-hidden">
        <DialogHeader>
          <DialogTitle className="text-zinc-100 flex items-center gap-3">
            <Badge variant={eventVariant(entry.eventType)}>
              {t(`history.event_${entry.eventType}`, entry.eventType)}
            </Badge>
            <span className="text-sm text-zinc-400 font-normal">
              {new Date(entry.date).toLocaleString()}
            </span>
          </DialogTitle>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto space-y-4">
          {/* Common fields */}
          <div className="space-y-0">
            {entry.magazineTitle && (
              <DetailRow label={t('historyDetail.magazine')} value={entry.magazineTitle} />
            )}
            {entry.issueNumber !== null && (
              <DetailRow label={t('historyDetail.issue')} value={`#${entry.issueNumber}`} />
            )}
            {entry.issueDate && (
              <DetailRow
                label={t('historyDetail.issueDate')}
                value={new Date(entry.issueDate + 'T00:00:00').toLocaleDateString()}
              />
            )}
          </div>

          {/* Event-specific details from structured data */}
          {data && (
            <div className="border-t border-zinc-800/50 pt-3">
              {renderEventDetails(entry.eventType, data, t)}
            </div>
          )}

          {/* Fallback: parse details text for older events without structured data */}
          {!data && entry.details && (
            <div className="border-t border-zinc-800/50 pt-3">
              {renderFallbackDetails(entry.eventType, entry.details, t)}
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function renderEventDetails(
  eventType: string,
  data: Record<string, unknown>,
  t: any,
) {
  switch (eventType) {
    case 'grab':
      return (
        <div className="space-y-0">
          <DetailRow label={t('historyDetail.releaseTitle')} value={data.release_title as string} />
          <DetailRow label={t('historyDetail.magazine')} value={data.magazine_title as string} />
          <DetailRow label={t('historyDetail.issue')} value={data.issue_number != null ? `#${data.issue_number}` : undefined} />
          {data.match_score != null && (
            <div className="flex items-start gap-3 py-1.5">
              <span className="text-zinc-500 text-sm min-w-[140px] shrink-0">{t('historyDetail.matchScore')}</span>
              <span className={`text-sm font-mono font-medium ${
                (data.match_score as number) >= 90 ? 'text-green-400' :
                (data.match_score as number) >= 75 ? 'text-yellow-400' :
                'text-red-400'
              }`}>
                {data.match_score as number}
              </span>
            </div>
          )}
          <DetailRow label={t('historyDetail.matchDetails')} value={data.match_details as string} />
          <DetailRow label={t('historyDetail.protocol')} value={data.protocol as string} />
          <DetailRow label={t('historyDetail.downloadClient')} value={data.download_client as string} />
          <DetailRow label={t('historyDetail.source')} value={data.source as string} />
          <DetailRow label={t('historyDetail.downloadId')} value={data.download_id as string} />
          <DetailRow label={t('historyDetail.guid')} value={data.guid as string} />
        </div>
      )

    case 'searched':
      return (
        <div className="space-y-3">
          <div className="space-y-0">
            <DetailRow label={t('historyDetail.searchType')} value={formatSearchType(data.search_type as string, t)} />
            <DetailRow label={t('historyDetail.query')} value={data.query as string} />
            <DetailRow label={t('historyDetail.resultCount')} value={data.result_count as number} />
            {Array.isArray(data.indexers) && (
              <DetailRow label={t('historyDetail.indexers')} value={(data.indexers as string[]).join(', ')} />
            )}
            {data.wanted_count !== undefined && (
              <DetailRow label={t('historyDetail.wantedCount')} value={data.wanted_count as number} />
            )}
            {data.issues_with_results !== undefined && (
              <DetailRow label={t('historyDetail.issuesWithResults')} value={data.issues_with_results as number} />
            )}
            {data.items_scanned !== undefined && (
              <DetailRow label={t('historyDetail.itemsScanned')} value={data.items_scanned as number} />
            )}
            {data.grabbed_count !== undefined && (
              <DetailRow label={t('historyDetail.grabbedCount')} value={data.grabbed_count as number} />
            )}
            {/* RSS skip breakdown — only show counters > 0 so a clean
                run stays uncluttered. Together they explain "why 0
                grabbed?" instead of leaving the user guessing. */}
            {typeof data.unmatched_count === 'number' && data.unmatched_count > 0 && (
              <DetailRow label={t('historyDetail.unmatchedCount')} value={data.unmatched_count} />
            )}
            {typeof data.no_url_count === 'number' && data.no_url_count > 0 && (
              <DetailRow label={t('historyDetail.noUrlCount')} value={data.no_url_count} />
            )}
            {typeof data.blocklisted_count === 'number' && data.blocklisted_count > 0 && (
              <DetailRow label={t('historyDetail.blocklistedCount')} value={data.blocklisted_count} />
            )}
            {typeof data.grab_failed_count === 'number' && data.grab_failed_count > 0 && (
              <DetailRow label={t('historyDetail.grabFailedCount')} value={data.grab_failed_count} />
            )}
          </div>

          {/* Per-indexer / per-item errors — surfaced for RSS sync
              runs where one or more indexers failed or a grab raised. */}
          {Array.isArray(data.errors) && (data.errors as Array<{indexer: string; stage: string; title?: string; error: string}>).length > 0 && (
            <div>
              <h4 className="text-xs font-medium text-red-400 uppercase tracking-wide mb-2">
                {t('historyDetail.errors')}
              </h4>
              <div className="rounded border border-red-900/50 overflow-hidden">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="bg-red-950/30 text-red-400">
                      <th className="text-left px-2 py-1.5 font-medium">{t('historyDetail.indexer')}</th>
                      <th className="text-left px-2 py-1.5 font-medium">{t('historyDetail.stage')}</th>
                      <th className="text-left px-2 py-1.5 font-medium">{t('historyDetail.releaseTitle')}</th>
                      <th className="text-left px-2 py-1.5 font-medium">{t('historyDetail.error')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(data.errors as Array<{indexer: string; stage: string; title?: string; error: string}>).map((e, i) => (
                      <tr key={i} className="border-t border-red-900/30 hover:bg-red-950/20">
                        <td className="px-2 py-1.5 text-zinc-200">{e.indexer}</td>
                        <td className="px-2 py-1.5 text-zinc-400">{e.stage}</td>
                        <td className="px-2 py-1.5 text-zinc-400 max-w-[180px] truncate" title={e.title}>{e.title ?? '-'}</td>
                        <td className="px-2 py-1.5 text-red-300 max-w-[260px] truncate" title={e.error}>{e.error}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Sample of un-grabbed items so the user can sanity-check
              why their RSS feed isn't translating to grabs. */}
          {Array.isArray(data.skipped_samples) && (data.skipped_samples as Array<{title: string; reason: string; indexer?: string; magazine?: string}>).length > 0 && (
            <div>
              <h4 className="text-xs font-medium text-zinc-400 uppercase tracking-wide mb-2">
                {t('historyDetail.skippedSamples')}
              </h4>
              <div className="rounded border border-zinc-800 overflow-hidden">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="bg-zinc-900/50 text-zinc-500">
                      <th className="text-left px-2 py-1.5 font-medium">{t('historyDetail.releaseTitle')}</th>
                      <th className="text-left px-2 py-1.5 font-medium">{t('historyDetail.indexer')}</th>
                      <th className="text-left px-2 py-1.5 font-medium">{t('historyDetail.reason')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(data.skipped_samples as Array<{title: string; reason: string; indexer?: string; magazine?: string}>).map((s, i) => (
                      <tr key={i} className="border-t border-zinc-800/50 hover:bg-zinc-900/30">
                        <td className="px-2 py-1.5 text-zinc-200 max-w-[260px] truncate" title={s.title}>{s.title}</td>
                        <td className="px-2 py-1.5 text-zinc-400">{s.indexer ?? '-'}</td>
                        <td className="px-2 py-1.5 text-zinc-400">{t(`historyDetail.skipReason_${s.reason}`, s.reason)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Wanted-search pipeline breakdown (nouveau pipeline).
              Rendu uniquement quand data.candidates est présent —
              les anciens events n'ont que top_results et retombent
              sur le bloc legacy plus bas. */}
          {Array.isArray(data.candidates) && (data.candidates as WantedSearchCandidate[]).length > 0 && (
            <WantedSearchDetail data={data} />
          )}

          {/* Top search results table (legacy — pre-Phase 1 events) */}
          {!Array.isArray(data.candidates) && Array.isArray(data.top_results) && (data.top_results as SearchResult[]).length > 0 && (
            <div>
              <h4 className="text-xs font-medium text-zinc-400 uppercase tracking-wide mb-2">
                {t('historyDetail.topResults')}
              </h4>
              <div className="rounded border border-zinc-800 overflow-hidden">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="bg-zinc-900/50 text-zinc-500">
                      <th className="text-left px-2 py-1.5 font-medium">{t('historyDetail.releaseTitle')}</th>
                      <th className="text-left px-2 py-1.5 font-medium">{t('historyDetail.indexer')}</th>
                      <th className="text-right px-2 py-1.5 font-medium">{t('historyDetail.size')}</th>
                      <th className="text-right px-2 py-1.5 font-medium">{t('historyDetail.seeders')}</th>
                      <th className="text-left px-2 py-1.5 font-medium">{t('historyDetail.quality')}</th>
                      <th className="text-right px-2 py-1.5 font-medium">{t('historyDetail.score')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(data.top_results as SearchResult[]).map((r, i) => (
                      <tr key={i} className="border-t border-zinc-800/50 hover:bg-zinc-900/30">
                        <td className="px-2 py-1.5 text-zinc-200 max-w-[200px] truncate" title={r.title}>{r.title}</td>
                        <td className="px-2 py-1.5 text-zinc-400">{r.indexer}</td>
                        <td className="px-2 py-1.5 text-zinc-400 text-right">{formatSize(r.size)}</td>
                        <td className="px-2 py-1.5 text-zinc-400 text-right">{r.seeders ?? '-'}</td>
                        <td className="px-2 py-1.5 text-zinc-400">{r.quality}</td>
                        <td className="px-2 py-1.5 text-zinc-300 text-right font-mono">{r.score}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* RSS grabbed items table */}
          {Array.isArray(data.grabbed_items) && (data.grabbed_items as GrabbedItem[]).length > 0 && (
            <div>
              <h4 className="text-xs font-medium text-zinc-400 uppercase tracking-wide mb-2">
                {t('historyDetail.grabbedItems')}
              </h4>
              <div className="rounded border border-zinc-800 overflow-hidden">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="bg-zinc-900/50 text-zinc-500">
                      <th className="text-left px-2 py-1.5 font-medium">{t('historyDetail.releaseTitle')}</th>
                      <th className="text-left px-2 py-1.5 font-medium">{t('historyDetail.magazine')}</th>
                      <th className="text-left px-2 py-1.5 font-medium">{t('historyDetail.issue')}</th>
                      <th className="text-left px-2 py-1.5 font-medium">{t('historyDetail.indexer')}</th>
                      <th className="text-right px-2 py-1.5 font-medium">{t('historyDetail.score')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(data.grabbed_items as GrabbedItem[]).map((item, i) => (
                      <tr key={i} className="border-t border-zinc-800/50 hover:bg-zinc-900/30">
                        <td className="px-2 py-1.5 text-zinc-200 max-w-[200px] truncate" title={item.release_title}>{item.release_title}</td>
                        <td className="px-2 py-1.5 text-zinc-400">{item.magazine_title}</td>
                        <td className="px-2 py-1.5 text-zinc-400">{item.issue_number != null ? `#${item.issue_number}` : '-'}</td>
                        <td className="px-2 py-1.5 text-zinc-400">{item.indexer}</td>
                        <td className="px-2 py-1.5 text-zinc-300 text-right font-mono">{item.score}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Missing issues detail */}
          {Array.isArray(data.issues_detail) && (data.issues_detail as IssueDetail[]).length > 0 && (
            <div>
              <h4 className="text-xs font-medium text-zinc-400 uppercase tracking-wide mb-2">
                {t('historyDetail.issuesSearched')}
              </h4>
              <div className="rounded border border-zinc-800 overflow-hidden">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="bg-zinc-900/50 text-zinc-500">
                      <th className="text-left px-2 py-1.5 font-medium">{t('historyDetail.issue')}</th>
                      <th className="text-right px-2 py-1.5 font-medium">{t('historyDetail.resultCount')}</th>
                      <th className="text-left px-2 py-1.5 font-medium">{t('historyDetail.bestResult')}</th>
                      <th className="text-right px-2 py-1.5 font-medium">{t('historyDetail.score')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(data.issues_detail as IssueDetail[]).map((iss, i) => (
                      <tr key={i} className="border-t border-zinc-800/50 hover:bg-zinc-900/30">
                        <td className="px-2 py-1.5 text-zinc-200">{iss.issue_number != null ? `#${iss.issue_number}` : `ID ${iss.issue_id}`}</td>
                        <td className="px-2 py-1.5 text-zinc-400 text-right">{iss.result_count}</td>
                        <td className="px-2 py-1.5 text-zinc-400 max-w-[250px] truncate" title={iss.best_result}>{iss.best_result || '-'}</td>
                        <td className="px-2 py-1.5 text-zinc-300 text-right font-mono">{iss.best_score ?? '-'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )

    case 'download_completed':
      return (
        <div className="space-y-0">
          <DetailRow label={t('historyDetail.source')} value={data.source as string} />
          <DetailRow label={t('historyDetail.filename')} value={data.filename as string} />
          <DetailRow label={t('historyDetail.identifier')} value={data.identifier as string} />
          <DetailRow label={t('historyDetail.md5')} value={data.md5 as string} />
          <DetailRow label={t('historyDetail.downloadId')} value={data.download_id as string} />
          <DetailRow label={t('historyDetail.downloadPath')} value={data.download_path as string} />
        </div>
      )

    case 'import':
    case 'upgrade':
      return (
        <div className="space-y-0">
          <DetailRow label={t('historyDetail.filename')} value={data.filename as string} />
          <DetailRow label={t('historyDetail.quality')} value={data.quality as string} />
          <DetailRow label={t('historyDetail.format')} value={data.format as string} />
          <DetailRow label={t('historyDetail.releaseGroup')} value={data.release_group as string} />
          <DetailRow label={t('historyDetail.sourcePath')} value={data.source_path as string} />
          <DetailRow label={t('historyDetail.destPath')} value={data.dest_path as string} />
          <DetailRow label={t('historyDetail.importMode')} value={data.import_mode as string} />
        </div>
      )

    case 'unmatched':
      return (
        <div className="space-y-0">
          <DetailRow label={t('historyDetail.filename')} value={data.filename as string} />
          <DetailRow label={t('historyDetail.parsedTitle')} value={data.parsed_title as string} />
          <DetailRow label={t('historyDetail.sourcePath')} value={data.source_path as string} />
        </div>
      )

    case 'error':
      return (
        <div className="space-y-0">
          <DetailRow label={t('historyDetail.error')} value={data.error as string} />
          <DetailRow label={t('historyDetail.source')} value={data.source as string} />
          <DetailRow label={t('historyDetail.filename')} value={data.filename as string} />
          <DetailRow label={t('historyDetail.md5')} value={data.md5 as string} />
          <DetailRow label={t('historyDetail.sourcePath')} value={data.source_path as string} />
          <DetailRow label={t('historyDetail.downloadPath')} value={data.download_path as string} />
          <DetailRow label={t('historyDetail.downloadId')} value={data.download_id as string} />
        </div>
      )

    case 'ai_enrichment':
      return <AIEnrichmentDetail data={data} />

    case 'ai_ranker':
      return <AIRankerDetail data={data} />

    default:
      // Generic: show all data keys ; for nested dicts/arrays, dump
      // as pretty JSON so the user at least SEES the payload instead
      // of « [object Object] ».
      return (
        <div className="space-y-0">
          {Object.entries(data).map(([key, value]) => (
            <DetailRow
              key={key}
              label={key.replace(/_/g, ' ')}
              value={
                value == null
                  ? null
                  : typeof value === 'object'
                    ? JSON.stringify(value, null, 2)
                    : String(value)
              }
            />
          ))}
        </div>
      )
  }
}

// ---------------------------------------------------------------------------
// AI-specific detail renderers — les events ai_enrichment / ai_ranker portent
// des payloads riches (steps, models, timings) qui méritent un rendu dédié.
// ---------------------------------------------------------------------------

interface AIStep {
  step: string
  model?: string
  page?: number | string | null
  zone?: string | null
  tag?: string | null
  engine?: string | null
  input?: Record<string, unknown> | null
  params?: Record<string, unknown> | null
  output?: Record<string, unknown> | string | null
  error?: string | null
  elapsed_ms?: number
  leak_dropped?: boolean
}

function fmtMs(ms?: number | null): string {
  if (ms == null) return '?'
  if (ms < 1000) return `${ms} ms`
  return `${(ms / 1000).toFixed(1)} s`
}

const STEP_KIND_COLOR: Record<string, string> = {
  text: 'bg-blue-950 text-blue-300 border-blue-800',
  vision: 'bg-purple-950 text-purple-300 border-purple-800',
  python_ocr: 'bg-emerald-950 text-emerald-300 border-emerald-800',
  arbiter: 'bg-amber-950 text-amber-300 border-amber-800',
  arbiter_postvalidate: 'bg-orange-950 text-orange-300 border-orange-800',
  switch: 'bg-zinc-800 text-zinc-400 border-zinc-700',
  cache: 'bg-cyan-950 text-cyan-300 border-cyan-800',
  skip: 'bg-zinc-800 text-zinc-400 border-zinc-700',
}

/** Rendu riche d'une step ai_run — inputs / params / output
 *  déplié progressivement. Chaque bloc est optionnel selon ce que
 *  la step porte. */
function AIStepCard({ step: s }: { step: AIStep }) {
  const [expanded, setExpanded] = useState(false)
  const color = STEP_KIND_COLOR[s.step] ?? 'bg-zinc-800 text-zinc-300 border-zinc-700'

  const hasInput = s.input && Object.keys(s.input).length > 0
  const hasParams = s.params && Object.keys(s.params).length > 0
  const canExpand = hasInput || hasParams
  const outputPreview = renderOutputPreview(s.output)

  return (
    <div className="rounded border border-zinc-800 bg-zinc-900/40 p-3">
      <div className="flex items-center flex-wrap gap-2 mb-2">
        <span className={'text-xs px-2 py-0.5 rounded border font-mono ' + color}>
          {s.step}
        </span>
        {s.model && (
          <span className="text-xs text-zinc-400 font-mono">{s.model}</span>
        )}
        {s.engine && (
          <span className="text-xs text-zinc-400 font-mono">
            engine:{s.engine}
          </span>
        )}
        {s.page != null && s.page !== '' && (
          <span className="text-xs text-zinc-500">page {s.page}</span>
        )}
        {s.zone && (
          <span className="text-xs text-zinc-500">zone: {s.zone}</span>
        )}
        {s.tag && (
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-900/40 text-emerald-300">
            tag:{s.tag}
          </span>
        )}
        {s.leak_dropped && (
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-red-900/40 text-red-300">
            leak dropped
          </span>
        )}
        <span className="ml-auto text-xs text-zinc-500">
          {fmtMs(s.elapsed_ms)}
        </span>
      </div>

      {s.error && (
        <div className="text-xs text-rose-300 mb-2 break-words">
          <span className="text-zinc-500">Erreur : </span>
          {s.error}
        </div>
      )}

      {/* Output — bloc principal, toujours visible */}
      {outputPreview !== null && (
        <div>
          <div className="text-[10px] uppercase tracking-wide text-zinc-500 mb-1">
            Sortie
          </div>
          <pre className="text-xs bg-zinc-950 border border-zinc-800 rounded p-2 overflow-x-auto text-zinc-300 whitespace-pre-wrap break-words">
            {outputPreview}
          </pre>
        </div>
      )}

      {/* Input + Params — pliés par défaut, dépliage à la demande */}
      {canExpand && (
        <div className="mt-2 border-t border-zinc-800 pt-2">
          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            className="text-[10px] text-zinc-500 hover:text-zinc-300 uppercase tracking-wide"
          >
            {expanded ? '▾' : '▸'} Détails technique (entrées + paramètres)
          </button>
          {expanded && (
            <div className="mt-2 grid gap-2 md:grid-cols-2">
              {hasInput && (
                <div>
                  <div className="text-[10px] uppercase text-zinc-500 mb-1">
                    Entrées
                  </div>
                  <pre className="text-[10px] bg-zinc-950 border border-zinc-800 rounded p-2 overflow-x-auto text-zinc-400 whitespace-pre-wrap break-words">
                    {JSON.stringify(s.input, null, 2)}
                  </pre>
                </div>
              )}
              {hasParams && (
                <div>
                  <div className="text-[10px] uppercase text-zinc-500 mb-1">
                    Paramètres
                  </div>
                  <pre className="text-[10px] bg-zinc-950 border border-zinc-800 rounded p-2 overflow-x-auto text-zinc-400 whitespace-pre-wrap break-words">
                    {JSON.stringify(s.params, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function renderOutputPreview(
  out: AIStep['output'],
): string | null {
  if (out == null) return null
  if (typeof out === 'string') {
    return out.length > 0 ? out.slice(0, 2000) : null
  }
  if (typeof out === 'object') {
    try {
      return JSON.stringify(out, null, 2)
    } catch {
      return String(out)
    }
  }
  return String(out)
}

function StatusPill({ status }: { status: string }) {
  const colors: Record<string, string> = {
    success: 'bg-emerald-950 text-emerald-300 border-emerald-800',
    skipped: 'bg-amber-950 text-amber-300 border-amber-800',
    failed: 'bg-rose-950 text-rose-300 border-rose-800',
    running: 'bg-blue-950 text-blue-300 border-blue-800',
  }
  const cls = colors[status] ?? 'bg-zinc-900 text-zinc-300 border-zinc-700'
  return (
    <span className={`text-xs px-2 py-0.5 rounded border ${cls}`}>
      {status}
    </span>
  )
}

function KV({
  label,
  children,
}: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-start gap-3 py-1">
      <span className="text-zinc-500 text-xs uppercase tracking-wide min-w-[110px] shrink-0">
        {label}
      </span>
      <span className="text-zinc-200 text-sm break-all flex-1">{children}</span>
    </div>
  )
}

function AIEnrichmentDetail({ data }: { data: Record<string, unknown> }) {
  const steps = (data.steps as AIStep[] | undefined) ?? []
  const final = (data.final as Record<string, unknown> | undefined) ?? {}
  const runId = data.run_id as number | undefined
  const trigger = data.trigger as string | undefined
  const status = (data.status as string | undefined) ?? 'success'
  const mode = data.applied_mode as string | undefined
  const totalMs = data.total_elapsed_ms as number | undefined
  const err = data.error_message as string | undefined

  return (
    <div className="space-y-4">
      {/* Résumé */}
      <div className="rounded border border-zinc-800 bg-zinc-900/40 p-3 space-y-1">
        <div className="flex items-center gap-2 mb-2">
          <span className="text-sm text-zinc-300 font-medium">
            Run #{runId ?? '?'}
          </span>
          <StatusPill status={status} />
          {mode && (
            <span className="text-xs text-zinc-500 px-2 py-0.5 rounded bg-zinc-800">
              mode: {mode}
            </span>
          )}
          {trigger && (
            <span className="text-xs text-zinc-500 px-2 py-0.5 rounded bg-zinc-800">
              {trigger}
            </span>
          )}
        </div>
        <KV label="Durée totale">{fmtMs(totalMs)}</KV>
        {err && <KV label="Erreur"><span className="text-rose-300">{err}</span></KV>}
      </div>

      {/* Champs finaux extraits */}
      <div>
        <div className="text-xs uppercase tracking-wide text-zinc-500 mb-2">
          Champs extraits (résultat arbitre)
        </div>
        {Object.keys(final).length === 0 ? (
          <div className="text-sm text-zinc-500 italic">
            Aucun champ extrait.
          </div>
        ) : (
          <div className="rounded border border-zinc-800 divide-y divide-zinc-800">
            {Object.entries(final).map(([k, v]) => (
              <div key={k} className="flex items-center gap-3 px-3 py-2">
                <span className="text-xs text-zinc-500 min-w-[130px]">
                  {k}
                </span>
                <span className="text-sm text-zinc-100 font-mono">
                  {v == null ? <span className="text-zinc-600">null</span> : String(v)}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Étapes détaillées */}
      <div>
        <div className="text-xs uppercase tracking-wide text-zinc-500 mb-2">
          Étapes du pipeline ({steps.length})
        </div>
        <div className="space-y-2">
          {steps.map((s, i) => (
            <AIStepCard key={i} step={s} />
          ))}
        </div>
      </div>
    </div>
  )
}

interface AIBatch {
  batch_index?: number
  is_final?: boolean
  model?: string
  candidates?: Array<{ id?: string; title?: string; publish_date?: string | null }>
  output?: Record<string, unknown> | null
  error?: string | null
  elapsed_ms?: number
}

function AIRankerDetail({ data }: { data: Record<string, unknown> }) {
  const status = (data.status as string) ?? 'success'
  const mode = data.applied_mode as string | undefined
  const model = data.model_used as string | undefined
  const scorerTop = data.scorer_top_index as number | null | undefined
  const aiPick = data.ai_picked_index as number | null | undefined
  const confidence = data.confidence as number | null | undefined
  const reason = data.reason as string | null | undefined
  const totalMs = data.total_elapsed_ms as number | undefined
  const batches = (data.batches as AIBatch[] | undefined) ?? []

  return (
    <div className="space-y-4">
      <div className="rounded border border-zinc-800 bg-zinc-900/40 p-3 space-y-1">
        <div className="flex items-center gap-2 mb-2">
          <span className="text-sm text-zinc-300 font-medium">Run ranker</span>
          <StatusPill status={status} />
          {mode && (
            <span className="text-xs text-zinc-500 px-2 py-0.5 rounded bg-zinc-800">
              mode: {mode}
            </span>
          )}
          {model && (
            <span className="text-xs text-zinc-400 font-mono">{model}</span>
          )}
        </div>
        <KV label="Durée totale">{fmtMs(totalMs)}</KV>
        <KV label="Pick scorer">
          {scorerTop == null ? 'aucun' : `index ${scorerTop}`}
        </KV>
        <KV label="Pick IA">
          {aiPick == null ? (
            <span className="text-rose-300">refusé</span>
          ) : (
            `index ${aiPick}`
          )}
        </KV>
        <KV label="Confiance">
          {confidence == null ? '?' : `${(confidence * 100).toFixed(0)} %`}
        </KV>
        {reason && <KV label="Raison">{reason}</KV>}
      </div>

      <div>
        <div className="text-xs uppercase tracking-wide text-zinc-500 mb-2">
          Batches ({batches.length})
        </div>
        <div className="space-y-2">
          {batches.map((b, i) => (
            <div
              key={i}
              className="rounded border border-zinc-800 bg-zinc-900/40 p-3"
            >
              <div className="flex items-center gap-2 mb-2">
                <span className="text-xs px-2 py-0.5 rounded bg-blue-950 text-blue-300 border border-blue-800 font-mono">
                  {b.is_final ? 'FINAL' : `Batch ${b.batch_index}`}
                </span>
                {b.model && (
                  <span className="text-xs text-zinc-400 font-mono">
                    {b.model}
                  </span>
                )}
                <span className="ml-auto text-xs text-zinc-500">
                  {fmtMs(b.elapsed_ms)}
                </span>
              </div>
              {b.candidates && b.candidates.length > 0 && (
                <div className="text-xs text-zinc-400 mb-2">
                  Candidats :
                  <ul className="list-decimal ml-6 mt-1 space-y-0.5">
                    {b.candidates.map((c, idx) => (
                      <li key={idx} className="text-zinc-300">
                        {c.title ?? c.id}
                        {c.publish_date && (
                          <span className="text-zinc-500 ml-2">
                            ({c.publish_date})
                          </span>
                        )}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {b.error && (
                <div className="text-xs text-rose-300">Erreur : {b.error}</div>
              )}
              {b.output && (
                <pre className="text-xs bg-zinc-950 border border-zinc-800 rounded p-2 overflow-x-auto text-zinc-300">
                  {JSON.stringify(b.output, null, 2)}
                </pre>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function formatSearchType(type: string | undefined, t: any): string {
  if (!type) return ''
  switch (type) {
    case 'manual':
      return t('historyDetail.searchManual')
    case 'free':
      return t('historyDetail.searchFree')
    case 'missing':
      return t('historyDetail.searchMissing')
    case 'rss':
      return t('historyDetail.searchRss')
    default:
      return type
  }
}

/** Parse details text from older events (before structured data was added). */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function renderFallbackDetails(
  eventType: string,
  details: string,
  t: any,
) {
  switch (eventType) {
    case 'grab': {
      // "Grabbed: <title>" or "Grabbed from <source>: <title>"
      const fromMatch = details.match(/^Grabbed from (.+?): (.+)$/)
      const simpleMatch = details.match(/^Grabbed: (.+)$/)
      if (fromMatch) {
        return (
          <div className="space-y-0">
            <DetailRow label={t('historyDetail.releaseTitle')} value={fromMatch[2]} />
            <DetailRow label={t('historyDetail.source')} value={fromMatch[1]} />
          </div>
        )
      }
      if (simpleMatch) {
        return (
          <div className="space-y-0">
            <DetailRow label={t('historyDetail.releaseTitle')} value={simpleMatch[1]} />
          </div>
        )
      }
      return <DetailRow label={t('historyDetail.details')} value={details} />
    }

    case 'searched': {
      // "RSS sync: 50 items scanned, 2 grabbed"
      const rssMatch = details.match(/^RSS sync: (\d+) items scanned, (\d+) grabbed$/)
      if (rssMatch) {
        return (
          <div className="space-y-0">
            <DetailRow label={t('historyDetail.searchType')} value={t('historyDetail.searchRss')} />
            <DetailRow label={t('historyDetail.itemsScanned')} value={Number(rssMatch[1])} />
            <DetailRow label={t('historyDetail.grabbedCount')} value={Number(rssMatch[2])} />
          </div>
        )
      }
      // "Manual search: <query> (N results)"
      const manualMatch = details.match(/^Manual search: (.+?) \((\d+) results\)$/)
      if (manualMatch) {
        return (
          <div className="space-y-0">
            <DetailRow label={t('historyDetail.searchType')} value={t('historyDetail.searchManual')} />
            <DetailRow label={t('historyDetail.query')} value={manualMatch[1]} />
            <DetailRow label={t('historyDetail.resultCount')} value={Number(manualMatch[2])} />
          </div>
        )
      }
      // "Free search: '<query>' (N results)"
      const freeMatch = details.match(/^Free search: '(.+?)' \((\d+) results\)$/)
      if (freeMatch) {
        return (
          <div className="space-y-0">
            <DetailRow label={t('historyDetail.searchType')} value={t('historyDetail.searchFree')} />
            <DetailRow label={t('historyDetail.query')} value={freeMatch[1]} />
            <DetailRow label={t('historyDetail.resultCount')} value={Number(freeMatch[2])} />
          </div>
        )
      }
      // "Missing issues search: N issues, M results"
      const missingMatch = details.match(/^Missing issues search: (\d+) issues, (\d+) results$/)
      if (missingMatch) {
        return (
          <div className="space-y-0">
            <DetailRow label={t('historyDetail.searchType')} value={t('historyDetail.searchMissing')} />
            <DetailRow label={t('historyDetail.wantedCount')} value={Number(missingMatch[1])} />
            <DetailRow label={t('historyDetail.resultCount')} value={Number(missingMatch[2])} />
          </div>
        )
      }
      return <DetailRow label={t('historyDetail.details')} value={details} />
    }

    case 'import':
    case 'upgrade': {
      // "Imported: <filename> (<quality>)"
      const importMatch = details.match(/^Imported: (.+?) \((.+?)\)$/)
      if (importMatch) {
        return (
          <div className="space-y-0">
            <DetailRow label={t('historyDetail.filename')} value={importMatch[1]} />
            <DetailRow label={t('historyDetail.quality')} value={importMatch[2]} />
          </div>
        )
      }
      // "Imported: <filename>"
      const simpleImport = details.match(/^Imported: (.+)$/)
      if (simpleImport) {
        return (
          <div className="space-y-0">
            <DetailRow label={t('historyDetail.filename')} value={simpleImport[1]} />
          </div>
        )
      }
      return <DetailRow label={t('historyDetail.details')} value={details} />
    }

    case 'download_completed': {
      // "Downloaded from <source>: <name>"
      const dlMatch = details.match(/^Downloaded from (.+?): (.+)$/)
      if (dlMatch) {
        return (
          <div className="space-y-0">
            <DetailRow label={t('historyDetail.source')} value={dlMatch[1]} />
            <DetailRow label={t('historyDetail.filename')} value={dlMatch[2]} />
          </div>
        )
      }
      return <DetailRow label={t('historyDetail.details')} value={details} />
    }

    case 'unmatched': {
      // "Unmatched file: <filename>"
      const unmatchedMatch = details.match(/^Unmatched file: (.+)$/)
      if (unmatchedMatch) {
        return (
          <div className="space-y-0">
            <DetailRow label={t('historyDetail.filename')} value={unmatchedMatch[1]} />
          </div>
        )
      }
      return <DetailRow label={t('historyDetail.details')} value={details} />
    }

    case 'error': {
      // "Import failed: <error>" or "Download failed: <error>"
      const errorMatch = details.match(/^(?:Import|Download) failed: (.+)$/)
      if (errorMatch) {
        return (
          <div className="space-y-0">
            <DetailRow label={t('historyDetail.error')} value={errorMatch[1]} />
          </div>
        )
      }
      return <DetailRow label={t('historyDetail.details')} value={details} />
    }

    default:
      return <DetailRow label={t('historyDetail.details')} value={details} />
  }
}


// WantedSearchDetail extrait dans ./WantedSearchDetail.tsx pour être
// réutilisé par le modal "Recherche maintenant" sur les issue rows.
