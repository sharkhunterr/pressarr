import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import {
  AlertCircle,
  Ban,
  Check,
  ChevronDown,
  ChevronRight,
  Clock,
  Download,
  FileText,
  Loader2,
  Package,
  RefreshCw,
  RotateCw,
  ShieldAlert,
  ShieldCheck,
  ShieldX,
  Sparkles,
  Trash2,
  Upload,
} from 'lucide-react'

import {
  deletePackDispatchFile,
  listPackDispatchFiles,
  reanalyzePackDispatchFile,
  rescanImportedPackDispatch,
  resolvePackDispatchFile,
  unimportPackDispatchFile,
  updatePackDispatchMetadata,
  type PackDispatchFile,
  type PackDispatchMetadataOverrides,
} from '@/api/packs'
import { getMagazines, type Magazine } from '@/api/magazines'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
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

interface Props {
  packId: number
}

// L'UI n'expose que 3 statuts principaux (en attente / importé / ignoré).
// pending_analysis et error sont considérés comme des sous-états de "en
// attente" — les actions user restent les mêmes.
const STATUS_LABELS: Record<PackDispatchFile['status'], string> = {
  pending_analysis: 'Analyse…',
  pending_user: 'En attente',
  imported: 'Importé',
  ignored: 'Ignoré',
  error: 'En attente',
}

const STATUS_STYLES: Record<PackDispatchFile['status'], string> = {
  pending_analysis: 'bg-zinc-800 text-zinc-300',
  pending_user: 'bg-amber-500/20 text-amber-200 border border-amber-500/30',
  imported: 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30',
  ignored: 'bg-zinc-700/40 text-zinc-500',
  error: 'bg-amber-500/20 text-amber-200 border border-amber-500/30',
}

type UiStatus = 'all' | 'pending' | 'imported' | 'ignored'

const STATUS_FILTERS: Array<{ value: UiStatus; label: string }> = [
  { value: 'all', label: 'Tout' },
  { value: 'pending', label: 'En attente' },
  { value: 'imported', label: 'Importés' },
  { value: 'ignored', label: 'Ignorés' },
]

// Un fichier est "en attente d'action user" si non-imported/non-ignoré.
// pending_analysis, pending_user, error → tous listés dans "En attente".
const isPending = (s: PackDispatchFile['status']) =>
  s === 'pending_analysis' || s === 'pending_user' || s === 'error'

