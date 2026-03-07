import { useTranslation } from 'react-i18next'

import type { HistoryEntry } from '@/api/history'
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

function renderEventDetails(
  eventType: string,
  data: Record<string, unknown>,
  t: (key: string, fallback?: string) => string,
) {
  switch (eventType) {
    case 'grab':
      return (
        <div className="space-y-0">
          <DetailRow label={t('historyDetail.releaseTitle')} value={data.release_title as string} />
          <DetailRow label={t('historyDetail.magazine')} value={data.magazine_title as string} />
          <DetailRow label={t('historyDetail.issue')} value={data.issue_number != null ? `#${data.issue_number}` : undefined} />
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
            {data.indexers && (
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
          </div>

          {/* Top search results table */}
          {Array.isArray(data.top_results) && (data.top_results as SearchResult[]).length > 0 && (
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

    default:
      // Generic: show all data keys
      return (
        <div className="space-y-0">
          {Object.entries(data).map(([key, value]) => (
            <DetailRow
              key={key}
              label={key.replace(/_/g, ' ')}
              value={value != null ? String(value) : null}
            />
          ))}
        </div>
      )
  }
}

function formatSearchType(type: string | undefined, t: (key: string, fallback?: string) => string): string {
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
function renderFallbackDetails(
  eventType: string,
  details: string,
  t: (key: string, fallback?: string) => string,
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
