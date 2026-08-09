/**
 * PackFilesTab — onglet POST-HOC sur PackDetail qui liste les fichiers
 * importés via ce pack (via history.pack_id + eventType=import) avec
 * un bouton "Gérer" par magazine qui pointe vers la page du magazine
 * concerné (où le File Manager existant permet la réassignation).
 *
 * Le back consolide les fichiers importés d'un pack dans un unique
 * history event `import` avec `data.results[]`. On expand cette
 * structure pour afficher une ligne par fichier — un event pack qui
 * a importé N fichiers produit N lignes ici.
 */

import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import {
  Loader2,
  ExternalLink,
  AlertCircle,
  CheckCircle2,
  Package,
} from 'lucide-react'

import { getHistory, type HistoryEntry } from '@/api/history'
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

interface PackImportResult {
  filename?: string
  success?: boolean
  message?: string
  issue_id?: number | null
  magazine_id?: number | null
  magazine_title?: string | null
  issue_number?: number | string | null
}

interface Row {
  eventId: number
  eventDate: string
  filename: string
  success: boolean
  message: string | null
  magazineId: number | null
  magazineTitle: string | null
  issueNumber: string | null
}

function extractRows(events: HistoryEntry[]): Row[] {
  const out: Row[] = []
  for (const ev of events) {
    const results = (ev.data?.results as PackImportResult[] | undefined) ?? []
    if (!results.length) {
      // Événement import sans breakdown — surface a minima l'event
      out.push({
        eventId: ev.id,
        eventDate: ev.date,
        filename: ev.details ?? `Import pack #${ev.id}`,
        success: true,
        message: ev.details,
        magazineId: ev.magazineId,
        magazineTitle: ev.magazineTitle,
        issueNumber: ev.issueNumber != null ? String(ev.issueNumber) : null,
      })
      continue
    }
    for (const r of results) {
      out.push({
        eventId: ev.id,
        eventDate: ev.date,
        filename: r.filename ?? '(fichier inconnu)',
        success: r.success ?? false,
        message: r.message ?? null,
        magazineId: r.magazine_id ?? null,
        magazineTitle: r.magazine_title ?? null,
        issueNumber:
          r.issue_number != null ? String(r.issue_number) : null,
      })
    }
  }
  return out
}

interface Props {
  packId: number
}

export function PackFilesTab({ packId }: Props) {
  const { t } = useTranslation()
  const navigate = useNavigate()

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['pack-import-history', packId],
    queryFn: () =>
      getHistory({
        packId,
        eventType: 'import',
        pageSize: 100,
      }),
  })

  const rows = useMemo(
    () => extractRows(data?.records ?? []),
    [data?.records],
  )

  const totalOk = rows.filter((r) => r.success).length
  const totalKo = rows.filter((r) => !r.success).length

  if (isLoading) {
    return (
      <div className="pt-4 flex items-center gap-2 text-zinc-400 text-sm">
        <Loader2 className="size-4 animate-spin" />
        {t('packs.loadingFiles', 'Chargement des fichiers importés…')}
      </div>
    )
  }
  if (isError) {
    return (
      <p role="alert" className="pt-4 text-sm text-red-400">
        {(error as Error).message}
      </p>
    )
  }

  return (
    <div className="pt-4 space-y-4">
      <div className="flex items-center gap-3">
        <Package className="size-5 text-violet-400" />
        <h3 className="text-sm font-semibold text-zinc-100">
          {t('packs.filesTitle', 'Fichiers importés via ce pack')}
        </h3>
        <div className="ml-auto flex items-center gap-2 text-xs">
          <Badge variant="outline" className="border-emerald-800 text-emerald-400">
            {totalOk} {t('packs.filesOk', 'importés')}
          </Badge>
          {totalKo > 0 && (
            <Badge variant="outline" className="border-red-800 text-red-400">
              {totalKo} {t('packs.filesKo', 'échoués')}
            </Badge>
          )}
        </div>
      </div>

      {rows.length === 0 ? (
        <div className="rounded-md border border-zinc-800 bg-zinc-950 p-6 text-center">
          <p className="text-sm text-zinc-400">
            {t(
              'packs.filesEmpty',
              'Aucun import via ce pack pour le moment. Grab un release depuis l\'onglet Recherche pour peupler cette vue.',
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
                <TableHead className="text-zinc-400">
                  {t('packs.fileDate', 'Date')}
                </TableHead>
                <TableHead className="text-right text-zinc-400">
                  {t('packs.fileActions', 'Actions')}
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((r, i) => (
                <TableRow
                  key={`${r.eventId}-${i}`}
                  className="border-zinc-800 hover:bg-zinc-900/40"
                >
                  <TableCell className="font-mono text-xs text-zinc-100 max-w-[280px] truncate">
                    {r.filename}
                    {r.message && !r.success && (
                      <div className="text-[10px] text-red-400 mt-0.5 font-sans">
                        {r.message}
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
                    {r.success ? (
                      <Badge
                        variant="outline"
                        className="border-emerald-800/60 bg-emerald-950/30 text-emerald-400 text-[10px]"
                      >
                        <CheckCircle2 className="size-3 mr-1" />
                        OK
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
                  <TableCell className="text-zinc-500 text-xs">
                    {new Date(r.eventDate).toLocaleString()}
                  </TableCell>
                  <TableCell className="text-right">
                    {r.magazineId && (
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
          '💡 Pour réassigner un fichier à un autre magazine, ouvre le magazine cible → clique sur « File Manager » — glisse-dépose ou choisis l\'issue cible.',
        )}
      </p>
    </div>
  )
}