function formatSize(bytes: number): string {
  if (!bytes) return '—'
  const u = ['o', 'ko', 'Mo', 'Go']
  let i = 0
  let n = bytes
  while (n >= 1024 && i < u.length - 1) {
    n /= 1024
    i++
  }
  return `${n.toFixed(i === 0 ? 0 : 1)} ${u[i]}`
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString(undefined, {
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

interface PackGrab {
  downloadId: string
  files: PackDispatchFile[]
  totalSize: number
  earliestCreatedAt: string
  counts: Record<PackDispatchFile['status'], number>
}

function groupByDownload(files: PackDispatchFile[]): PackGrab[] {
  const groups = new Map<string, PackGrab>()
  for (const f of files) {
    const key = f.downloadId || 'unknown'
    let g = groups.get(key)
    if (!g) {
      g = {
        downloadId: key,
        files: [],
        totalSize: 0,
        earliestCreatedAt: f.createdAt,
        counts: {
          pending_analysis: 0,
          pending_user: 0,
          imported: 0,
          ignored: 0,
          error: 0,
        },
      }
      groups.set(key, g)
    }
    g.files.push(f)
    g.totalSize += f.size || 0
    if (new Date(f.createdAt) < new Date(g.earliestCreatedAt)) {
      g.earliestCreatedAt = f.createdAt
    }
    g.counts[f.status]++
  }
  // Tri : grab le plus récent en haut
  return [...groups.values()].sort(
    (a, b) => new Date(b.earliestCreatedAt).getTime() - new Date(a.earliestCreatedAt).getTime(),
  )
}

export function PackDispatchTab({ packId }: Props) {
  const qc = useQueryClient()
  const [filter, setFilter] = useState<UiStatus>('all')
  const [selected, setSelected] = useState<PackDispatchFile | null>(null)
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set())

  // On charge TOUT et filtre client-side pour permettre le groupement
  // par download_id sur toutes les rows (sinon les grabs mixtes seraient
  // scindés artificiellement par le filtre serveur).
  const filesQ = useQuery({
    queryKey: ['pack-dispatch', packId],
    queryFn: () => listPackDispatchFiles(packId),
    refetchInterval: (q) => {
      const data = q.state.data as PackDispatchFile[] | undefined
      if (!data) return 4000
      const live = data.some((f) => f.status === 'pending_analysis')
      return live ? 3000 : 8000
    },
    refetchIntervalInBackground: false,
  })

  const magazinesQ = useQuery({
    queryKey: ['magazines-all'],
    queryFn: () => getMagazines(),
    staleTime: 60_000,
  })

  const files = filesQ.data ?? []
  const filteredFiles = useMemo(() => {
    if (filter === 'all') return files
    if (filter === 'pending') return files.filter((f) => isPending(f.status))
    return files.filter((f) => f.status === filter)
  }, [files, filter])

  const grabs = useMemo(() => groupByDownload(filteredFiles), [filteredFiles])

  const counts = useMemo(() => {
    let pending = 0, imported = 0, ignored = 0
    for (const f of files) {
      if (isPending(f.status)) pending++
      else if (f.status === 'imported') imported++
      else if (f.status === 'ignored') ignored++
    }
    return { all: files.length, pending, imported, ignored }
  }, [files])

  const refresh = () => qc.invalidateQueries({ queryKey: ['pack-dispatch', packId] })

  const rescanMut = useMutation({
    mutationFn: () => rescanImportedPackDispatch(packId),
    onMutate: () => {
      toast.loading(
        `Réanalyse des ${counts.imported} fichiers importés — peut prendre plusieurs minutes…`,
        { id: `rescan-${packId}` },
      )
    },
    onSuccess: (res) => {
      toast.success(
        `Rescan terminé : ${res.reanalyzed}/${res.total} OK · ${res.errors} erreur(s)`,
        { id: `rescan-${packId}` },
      )
      qc.invalidateQueries({ queryKey: ['pack-dispatch', packId] })
    },
    onError: (e: Error) =>
      toast.error(`Échec rescan : ${e.message}`, { id: `rescan-${packId}` }),
  })

  const toggleGroup = (key: string) => {
    setCollapsed((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  return (
    <div className="pt-4 space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        {STATUS_FILTERS.map((f) => (
          <Button
            key={f.value}
            variant={filter === f.value ? 'default' : 'outline'}
            size="sm"
            onClick={() => setFilter(f.value)}
            className={filter === f.value ? 'bg-[#7C3AED] hover:bg-[#6D28D9]' : ''}
          >
            {f.label}
            {counts[f.value] > 0 && (
              <span className="ml-1.5 text-xs opacity-75">{counts[f.value]}</span>
            )}
          </Button>
        ))}
        <div className="grow" />
        {counts.imported > 0 && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              if (
                confirm(
                  `Réanalyser IA les ${counts.imported} fichiers déjà importés ?\n\n` +
                    `Ça met à jour les metadata extraites + confidence sans toucher aux imports. ` +
                    `Prend ~30-60s par fichier.`,
                )
              )
                rescanMut.mutate()
            }}
            disabled={rescanMut.isPending}
            title="Ré-analyser IA sur tous les fichiers importés (metadata seulement)"
          >
            {rescanMut.isPending ? (
              <Loader2 className="size-3.5 animate-spin text-purple-400" />
            ) : (
              <Sparkles className="size-3.5 text-purple-400" />
            )}
            Rescan importés
          </Button>
        )}
        <Button variant="outline" size="sm" onClick={refresh}>
          <RefreshCw className="size-3.5" />
          Rafraîchir
        </Button>
      </div>

      {filesQ.isLoading ? (
        <div className="flex items-center justify-center py-12 text-zinc-500">
          <Loader2 className="size-4 animate-spin mr-2" />
          Chargement…
        </div>
      ) : grabs.length === 0 ? (
        <div className="rounded border border-dashed border-zinc-800 py-10 text-center text-zinc-500">
          Aucun fichier dispatch — lance un grab pour peupler cette liste.
        </div>
      ) : (
        <div className="space-y-3">
          {grabs.map((g) => (
            <GrabGroup
              key={g.downloadId}
              grab={g}
              collapsed={collapsed.has(g.downloadId)}
              onToggle={() => toggleGroup(g.downloadId)}
              magazines={magazinesQ.data ?? []}
              onDetail={setSelected}
              packId={packId}
            />
          ))}
        </div>
      )}

      <DispatchDetailModal
        packId={packId}
        file={selected}
        magazines={magazinesQ.data ?? []}
        onClose={() => setSelected(null)}
      />
    </div>
  )
}

