/**
 * Files — File Manager global.
 *
 * Vue unique sur tous les IssueFile du système avec :
 *  - Filtres : magazine, assigné/non, format, recherche full-text
 *  - Actions par ligne : Assigner (à un magazine + issue), Détacher,
 *    Supprimer (fichier disque + row DB)
 *  - Cleanup : bouton pour purger les rows dont le fichier a été
 *    supprimé hors pressarr (exists_on_disk=false)
 *  - Pagination serveur (50 par page par défaut, jusqu'à 500)
 */

import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import {
  ChevronLeft,
  ChevronRight,
  ExternalLink,
  Files as FilesIcon,
  FolderOpen,
  Loader2,
  Search,
  Trash2,
  Unlink,
  X,
} from 'lucide-react'

import {
  assignFile,
  deleteFile,
  getFiles,
  type AssignedFilter,
  type FileManagerRow,
} from '@/api/files'
import { getMagazines, type Magazine } from '@/api/magazines'
import { getIssues, type Issue } from '@/api/issues'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { useNavigate } from 'react-router-dom'

const PAGE_SIZE = 50

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(1024))
  return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${units[i]}`
}

function formatIssueLabel(row: FileManagerRow): string {
  if (!row.issue) return '—'
  const parts: string[] = []
  if (row.issue.number != null) parts.push(`N°${row.issue.number}`)
  if (row.issue.year != null) {
    const ym =
      row.issue.month != null
        ? `${String(row.issue.month).padStart(2, '0')}/${row.issue.year}`
        : String(row.issue.year)
    parts.push(ym)
  }
  return parts.join(' · ') || `#${row.issue.id}`
}

