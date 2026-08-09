/**
 * PackFilesTab — onglet POST-HOC sur PackDetail.
 *
 * Croise 2 sources :
 *  - History (event_type=import, pack_id=X) → fichiers déjà passés
 *    par dispatch, avec statut OK/échoué + magazine matché
 *  - Pending files (GET /pack/{id}/pending-files) → fichiers du dernier
 *    download qui sont encore physiquement sur disque et n'ont pas
 *    été importés (typique après auto_import silencieux qui a skip
 *    la plupart des fichiers < fuzzy 60%)
 *
 * Chaque ligne expose :
 *  - "Gérer" (si OK) : redirige vers /magazine/{id} pour le File Manager
 *  - "Réimporter" (si échec/pending) : ouvre PackFileReimportDialog
 */

import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import {
  Loader2,
  ExternalLink,
  AlertCircle,
  CheckCircle2,
  Package,
  RotateCcw,
  Clock,
} from 'lucide-react'

import { getHistory, type HistoryEntry } from '@/api/history'
import { getPackPendingFiles, type PackPendingFile } from '@/api/packs'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { PackFileReimportDialog } from './PackFileReimportDialog'

interface PackImportResult {
  filename?: string
  success?: boolean
  message?: string
  issue_id?: number | null
  magazine_id?: number | null
  magazine_title?: string | null
  issue_number?: number | string | null
}

type RowKind = 'ok' | 'failed' | 'pending'

interface Row {
  key: string
  kind: RowKind
  filename: string
  proposedTitle: string | null
  message: string | null
  magazineId: number | null
  magazineTitle: string | null
  issueNumber: string | null
  eventDate: string | null
}

function extractHistoryRows(events: HistoryEntry[]): Row[] {
  const out: Row[] = []
  for (const ev of events) {
    const results = (ev.data?.results as PackImportResult[] | undefined) ?? []
    if (!results.length) {
      out.push({
        key: `hist-${ev.id}`,
        kind: 'ok',
        filename: ev.details ?? `Import pack #${ev.id}`,
        proposedTitle: null,
        message: ev.details,
        magazineId: ev.magazineId,
        magazineTitle: ev.magazineTitle,
        issueNumber: ev.issueNumber != null ? String(ev.issueNumber) : null,
        eventDate: ev.date,
      })
      continue
    }
    for (let i = 0; i < results.length; i++) {
      const r = results[i]
      out.push({
        key: `hist-${ev.id}-${i}`,
        kind: r.success ? 'ok' : 'failed',
        filename: r.filename ?? '(fichier inconnu)',
        proposedTitle: null,
        message: r.message ?? null,
        magazineId: r.magazine_id ?? null,
        magazineTitle: r.magazine_title ?? null,
        issueNumber: r.issue_number != null ? String(r.issue_number) : null,
        eventDate: ev.date,
      })
    }
  }
  return out
}

function pendingToRow(p: PackPendingFile): Row {
  return {
    key: `pend-${p.filename}`,
    kind: 'pending',
    filename: p.filename,
    proposedTitle: p.parsed_title,
    message: p.exclude_reason,
    magazineId: p.matched_magazine_id,
    magazineTitle: p.matched_magazine_title,
    issueNumber: p.parsed_number,
    eventDate: null,
  }
}

interface Props {
  packId: number
}