function GrabGroup({
  grab,
  collapsed,
  onToggle,
  magazines,
  onDetail,
  packId,
}: {
  grab: PackGrab
  collapsed: boolean
  onToggle: () => void
  magazines: Magazine[]
  onDetail: (row: PackDispatchFile) => void
  packId: number
}) {
  const shortId = grab.downloadId.slice(0, 12)
  const pending = grab.counts.pending_analysis + grab.counts.pending_user + grab.counts.error
  return (
    <div className="rounded border border-zinc-800 overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full flex items-center gap-3 px-3 py-2.5 bg-zinc-900/70 hover:bg-zinc-900 text-left"
      >
        {collapsed ? (
          <ChevronRight className="size-4 text-zinc-500 shrink-0" />
        ) : (
          <ChevronDown className="size-4 text-zinc-400 shrink-0" />
        )}
        <Package className="size-4 text-purple-400 shrink-0" />
        <div className="flex-1 min-w-0">
          <div className="flex items-baseline gap-2 flex-wrap">
            <span className="text-sm font-medium text-zinc-100">Grab</span>
            <span className="text-xs font-mono text-zinc-500">{shortId}</span>
          </div>
          <div className="flex items-center gap-3 text-xs text-zinc-500 mt-0.5 flex-wrap">
            <span className="inline-flex items-center gap-1">
              <FileText className="size-3" />
              {grab.files.length} fichier{grab.files.length > 1 ? 's' : ''}
            </span>
            <span className="inline-flex items-center gap-1">
              <Download className="size-3" />
              {formatSize(grab.totalSize)}
            </span>
            <span className="inline-flex items-center gap-1">
              <Clock className="size-3" />
              {formatDate(grab.earliestCreatedAt)}
            </span>
          </div>
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          {pending > 0 && (
            <Badge className="bg-amber-500/20 text-amber-200 border border-amber-500/30">
              {pending} en attente
            </Badge>
          )}
          {grab.counts.imported > 0 && (
            <Badge className="bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
              {grab.counts.imported} importé{grab.counts.imported > 1 ? 's' : ''}
            </Badge>
          )}
          {grab.counts.ignored > 0 && (
            <Badge className="bg-zinc-700/40 text-zinc-500">
              {grab.counts.ignored} ignoré{grab.counts.ignored > 1 ? 's' : ''}
            </Badge>
          )}
        </div>
      </button>
      {!collapsed && (
        <Table>
          <TableHeader>
            <TableRow className="border-zinc-800 hover:bg-transparent">
              <TableHead className="text-zinc-400">Fichier</TableHead>
              <TableHead className="text-zinc-400">Extrait IA</TableHead>
              <TableHead className="text-zinc-400">Magazine</TableHead>
              <TableHead className="text-zinc-400">Statut</TableHead>
              <TableHead className="text-zinc-400 text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {grab.files.map((f) => (
              <DispatchRow
                key={f.id}
                file={f}
                magazines={magazines}
                onDetail={onDetail}
                packId={packId}
              />
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  )
}

function DispatchRow({
  file,
  magazines,
  onDetail,
  packId,
}: {
  file: PackDispatchFile
  magazines: Magazine[]
  onDetail: (row: PackDispatchFile) => void
  packId: number
}) {
  const qc = useQueryClient()
  const ex = file.extractedMetadata

  const reanalyze = useMutation({
    mutationFn: () => reanalyzePackDispatchFile(packId, file.id),
    onMutate: () => {
      toast.loading(`${file.filename} — analyse IA en cours…`, {
        id: `reanalyze-${file.id}`,
      })
    },
    onSuccess: (res) => {
      toast.success(
        `${file.filename} — ${
          res.confidence === 'confirmed'
            ? 'confirmé'
            : res.confidence === 'rejected'
              ? 'rejeté'
              : 'à valider'
        }`,
        { id: `reanalyze-${file.id}` },
      )
      qc.invalidateQueries({ queryKey: ['pack-dispatch', packId] })
    },
    onError: (e: Error) =>
      toast.error(`Échec : ${e.message}`, { id: `reanalyze-${file.id}` }),
  })

  const ignore = useMutation({
    mutationFn: () => resolvePackDispatchFile(packId, file.id, { action: 'ignore' }),
    onSuccess: () => {
      toast.success(`${file.filename} ignoré`)
      qc.invalidateQueries({ queryKey: ['pack-dispatch', packId] })
    },
    onError: (e: Error) => toast.error(`Échec : ${e.message}`),
  })

  // Réimporter : annule l'import (delete issue + placeholder mag vide)
  // puis rouvre le modal pour choisir un autre magazine cible. La row
  // retour est en pending_user → on l'ouvre directement.
  const reimport = useMutation({
    mutationFn: () => unimportPackDispatchFile(packId, file.id),
    onSuccess: (row) => {
      toast.success('Import annulé — choisis un nouveau magazine')
      qc.invalidateQueries({ queryKey: ['pack-dispatch', packId] })
      qc.invalidateQueries({ queryKey: ['magazines'] })
      qc.invalidateQueries({ queryKey: ['magazines-all'] })
      // Ouvre le modal avec le row fraîchement resetté
      onDetail(row)
    },
    onError: (e: Error) => toast.error(`Échec ré-import : ${e.message}`),
  })

  const del = useMutation({
    mutationFn: () => deletePackDispatchFile(packId, file.id),
    onSuccess: () => {
      toast.success('Row supprimée')
      qc.invalidateQueries({ queryKey: ['pack-dispatch', packId] })
    },
    onError: (e: Error) => toast.error(`Échec : ${e.message}`),
  })

  const magTitle =
    file.matchedMagazineTitle ??
    (file.userActionMagazineId != null
      ? magazines.find((m) => m.id === file.userActionMagazineId)?.title ?? '—'
      : '—')

  const pending = isPending(file.status)
  const imported = file.status === 'imported'
  const ignored = file.status === 'ignored'

  return (
    <TableRow className="border-zinc-800 hover:bg-zinc-900/50">
      <TableCell className="align-top">
        <button
          onClick={() => onDetail(file)}
          className="text-left text-zinc-100 hover:text-purple-300 flex items-start gap-2 max-w-md"
        >
          <FileText className="size-4 mt-0.5 shrink-0 text-zinc-500" />
          <span className="truncate text-sm">{file.filename}</span>
        </button>
        {file.errorMessage && (
          <div className="mt-1 flex items-center gap-1 text-xs text-red-400">
            <AlertCircle className="size-3" />
            <span className="truncate max-w-xs">{file.errorMessage}</span>
          </div>
        )}
      </TableCell>

      <TableCell className="align-top">
        {ex ? (
          <div className="text-xs text-zinc-400 space-y-0.5">
            {ex.title && <div className="text-zinc-200">{ex.title}</div>}
            <div className="flex flex-wrap gap-x-2">
              {ex.issue_number != null && <span>N°{ex.issue_number}</span>}
              {ex.year && (
                <span>
                  {ex.day ? `${String(ex.day).padStart(2, '0')}/` : ''}
                  {ex.month ? `${String(ex.month).padStart(2, '0')}/` : ''}
                  {ex.year}
                </span>
              )}
              {ex.issn && <span className="font-mono">ISSN {ex.issn}</span>}
            </div>
            {ex.source && (
              <div className="text-[10px] text-zinc-600 uppercase tracking-wide">
                via {ex.source}
              </div>
            )}
          </div>
        ) : file.status === 'pending_analysis' ? (
          <div className="flex items-center gap-1 text-xs text-zinc-500">
            <Loader2 className="size-3 animate-spin" />
            Analyse…
          </div>
        ) : (
          <span className="text-xs text-zinc-600">—</span>
        )}
      </TableCell>

      <TableCell className="align-top">
        <div className="text-sm text-zinc-200">{magTitle}</div>
        {file.matchScore != null && (
          <div className="text-[10px] text-zinc-500">
            {file.matchSource ?? '?'} · {file.matchScore.toFixed(0)}%
          </div>
        )}
      </TableCell>

      <TableCell className="align-top">
        <div className="flex flex-col gap-1 items-start">
          <Badge className={STATUS_STYLES[file.status]}>
            {STATUS_LABELS[file.status]}
          </Badge>
          {file.confidence && <ConfidenceBadge value={file.confidence} />}
        </div>
      </TableCell>

      <TableCell className="text-right align-top">
        <div className="inline-flex items-center gap-1">
          {/* PENDING (analysis / user / error) : Import · Ignore · IA · Del */}
          {pending && (
            <>
              <Button
                variant="outline"
                size="sm"
                onClick={() => onDetail(file)}
                className="text-purple-300 border-purple-500/40 hover:bg-purple-500/10"
                title="Importer — choisir un magazine cible"
              >
                <Upload className="size-3.5" />
                Importer
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => ignore.mutate()}
                disabled={ignore.isPending}
                className="text-zinc-300 border-zinc-700 hover:bg-zinc-800"
                title="Marquer comme ignoré — le fichier ne sera pas importé"
              >
                {ignore.isPending ? (
                  <Loader2 className="size-3.5 animate-spin" />
                ) : (
                  <Ban className="size-3.5" />
                )}
                Ignorer
              </Button>
            </>
          )}

          {/* IMPORTED : Réimporter · IA · Del */}
          {imported && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                if (
                  confirm(
                    `Annuler l'import de "${file.filename}" ?\n\n` +
                      `L'issue créée sera supprimée. Si le magazine cible avait été auto-créé ` +
                      `(placeholder) et ne contient plus aucune autre issue, il sera aussi supprimé. ` +
                      `Tu pourras ensuite choisir un autre magazine cible.`,
                  )
                )
                  reimport.mutate()
              }}
              disabled={reimport.isPending}
              className="text-amber-300 border-amber-500/40 hover:bg-amber-500/10"
              title="Ré-importer — annule l'import courant et rouvre le modal"
            >
              {reimport.isPending ? (
                <Loader2 className="size-3.5 animate-spin" />
              ) : (
                <RotateCw className="size-3.5" />
              )}
              Ré-importer
            </Button>
          )}

          {/* IGNORED : Importer (unignore) · Del */}
          {ignored && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => onDetail(file)}
              className="text-purple-300 border-purple-500/40 hover:bg-purple-500/10"
              title="Réactiver et importer"
            >
              <Upload className="size-3.5" />
              Importer
            </Button>
          )}

          {/* IA — sur tous sauf ignored (pas de sens d'analyser un ignoré) */}
          {!ignored && (
            <Button
              variant="ghost"
              size="icon-xs"
              onClick={() => reanalyze.mutate()}
              disabled={reanalyze.isPending}
              title={
                imported
                  ? 'Ré-analyser IA (metadata seulement — l\'import n\'est pas touché)'
                  : file.matchedMagazineId
                    ? 'Relancer analyse IA avec les zones du magazine matché'
                    : 'Relancer analyse IA'
              }
            >
              {reanalyze.isPending ? (
                <Loader2 className="size-3.5 animate-spin text-purple-400" />
              ) : (
                <Sparkles className="size-3.5 text-purple-400" />
              )}
            </Button>
          )}

          <Button
            variant="ghost"
            size="icon-xs"
            onClick={() => {
              if (confirm('Retirer cette entrée du registre dispatch ?')) del.mutate()
            }}
            disabled={del.isPending}
            title="Supprimer entrée"
          >
            <Trash2 className="size-3.5 text-red-400/70" />
          </Button>
        </div>
      </TableCell>
    </TableRow>
  )
}