export default function Files() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()

  const [searchInput, setSearchInput] = useState('')
  const [search, setSearch] = useState('')
  const [magazineId, setMagazineId] = useState<number | null>(null)
  const [assigned, setAssigned] = useState<AssignedFilter>('all')
  const [format, setFormat] = useState<string>('')
  const [page, setPage] = useState(1)
  const [assignTarget, setAssignTarget] = useState<FileManagerRow | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<FileManagerRow | null>(null)

  // Debounce simple sur la barre de recherche pour éviter de spammer
  // le back à chaque frappe. Reset page à 1 au changement.
  useEffect(() => {
    const id = setTimeout(() => {
      setSearch(searchInput)
      setPage(1)
    }, 250)
    return () => clearTimeout(id)
  }, [searchInput])

  const { data: magazines = [] } = useQuery<Magazine[]>({
    queryKey: ['magazines'],
    queryFn: getMagazines,
  })

  const { data, isLoading, isError, error } = useQuery({
    queryKey: [
      'files',
      { search, magazineId, assigned, format, page },
    ],
    queryFn: () =>
      getFiles({
        search: search || undefined,
        magazineId: magazineId ?? undefined,
        assigned,
        format: format || undefined,
        page,
        pageSize: PAGE_SIZE,
      }),
    placeholderData: (prev) => prev,
  })

  const deleteMut = useMutation({
    mutationFn: (id: number) => deleteFile(id, true),
    onSuccess: () => {
      toast.success(t('files.deleteOk', 'Fichier supprimé'))
      qc.invalidateQueries({ queryKey: ['files'] })
      setDeleteTarget(null)
    },
    onError: (e: Error) => toast.error(e.message),
  })

  const detachMut = useMutation({
    mutationFn: (id: number) => assignFile(id, { issueId: null }),
    onSuccess: () => {
      toast.success(t('files.detachOk', 'Fichier détaché'))
      qc.invalidateQueries({ queryKey: ['files'] })
    },
    onError: (e: Error) => toast.error(e.message),
  })

  const totalPages = data
    ? Math.max(1, Math.ceil(data.total / data.pageSize))
    : 1

  return (
    <div className="p-4 lg:p-8 space-y-4">
      <div className="flex items-center gap-3">
        <FilesIcon className="size-6 text-violet-400" />
        <h1 className="text-2xl font-bold text-zinc-100">
          {t('files.title', 'File Manager')}
        </h1>
        {data && (
          <div className="ml-auto flex gap-2 flex-wrap text-xs">
            <Badge variant="outline" className="border-zinc-700 text-zinc-300">
              {data.total} {t('files.matching', 'résultats')}
            </Badge>
            <Badge variant="outline" className="border-emerald-800 text-emerald-400">
              {data.totalAssigned} {t('files.assigned', 'assignés')}
            </Badge>
            <Badge variant="outline" className="border-amber-800 text-amber-400">
              {data.totalUnassigned} {t('files.unassigned', 'non-assignés')}
            </Badge>
            {data.totalMissingOnDisk > 0 && (
              <Badge variant="outline" className="border-red-800 text-red-400">
                {data.totalMissingOnDisk} {t('files.missingOnDisk', 'manquants sur disque')}
              </Badge>
            )}
          </div>
        )}
      </div>

      {/* Filtres */}
      <Card className="bg-zinc-950 border-zinc-800">
        <CardContent className="pt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div className="relative">
            <Search className="absolute left-2 top-2.5 size-4 text-zinc-500" />
            <Input
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder={t('files.searchPlaceholder', 'Nom de fichier ou chemin…')}
              className="pl-8 bg-zinc-900 border-zinc-700 text-zinc-100"
            />
            {searchInput && (
              <button
                type="button"
                onClick={() => setSearchInput('')}
                className="absolute right-2 top-2.5 text-zinc-500 hover:text-zinc-300"
              >
                <X className="size-4" />
              </button>
            )}
          </div>

          <Select
            value={magazineId != null ? String(magazineId) : 'all'}
            onValueChange={(v) => {
              setMagazineId(v === 'all' ? null : Number(v))
              setPage(1)
            }}
          >
            <SelectTrigger className="bg-zinc-900 border-zinc-700 text-zinc-100">
              <SelectValue placeholder={t('files.magazineAll', 'Tous les magazines')} />
            </SelectTrigger>
            <SelectContent className="bg-zinc-900 border-zinc-700 max-h-72">
              <SelectItem value="all">
                {t('files.magazineAll', 'Tous les magazines')}
              </SelectItem>
              {magazines
                .slice()
                .sort((a, b) => a.title.localeCompare(b.title))
                .map((m) => (
                  <SelectItem key={m.id} value={String(m.id)}>
                    {m.title}
                  </SelectItem>
                ))}
            </SelectContent>
          </Select>

          <Select
            value={assigned}
            onValueChange={(v) => {
              setAssigned(v as AssignedFilter)
              setPage(1)
            }}
          >
            <SelectTrigger className="bg-zinc-900 border-zinc-700 text-zinc-100">
              <SelectValue />
            </SelectTrigger>
            <SelectContent className="bg-zinc-900 border-zinc-700">
              <SelectItem value="all">{t('files.assignedAll', 'Tous')}</SelectItem>
              <SelectItem value="yes">{t('files.assignedYes', 'Assignés')}</SelectItem>
              <SelectItem value="no">{t('files.assignedNo', 'Non-assignés')}</SelectItem>
            </SelectContent>
          </Select>

          <Select
            value={format || 'all'}
            onValueChange={(v) => {
              setFormat(v === 'all' ? '' : v)
              setPage(1)
            }}
          >
            <SelectTrigger className="bg-zinc-900 border-zinc-700 text-zinc-100">
              <SelectValue placeholder={t('files.formatAll', 'Tous formats')} />
            </SelectTrigger>
            <SelectContent className="bg-zinc-900 border-zinc-700">
              <SelectItem value="all">{t('files.formatAll', 'Tous formats')}</SelectItem>
              <SelectItem value="pdf">PDF</SelectItem>
              <SelectItem value="epub">EPUB</SelectItem>
              <SelectItem value="cbr">CBR</SelectItem>
              <SelectItem value="cbz">CBZ</SelectItem>
              <SelectItem value="mobi">MOBI</SelectItem>
            </SelectContent>
          </Select>
        </CardContent>
      </Card>

      {/* Table */}
      <Card className="bg-zinc-950 border-zinc-800">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-zinc-300 flex items-center gap-2">
            <FolderOpen className="size-4" />
            {t('files.listTitle', 'Fichiers')}
            {isLoading && <Loader2 className="size-3 animate-spin ml-2" />}
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {isError && (
            <p role="alert" className="p-4 text-sm text-red-400">
              {(error as Error).message}
            </p>
          )}
          {!isError && data && data.records.length === 0 && (
            <p className="p-6 text-center text-sm text-zinc-500">
              {t('files.empty', 'Aucun fichier ne correspond à ces filtres.')}
            </p>
          )}
          {data && data.records.length > 0 && (
            <Table>
              <TableHeader className="bg-zinc-900/60">
                <TableRow className="border-zinc-800">
                  <TableHead className="text-zinc-400">
                    {t('files.colFilename', 'Fichier')}
                  </TableHead>
                  <TableHead className="text-zinc-400">
                    {t('files.colMagazine', 'Magazine')}
                  </TableHead>
                  <TableHead className="text-zinc-400">
                    {t('files.colIssue', 'Issue')}
                  </TableHead>
                  <TableHead className="text-zinc-400">
                    {t('files.colFormat', 'Format')}
                  </TableHead>
                  <TableHead className="text-zinc-400 text-right">
                    {t('files.colSize', 'Taille')}
                  </TableHead>
                  <TableHead className="text-zinc-400">
                    {t('files.colImported', 'Importé le')}
                  </TableHead>
                  <TableHead className="text-zinc-400 text-right">
                    {t('files.colActions', 'Actions')}
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.records.map((r) => (
                  <TableRow
                    key={r.id}
                    className="border-zinc-800 hover:bg-zinc-900/40"
                  >
                    <TableCell className="max-w-[300px] truncate">
                      <div className="text-zinc-100 text-sm truncate" title={r.filename}>
                        {r.filename}
                      </div>
                      <div
                        className="text-[10px] text-zinc-500 truncate font-mono"
                        title={r.path}
                      >
                        {r.relativePath}
                      </div>
                      {!r.existsOnDisk && (
                        <Badge
                          variant="outline"
                          className="mt-1 border-red-800/60 bg-red-950/30 text-red-400 text-[9px]"
                        >
                          {t('files.missingOnDiskBadge', 'Fichier absent sur disque')}
                        </Badge>
                      )}
                    </TableCell>
                    <TableCell>
                      <button
                        type="button"
                        onClick={() => navigate(`/magazine/${r.magazine.id}`)}
                        className="text-sm text-violet-400 hover:text-violet-300 hover:underline text-left"
                      >
                        {r.magazine.title}
                      </button>
                    </TableCell>
                    <TableCell className="text-sm text-zinc-300">
                      {formatIssueLabel(r)}
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline" className="border-zinc-700 text-zinc-300 uppercase text-[9px]">
                        {r.format}
                      </Badge>
                      {r.quality && r.quality !== 'unknown' && (
                        <div className="text-[10px] text-zinc-500 mt-0.5">{r.quality}</div>
                      )}
                    </TableCell>
                    <TableCell className="text-right text-zinc-400 text-sm font-mono">
                      {formatBytes(r.size)}
                    </TableCell>
                    <TableCell className="text-xs text-zinc-500">
                      {new Date(r.importedAt).toLocaleDateString()}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-1">
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => setAssignTarget(r)}
                          className="h-7 text-violet-400 hover:text-violet-300 hover:bg-zinc-800"
                          title={t('files.assignHint', 'Réassigner à un autre magazine/issue')}
                        >
                          <ExternalLink className="size-3 mr-1" />
                          {t('files.assign', 'Réassigner')}
                        </Button>
                        {r.issue && (
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => detachMut.mutate(r.id)}
                            disabled={detachMut.isPending}
                            className="h-7 text-amber-400 hover:text-amber-300 hover:bg-zinc-800"
                            title={t(
                              'files.detachHint',
                              'Détacher de l\'issue (garde le fichier sous le magazine)',
                            )}
                          >
                            <Unlink className="size-3" />
                          </Button>
                        )}
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => setDeleteTarget(r)}
                          className="h-7 text-red-400 hover:text-red-300 hover:bg-zinc-800"
                          title={t('files.deleteHint', 'Supprimer (fichier disque + entrée DB)')}
                        >
                          <Trash2 className="size-3" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Pagination */}
      {data && data.total > PAGE_SIZE && (
        <div className="flex items-center justify-between text-xs text-zinc-400">
          <div>
            {t('files.pageInfo', 'Page')} {data.page} / {totalPages} —{' '}
            {(data.page - 1) * data.pageSize + 1}–
            {Math.min(data.page * data.pageSize, data.total)} {t('files.of', 'sur')}{' '}
            {data.total}
          </div>
          <div className="flex gap-1">
            <Button
              size="sm"
              variant="outline"
              disabled={page <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
            >
              <ChevronLeft className="size-3" />
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={page >= totalPages}
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            >
              <ChevronRight className="size-3" />
            </Button>
          </div>
        </div>
      )}

      {/* Assign dialog */}
      {assignTarget && (
        <AssignDialog
          file={assignTarget}
          onClose={() => setAssignTarget(null)}
          onDone={() => {
            qc.invalidateQueries({ queryKey: ['files'] })
            setAssignTarget(null)
          }}
        />
      )}

      {/* Delete confirm */}
      {deleteTarget && (
        <Dialog
          open={true}
          onOpenChange={(o) => {
            if (!o) setDeleteTarget(null)
          }}
        >
          <DialogContent className="bg-zinc-950 border-zinc-800">
            <DialogHeader>
              <DialogTitle className="text-zinc-100">
                {t('files.deleteConfirmTitle', 'Supprimer ce fichier ?')}
              </DialogTitle>
              <DialogDescription className="text-zinc-400">
                <div className="font-mono text-xs break-all py-1">
                  {deleteTarget.filename}
                </div>
                {t(
                  'files.deleteConfirmBody',
                  'Le fichier sera supprimé du disque ET l\'entrée retirée de la base. Action irréversible.',
                )}
              </DialogDescription>
            </DialogHeader>
            <DialogFooter>
              <Button variant="outline" onClick={() => setDeleteTarget(null)}>
                {t('common.cancel', 'Annuler')}
              </Button>
              <Button
                variant="destructive"
                onClick={() => deleteMut.mutate(deleteTarget.id)}
                disabled={deleteMut.isPending}
              >
                {deleteMut.isPending && (
                  <Loader2 className="size-3 mr-1 animate-spin" />
                )}
                {t('files.deleteDo', 'Supprimer')}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────


function AssignDialog({
  file,
  onClose,
  onDone,
}: {
  file: FileManagerRow
  onClose: () => void
  onDone: () => void
}) {
  const { t } = useTranslation()
  const [magazineId, setMagazineId] = useState<number>(file.magazine.id)
  const [issueId, setIssueId] = useState<number | null>(file.issue?.id ?? null)

  const { data: magazines = [] } = useQuery<Magazine[]>({
    queryKey: ['magazines'],
    queryFn: getMagazines,
  })
  const { data: issues = [], isLoading: issuesLoading } = useQuery<Issue[]>({
    queryKey: ['issues', magazineId],
    queryFn: () => getIssues(magazineId),
    enabled: magazineId > 0,
  })

  const sortedIssues = useMemo(
    () =>
      issues
        .slice()
        .sort((a, b) => (b.number ?? 0) - (a.number ?? 0)),
    [issues],
  )

  const mut = useMutation({
    mutationFn: () =>
      assignFile(file.id, { issueId: issueId, magazineId }),
    onSuccess: () => {
      toast.success(t('files.assignOk', 'Fichier réassigné'))
      onDone()
    },
    onError: (e: Error) => toast.error(e.message),
  })

  return (
    <Dialog open={true} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-xl bg-zinc-950 border-zinc-800">
        <DialogHeader>
          <DialogTitle className="text-zinc-100">
            {t('files.assignTitle', 'Réassigner ce fichier')}
          </DialogTitle>
          <DialogDescription className="font-mono text-xs text-zinc-400 break-all">
            {file.filename}
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 py-2">
          <div className="grid gap-1.5">
            <label className="text-xs font-medium text-zinc-300">
              {t('files.assignMagazine', 'Magazine')}
            </label>
            <Select
              value={String(magazineId)}
              onValueChange={(v) => {
                setMagazineId(Number(v))
                setIssueId(null)
              }}
            >
              <SelectTrigger className="bg-zinc-900 border-zinc-700 text-zinc-100">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="bg-zinc-900 border-zinc-700 max-h-72">
                {magazines
                  .slice()
                  .sort((a, b) => a.title.localeCompare(b.title))
                  .map((m) => (
                    <SelectItem key={m.id} value={String(m.id)}>
                      {m.title}
                    </SelectItem>
                  ))}
              </SelectContent>
            </Select>
          </div>

          <div className="grid gap-1.5">
            <label className="text-xs font-medium text-zinc-300 flex items-center gap-2">
              {t('files.assignIssue', 'Issue')}
              {issuesLoading && <Loader2 className="size-3 animate-spin" />}
            </label>
            <Select
              value={issueId != null ? String(issueId) : 'none'}
              onValueChange={(v) => setIssueId(v === 'none' ? null : Number(v))}
            >
              <SelectTrigger className="bg-zinc-900 border-zinc-700 text-zinc-100">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="bg-zinc-900 border-zinc-700 max-h-72">
                <SelectItem value="none">
                  — {t('files.assignDetach', 'Détacher (aucun issue)')} —
                </SelectItem>
                {sortedIssues.map((i) => (
                  <SelectItem key={i.id} value={String(i.id)}>
                    {i.number != null ? `N°${i.number} ` : ''}
                    {i.year != null
                      ? `(${i.month != null ? String(i.month).padStart(2, '0') + '/' : ''}${i.year})`
                      : ''}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-[10px] text-zinc-500">
              {t(
                'files.assignHelp',
                'Détacher garde le fichier sous le magazine mais sans l\'attacher à un issue précis (visible dans « Non-assignés »).',
              )}
            </p>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            {t('common.cancel', 'Annuler')}
          </Button>
          <Button
            className="bg-violet-600 hover:bg-violet-500 text-white"
            onClick={() => mut.mutate()}
            disabled={mut.isPending}
          >
            {mut.isPending && <Loader2 className="size-3 mr-1 animate-spin" />}
            {t('files.assignDo', 'Appliquer')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