export function PackFilesTab({ packId }: Props) {
  const { t } = useTranslation()
  const navigate = useNavigate()

  const historyQ = useQuery({
    queryKey: ['pack-import-history', packId],
    queryFn: () =>
      getHistory({
        packId,
        eventType: 'import',
        pageSize: 100,
      }),
  })
  const pendingQ = useQuery({
    queryKey: ['pack-pending-files', packId],
    queryFn: () => getPackPendingFiles(packId),
  })

  const [reimport, setReimport] = useState<{
    filename: string
    proposedTitle: string | null
  } | null>(null)

  const rows = useMemo<Row[]>(() => {
    const historyRows = extractHistoryRows(historyQ.data?.records ?? [])
    const historyFilenames = new Set(
      historyRows.filter((r) => r.kind === 'ok').map((r) => r.filename),
    )
    const pendingRows = (pendingQ.data?.files ?? [])
      // Ne montre pas les pending qui ont déjà été importés OK ailleurs
      // (avoid duplicates)
      .filter((p) => !historyFilenames.has(p.filename))
      .map(pendingToRow)
    // Pending en premier (action requise) puis history (chronologique).
    return [...pendingRows, ...historyRows]
  }, [historyQ.data, pendingQ.data])

  const isLoading = historyQ.isLoading || pendingQ.isLoading
  const downloadId = pendingQ.data?.downloadId ?? null

  const totalOk = rows.filter((r) => r.kind === 'ok').length
  const totalKo = rows.filter((r) => r.kind === 'failed').length
  const totalPending = rows.filter((r) => r.kind === 'pending').length

  if (isLoading) {
    return (
      <div className="pt-4 flex items-center gap-2 text-zinc-400 text-sm">
        <Loader2 className="size-4 animate-spin" />
        {t('packs.loadingFiles', 'Chargement des fichiers…')}
      </div>
    )
  }

  return (
    <>
      <div className="pt-4 space-y-4">
        <div className="flex items-center gap-3 flex-wrap">
          <Package className="size-5 text-violet-400" />
          <h3 className="text-sm font-semibold text-zinc-100">
            {t('packs.filesTitle', 'Fichiers du pack')}
          </h3>
          <div className="ml-auto flex items-center gap-2 text-xs flex-wrap">
            {totalOk > 0 && (
              <Badge variant="outline" className="border-emerald-800 text-emerald-400">
                {totalOk} {t('packs.filesOk', 'importés')}
              </Badge>
            )}
            {totalKo > 0 && (
              <Badge variant="outline" className="border-red-800 text-red-400">
                {totalKo} {t('packs.filesKo', 'échoués')}
              </Badge>
            )}
            {totalPending > 0 && (
              <Badge variant="outline" className="border-amber-800 text-amber-400">
                {totalPending} {t('packs.filesPending', 'en attente')}
              </Badge>
            )}
          </div>
        </div>

        {rows.length === 0 ? (
          <div className="rounded-md border border-zinc-800 bg-zinc-950 p-6 text-center">
            <p className="text-sm text-zinc-400">
              {t(
                'packs.filesEmpty',
                'Aucun fichier pour ce pack pour le moment. Grab un release depuis l\'onglet Recherche pour peupler cette vue.',
              )}
            </p>
          </div>
        ) : (
          <div className="rounded-md border border-zinc-800 bg-zinc-950/60 overflow-hidden">
            <Table>
              <TableHeader className="bg-zinc-900/60">
                <TableRow className="border-zinc-800">
                  <TableHead className="text-zinc-400">
                    {t('packs.fileName', 'Fichier')}
                  </TableHead>
                  <TableHead className="text-zinc-400">
                    {t('packs.fileMagazine', 'Magazine')}
                  </TableHead>
                  <TableHead className="text-zinc-400">
                    {t('packs.fileIssue', 'Issue')}
                  </TableHead>
                  <TableHead className="text-zinc-400">
                    {t('packs.fileStatus', 'Statut')}
                  </TableHead>
                  <TableHead className="text-right text-zinc-400">
                    {t('packs.fileActions', 'Actions')}
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((r) => (
                  <TableRow
                    key={r.key}
                    className="border-zinc-800 hover:bg-zinc-900/40"
                  >
                    <TableCell className="font-mono text-xs text-zinc-100 max-w-[280px] truncate">
                      {r.filename}
                      {r.message && r.kind !== 'ok' && (
                        <div className="text-[10px] text-red-400 mt-0.5 font-sans">
                          {r.message}
                        </div>
                      )}
                      {r.proposedTitle && r.kind === 'pending' && (
                        <div className="text-[10px] text-zinc-500 mt-0.5 font-sans italic">
                          {t('packs.filesParsedAs', 'Parsé comme :')} « {r.proposedTitle} »
                        </div>
                      )}
                    </TableCell>
                    <TableCell className="text-zinc-300 text-sm">
                      {r.magazineTitle ?? (
                        <span className="text-zinc-600">—</span>
                      )}
                    </TableCell>
                    <TableCell className="text-zinc-400 text-sm">
                      {r.issueNumber ? `N° ${r.issueNumber}` : '—'}
                    </TableCell>
                    <TableCell>
                      {r.kind === 'ok' ? (
                        <Badge
                          variant="outline"
                          className="border-emerald-800/60 bg-emerald-950/30 text-emerald-400 text-[10px]"
                        >
                          <CheckCircle2 className="size-3 mr-1" />
                          OK
                        </Badge>
                      ) : r.kind === 'pending' ? (
                        <Badge
                          variant="outline"
                          className="border-amber-800/60 bg-amber-950/30 text-amber-400 text-[10px]"
                        >
                          <Clock className="size-3 mr-1" />
                          {t('packs.filesPendingBadge', 'En attente')}
                        </Badge>
                      ) : (
                        <Badge
                          variant="outline"
                          className="border-red-800/60 bg-red-950/30 text-red-400 text-[10px]"
                        >
                          <AlertCircle className="size-3 mr-1" />
                          {t('packs.fileFailed', 'Échoué')}
                        </Badge>
                      )}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-1">
                        {r.kind === 'ok' && r.magazineId && (
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => navigate(`/magazine/${r.magazineId}`)}
                            className="h-7 text-violet-400 hover:text-violet-300 hover:bg-zinc-800"
                            title={t(
                              'packs.openMagazine',
                              'Ouvrir le magazine (File Manager permet de réassigner)',
                            )}
                          >
                            <ExternalLink className="size-3 mr-1" />
                            {t('packs.manage', 'Gérer')}
                          </Button>
                        )}
                        {r.kind !== 'ok' && (
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() =>
                              setReimport({
                                filename: r.filename,
                                proposedTitle: r.proposedTitle,
                              })
                            }
                            className="h-7 text-amber-400 hover:text-amber-300 hover:bg-zinc-800"
                            title={t(
                              'packs.reimportHint',
                              'Réimporter avec un magazine existant ou en créant un nouveau',
                            )}
                          >
                            <RotateCcw className="size-3 mr-1" />
                            {t('packs.reimport', 'Réimporter')}
                          </Button>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}

        <p className="text-[10px] text-zinc-500">
          {t(
            'packs.filesHint',
            '💡 « Réimporter » ouvre un dialog pour choisir le bon magazine (existant OU créé à la volée). L\'issue est créée automatiquement à partir du parsing du nom de fichier.',
          )}
        </p>
      </div>

      {reimport && (
        <PackFileReimportDialog
          packId={packId}
          downloadId={downloadId}
          filename={reimport.filename}
          proposedTitle={reimport.proposedTitle}
          open={reimport !== null}
          onOpenChange={(o) => {
            if (!o) setReimport(null)
          }}
        />
      )}
    </>
  )
}