function DispatchDetailModal({
  packId,
  file,
  magazines,
  onClose,
}: {
  packId: number
  file: PackDispatchFile | null
  magazines: Magazine[]
  onClose: () => void
}) {
  const qc = useQueryClient()
  const [action, setAction] = useState<'assign_existing' | 'create_magazine'>('assign_existing')
  const [magazineId, setMagazineId] = useState<string>('')
  const [newTitle, setNewTitle] = useState('')
  const [newFrequency, setNewFrequency] = useState('weekly')
  const [newIssn, setNewIssn] = useState('')

  const [editMode, setEditMode] = useState(false)
  const [metaTitle, setMetaTitle] = useState('')
  const [metaSubtitle, setMetaSubtitle] = useState('')
  const [metaPrice, setMetaPrice] = useState('')
  const [metaNumber, setMetaNumber] = useState('')
  const [metaYear, setMetaYear] = useState('')
  const [metaMonth, setMetaMonth] = useState('')
  const [metaDay, setMetaDay] = useState('')
  const [metaIssn, setMetaIssn] = useState('')

  const buildMetadataOverrides = (): PackDispatchMetadataOverrides => {
    const orig = file?.extractedMetadata ?? {}
    const overrides: PackDispatchMetadataOverrides = {}
    const t = metaTitle.trim()
    if (t && t !== (orig.title ?? '')) overrides.title = t
    const s = metaSubtitle.trim()
    if (s !== ((orig as { subtitle?: string }).subtitle ?? '')) overrides.subtitle = s || null
    const p = metaPrice.trim()
    if (p !== ((orig as { price?: string }).price ?? '')) overrides.price = p || null
    const n = metaNumber.trim()
    if (n && Number(n) !== (orig.issue_number ?? null)) overrides.issue_number = Number(n)
    const y = metaYear.trim()
    if (y && Number(y) !== (orig.year ?? null)) overrides.year = Number(y)
    const mo = metaMonth.trim()
    if (mo && Number(mo) !== (orig.month ?? null)) overrides.month = Number(mo)
    const d = metaDay.trim()
    if (d && Number(d) !== (orig.day ?? null)) overrides.day = Number(d)
    const is = metaIssn.trim()
    if (is !== (orig.issn ?? '')) overrides.issn = is || null
    return overrides
  }

  const saveMetadataOnly = useMutation({
    mutationFn: () => {
      if (!file) throw new Error('no file')
      const overrides = buildMetadataOverrides()
      if (Object.keys(overrides).length === 0) throw new Error('Aucun changement')
      return updatePackDispatchMetadata(packId, file.id, overrides)
    },
    onSuccess: () => {
      toast.success('Metadata mises à jour')
      qc.invalidateQueries({ queryKey: ['pack-dispatch', packId] })
      setEditMode(false)
    },
    onError: (e: Error) => toast.error(`Échec : ${e.message}`),
  })

  const resolve = useMutation({
    mutationFn: () => {
      if (!file) throw new Error('no file')
      const overrides = editMode ? buildMetadataOverrides() : undefined
      const withOverrides =
        overrides && Object.keys(overrides).length > 0
          ? { metadataOverrides: overrides }
          : {}
      if (action === 'assign_existing') {
        if (!magazineId) throw new Error('Sélectionne un magazine')
        return resolvePackDispatchFile(packId, file.id, {
          action: 'assign_existing',
          magazineId: Number(magazineId),
          ...withOverrides,
        })
      }
      const title = newTitle.trim()
      if (!title) throw new Error('Titre du nouveau magazine requis')
      return resolvePackDispatchFile(packId, file.id, {
        action: 'create_magazine',
        magazineData: {
          title,
          frequency: newFrequency,
          issn: newIssn.trim() || null,
        },
        ...withOverrides,
      })
    },
    onMutate: () => {
      // Toast persistant — l'import peut prendre 30-60s (IA enrichment,
      // fetch cover, file copy). Sans feedback, le user voit juste un
      // spinner statique.
      toast.loading('Import en cours — peut prendre jusqu\'à 1 minute…', {
        id: `resolve-${file?.id ?? 'x'}`,
      })
    },
    onSuccess: () => {
      toast.success('Import terminé', { id: `resolve-${file?.id ?? 'x'}` })
      qc.invalidateQueries({ queryKey: ['pack-dispatch', packId] })
      qc.invalidateQueries({ queryKey: ['magazines'] })
      qc.invalidateQueries({ queryKey: ['magazines-all'] })
      onClose()
    },
    onError: (e: Error) =>
      toast.error(`Échec : ${e.message}`, { id: `resolve-${file?.id ?? 'x'}` }),
  })

  // Pré-remplit à chaque changement de fichier (useEffect + file.id
  // évite le bug useMemo qui ne trigger pas les setState).
  useEffect(() => {
    if (!file) return
    setEditMode(false)
    const ex = (file.extractedMetadata ?? {}) as {
      title?: string
      subtitle?: string
      price?: string
      issue_number?: number
      year?: number
      month?: number
      day?: number
      issn?: string
    }
    setMetaTitle(ex.title ?? '')
    setMetaSubtitle(ex.subtitle ?? '')
    setMetaPrice(ex.price ?? '')
    setMetaNumber(ex.issue_number != null ? String(ex.issue_number) : '')
    setMetaYear(ex.year != null ? String(ex.year) : '')
    setMetaMonth(ex.month != null ? String(ex.month) : '')
    setMetaDay(ex.day != null ? String(ex.day) : '')
    setMetaIssn(ex.issn ?? '')
    if (file.matchedMagazineId) {
      setAction('assign_existing')
      setMagazineId(String(file.matchedMagazineId))
    } else if (file.proposedMagazineData?.title) {
      setAction('create_magazine')
      setNewTitle(file.proposedMagazineData.title)
      setNewFrequency(file.proposedMagazineData.frequency ?? 'weekly')
      setNewIssn(file.proposedMagazineData.issn ?? '')
    } else {
      setAction('assign_existing')
      setMagazineId('')
      setNewTitle(ex.title ?? '')
    }
  }, [file?.id])

  if (!file) return null

  const ex = file.extractedMetadata
  // Un fichier importé n'est pas actionnable via ce modal — pour le
  // ré-importer il faut passer par le bouton Ré-importer de la row.
  const canResolve = isPending(file.status) || file.status === 'ignored'

  return (
    <Dialog open onOpenChange={(v) => { if (!v) onClose() }}>
      <DialogContent className="sm:max-w-2xl bg-zinc-950 border-zinc-800 max-h-[90vh] flex flex-col">
        <DialogHeader>
          <DialogTitle className="text-zinc-100 flex items-center gap-2">
            <FileText className="size-5 text-purple-400" />
            <span className="truncate">{file.filename}</span>
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4 overflow-y-auto flex-1 pr-1">
          <section className="space-y-2">
            <div className="flex items-center justify-between">
              <div className="text-xs uppercase tracking-wide text-zinc-500">
                {editMode ? 'Édition metadata' : 'Analyse IA'}
              </div>
              {canResolve && (
                <div className="flex items-center gap-1.5">
                  {editMode && (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => saveMetadataOnly.mutate()}
                      disabled={saveMetadataOnly.isPending}
                    >
                      {saveMetadataOnly.isPending ? (
                        <Loader2 className="size-3.5 animate-spin" />
                      ) : (
                        <Check className="size-3.5" />
                      )}
                      Enregistrer
                    </Button>
                  )}
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => setEditMode((v) => !v)}
                  >
                    {editMode ? 'Annuler' : 'Éditer'}
                  </Button>
                </div>
              )}
            </div>
            {editMode ? (
              <div className="rounded border border-zinc-800 bg-zinc-900/40 p-3 grid grid-cols-2 gap-2 text-sm">
                <div className="col-span-2">
                  <MetaEdit label="Titre" value={metaTitle} onChange={setMetaTitle} />
                </div>
                <div className="col-span-2">
                  <MetaEdit label="Sous-titre" value={metaSubtitle} onChange={setMetaSubtitle} />
                </div>
                <MetaEdit label="Numéro" value={metaNumber} onChange={setMetaNumber} numeric />
                <MetaEdit label="Prix" value={metaPrice} onChange={setMetaPrice} placeholder="3,50 €" />
                <MetaEdit label="Année" value={metaYear} onChange={setMetaYear} numeric />
                <MetaEdit label="Mois" value={metaMonth} onChange={setMetaMonth} numeric />
                <MetaEdit label="Jour" value={metaDay} onChange={setMetaDay} numeric />
                <MetaEdit label="ISSN" value={metaIssn} onChange={setMetaIssn} placeholder="1234-5678" />
              </div>
            ) : (
              <div className="rounded border border-zinc-800 bg-zinc-900/40 p-3 grid grid-cols-2 gap-2 text-sm">
                <div className="col-span-2">
                  <Field label="Titre extrait" value={ex?.title} />
                </div>
                {(ex as { subtitle?: string })?.subtitle && (
                  <div className="col-span-2">
                    <Field label="Sous-titre" value={(ex as { subtitle?: string }).subtitle} />
                  </div>
                )}
                <Field label="Numéro" value={ex?.issue_number ?? '—'} />
                <Field label="Prix" value={(ex as { price?: string })?.price ?? '—'} />
                <Field label="Année" value={ex?.year ?? '—'} />
                <Field label="Mois" value={ex?.month ?? '—'} />
                <Field label="Jour" value={ex?.day ?? '—'} />
                <Field label="ISSN" value={ex?.issn ?? '—'} />
                <Field label="Source" value={ex?.source ?? '—'} />
                <Field label="Run IA" value={file.aiRunId ?? '—'} />
              </div>
            )}
            {file.matchedMagazineId && !editMode && (
              <div className="rounded bg-emerald-500/10 border border-emerald-500/30 p-2 text-xs text-emerald-300 flex items-center gap-2 flex-wrap">
                <Check className="size-3.5" />
                Match auto : <strong>{file.matchedMagazineTitle}</strong>{' '}
                ({file.matchSource} · {file.matchScore?.toFixed(0)}%)
                {file.confidence && <ConfidenceBadge value={file.confidence} />}
              </div>
            )}
            {!file.matchedMagazineId && file.confidence && !editMode && (
              <div className="flex items-center gap-2">
                <ConfidenceBadge value={file.confidence} />
                <span className="text-xs text-zinc-500">
                  {file.confidence === 'rejected'
                    ? 'Extraction non fiable — édite les metadata ou ignore'
                    : 'À valider par l’utilisateur'}
                </span>
              </div>
            )}
          </section>

          {canResolve && (
            <section className="space-y-2">
              <div className="text-xs uppercase tracking-wide text-zinc-500">
                Action
              </div>

              <div className="flex flex-wrap gap-2">
                <Button
                  variant={action === 'assign_existing' ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setAction('assign_existing')}
                  className={action === 'assign_existing' ? 'bg-[#7C3AED] hover:bg-[#6D28D9]' : ''}
                >
                  Assigner à un magazine existant
                </Button>
                <Button
                  variant={action === 'create_magazine' ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setAction('create_magazine')}
                  className={action === 'create_magazine' ? 'bg-[#7C3AED] hover:bg-[#6D28D9]' : ''}
                >
                  Créer un nouveau magazine
                </Button>
              </div>

              {action === 'assign_existing' ? (
                <div className="grid gap-1.5">
                  <label className="text-xs text-zinc-400">Magazine cible</label>
                  <Select value={magazineId} onValueChange={setMagazineId}>
                    <SelectTrigger className="bg-zinc-900 border-zinc-700 text-zinc-100">
                      <SelectValue placeholder="— sélectionner —" />
                    </SelectTrigger>
                    <SelectContent className="max-h-[300px]">
                      {magazines.map((m) => (
                        <SelectItem key={m.id} value={String(m.id)}>
                          {m.title}
                          {m.isPlaceholder && ' (placeholder)'}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              ) : (
                <div className="grid gap-2">
                  <div className="grid gap-1.5">
                    <label className="text-xs text-zinc-400">Titre</label>
                    <Input
                      value={newTitle}
                      onChange={(e) => setNewTitle(e.target.value)}
                      className="bg-zinc-900 border-zinc-700 text-zinc-100"
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <div className="grid gap-1.5">
                      <label className="text-xs text-zinc-400">Fréquence</label>
                      <Select value={newFrequency} onValueChange={setNewFrequency}>
                        <SelectTrigger className="bg-zinc-900 border-zinc-700 text-zinc-100">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="daily">Quotidien</SelectItem>
                          <SelectItem value="weekly">Hebdomadaire</SelectItem>
                          <SelectItem value="biweekly">Bimensuel</SelectItem>
                          <SelectItem value="monthly">Mensuel</SelectItem>
                          <SelectItem value="bimonthly">Bimestriel</SelectItem>
                          <SelectItem value="quarterly">Trimestriel</SelectItem>
                          <SelectItem value="annual">Annuel</SelectItem>
                          <SelectItem value="irregular">Irrégulier</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="grid gap-1.5">
                      <label className="text-xs text-zinc-400">ISSN</label>
                      <Input
                        value={newIssn}
                        onChange={(e) => setNewIssn(e.target.value)}
                        placeholder="1234-5678"
                        className="bg-zinc-900 border-zinc-700 text-zinc-100 font-mono"
                      />
                    </div>
                  </div>
                  <p className="text-xs text-zinc-500">
                    Root folder et quality profile sont hérités du pack.
                  </p>
                </div>
              )}
            </section>
          )}

          <section className="space-y-1 text-xs text-zinc-500">
            <div className="flex items-center gap-1.5">
              <Clock className="size-3" />
              Créé : {new Date(file.createdAt).toLocaleString()}
            </div>
            {file.analyzedAt && (
              <div className="flex items-center gap-1.5">
                <ChevronDown className="size-3" />
                Analysé : {new Date(file.analyzedAt).toLocaleString()}
              </div>
            )}
            {file.resolvedAt && (
              <div className="flex items-center gap-1.5">
                <Check className="size-3" />
                Résolu : {new Date(file.resolvedAt).toLocaleString()}
              </div>
            )}
          </section>
        </div>

        <DialogFooter className="pt-4 border-t border-zinc-800">
          <Button variant="outline" onClick={onClose}>
            Fermer
          </Button>
          {canResolve && (
            <Button
              onClick={() => resolve.mutate()}
              disabled={resolve.isPending}
              className="bg-[#7C3AED] hover:bg-[#6D28D9]"
            >
              {resolve.isPending ? (
                <Loader2 className="size-3.5 animate-spin" />
              ) : (
                <Check className="size-3.5" />
              )}
              Valider
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function Field({ label, value }: { label: string; value: unknown }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wide text-zinc-500">{label}</div>
      <div className="text-zinc-200 truncate">
        {value === '' || value == null ? '—' : String(value)}
      </div>
    </div>
  )
}

function ConfidenceBadge({ value }: { value: 'confirmed' | 'doubt' | 'rejected' }) {
  const cfg = {
    confirmed: {
      Icon: ShieldCheck,
      cls: 'text-emerald-400',
      title: 'Confirmé — extraction fiable',
    },
    doubt: {
      Icon: ShieldAlert,
      cls: 'text-amber-400',
      title: 'Doute — à valider',
    },
    rejected: {
      Icon: ShieldX,
      cls: 'text-red-400',
      title: 'Rejeté — extraction non fiable',
    },
  }[value]
  const { Icon } = cfg
  return (
    <span title={cfg.title} className="inline-flex">
      <Icon className={`size-4 ${cfg.cls}`} strokeWidth={2.25} />
    </span>
  )
}

function MetaEdit({
  label,
  value,
  onChange,
  numeric,
  placeholder,
}: {
  label: string
  value: string
  onChange: (v: string) => void
  numeric?: boolean
  placeholder?: string
}) {
  return (
    <div>
      <label className="text-[10px] uppercase tracking-wide text-zinc-500">{label}</label>
      <Input
        value={value}
        onChange={(e) => {
          const v = e.target.value
          if (numeric) {
            if (v === '' || /^\d+$/.test(v)) onChange(v)
          } else {
            onChange(v)
          }
        }}
        placeholder={placeholder}
        className="h-7 bg-zinc-900 border-zinc-700 text-zinc-100 text-sm"
      />
    </div>
  )
}
