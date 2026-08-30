import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { Eye, EyeOff, Trash2, Search, Loader2, Download, RefreshCw, Pencil, Import, BookOpen, Clock, Sparkles, AlertTriangle, Package, ExternalLink } from 'lucide-react'

import { type Issue } from '@/api/issues'
import { type QueueEntry } from '@/api/queue'
import { StatusBadge } from '@/components/StatusBadge'
import { Button } from '@/components/ui/button'
import {
  TableCell,
  TableRow,
} from '@/components/ui/table'

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(1024))
  return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${units[i]}`
}

function formatSpeed(bytesPerSecond: number): string {
  if (bytesPerSecond === 0) return ''
  return `${formatBytes(bytesPerSecond)}/s`
}

export interface DeducedFields {
  deducedNumber?: number
  deducedYear?: number
  deducedMonth?: number
}

/** Signal d'incohérence entre le numéro DÉCLARÉ de l'issue et
 *  celui attendu par interpolation des voisins par date. Passé quand
 *  |declared - expected| dépasse une tolérance (voir MagazineDetail
 *  ~ detectNumberIncoherences). L'UI affiche le numéro en orange +
 *  icône ⚠ + tooltip "attendu ~N (interpolé depuis voisins)". */
export interface NumberIncoherence {
  expected: number
  reason: string
}

interface IssueRowProps {
  issue: Issue
  selected: boolean
  queueItem?: QueueEntry
  deduced?: DeducedFields
  numberIncoherence?: NumberIncoherence
  /** Weekdays (0=Lun..6=Dim) qui se regroupent en 1 issue weekend.
   *  Passé du magazine pour calculer le range de dates couvert par
   *  cette issue (ex Le Monde Sam+Dim+Lun → issue affichée
   *  "Sam 15 → Lun 17/08"). */
  weekendDays?: number[]
  onSelect: (id: number, checked: boolean) => void
  onToggleMonitor: (id: number, monitored: boolean) => void
  onEdit: (issue: Issue) => void
  onDeleteFile: (id: number) => void
  onSearch: (id: number) => void
  /** Bouton "Recherche auto" (pipeline unifié Prowlarr + IA + rules + auto-grab).
   *  Optionnel — non affiché si absent (backward compat pour usages
   *  hors magazine detail). */
  onWantedSearch?: (id: number) => void
  onRefresh: (id: number) => void
  onImport?: (id: number) => void
  onView?: (id: number) => void
  onHistory?: (id: number) => void
  refreshingId?: number | null
  importingId?: number | null
}

export function IssueRow({
  issue,
  selected,
  queueItem,
  deduced,
  numberIncoherence,
  weekendDays,
  onSelect,
  onToggleMonitor,
  onEdit,
  onDeleteFile,
  onSearch,
  onWantedSearch,
  onRefresh,
  onImport,
  onView,
  onHistory,
  refreshingId,
  importingId,
}: IssueRowProps) {
  const { t } = useTranslation()

  const hasRealNumber = issue.number !== null
  const hasRealDate = !!(issue.year || issue.publicationDate)

  const displayNumber = issue.isSpecial
    ? t('issues.special')
    : hasRealNumber
      ? `#${issue.number}`
      : deduced?.deducedNumber != null
        ? `#${deduced.deducedNumber}`
        : '-'

  const isNumberDeduced = !hasRealNumber && deduced?.deducedNumber != null

  const displayDate = issue.year
    ? issue.month
      ? issue.day
        ? `${String(issue.day).padStart(2, '0')}/${String(issue.month).padStart(2, '0')}/${issue.year}`
        : `${String(issue.month).padStart(2, '0')}/${issue.year}`
      : String(issue.year)
    : issue.publicationDate
      ? new Date(issue.publicationDate).toLocaleDateString()
      : deduced?.deducedYear != null
        ? deduced.deducedMonth != null
          ? `${String(deduced.deducedMonth).padStart(2, '0')}/${deduced.deducedYear}`
          : String(deduced.deducedYear)
        : '-'

  const isDateDeduced = !hasRealDate && deduced?.deducedYear != null

  // Détection issue weekend combinée : reconstitue toutes les dates
  // couvertes par le groupe (weekdays consécutifs dans weekend_days).
  // Ex Le Monde weekend_days=[5,6,0], issue publiée Lun 17/08 →
  // dates = [Sam 15/08, Dim 16/08, Lun 17/08]. Peut faire 2, 3, ou
  // plus de jours selon la config du magazine.
  const jsToIsoWd = (d: Date) => (d.getDay() === 0 ? 6 : d.getDay() - 1)
  let weekendDates: Date[] | null = null
  if (weekendDays && weekendDays.length > 0 && issue.year && issue.month && issue.day) {
    const to = new Date(issue.year, issue.month - 1, issue.day)
    if (weekendDays.includes(jsToIsoWd(to))) {
      const collected: Date[] = [to]
      let cur = new Date(to)
      // Recule tant que la veille est dans weekend_days et qu'on
      // reste dans la même semaine glissante (< 7 jours du dernier).
      while (true) {
        const prev = new Date(cur)
        prev.setDate(prev.getDate() - 1)
        if (
          weekendDays.includes(jsToIsoWd(prev)) &&
          (to.getTime() - prev.getTime()) < 7 * 24 * 3600 * 1000
        ) {
          collected.unshift(prev)
          cur = prev
        } else break
      }
      if (collected.length >= 2) weekendDates = collected
    }
  }

  const WEEKDAY_LABELS_SHORT = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim']
  const formatDayLine = (d: Date) => {
    const wd = WEEKDAY_LABELS_SHORT[jsToIsoWd(d)]
    return `${wd} ${String(d.getDate()).padStart(2, '0')}/${String(d.getMonth() + 1).padStart(2, '0')}/${d.getFullYear()}`
  }

  // Type d'issue : HS (hors-série), weekend (édition combinée), régulier.
  const issueTypeLabel = issue.isSpecial
    ? { label: 'HS', cls: 'bg-amber-500/15 text-amber-200 border-amber-500/30', title: 'Hors-série' }
    : weekendDates
      ? { label: `Weekend (${weekendDates.length}j)`, cls: 'bg-purple-500/15 text-purple-200 border-purple-500/30', title: 'Édition weekend combinée' }
      : { label: 'Régulier', cls: 'bg-zinc-800 text-zinc-400 border-zinc-700', title: 'Édition régulière' }

  // Queue progress
  const isInQueue = !!queueItem
  const queueProgress = queueItem
    ? queueItem.size > 0
      ? Math.round(((queueItem.size - queueItem.sizeLeft) / queueItem.size) * 100)
      : 0
    : 0

  return (
    <TableRow className="border-zinc-800 hover:bg-zinc-900/50">
      <TableCell className="w-10">
        <input
          type="checkbox"
          checked={selected}
          onChange={(e) => onSelect(issue.id, e.target.checked)}
          className="size-4 rounded border-zinc-600 bg-zinc-900 text-[#7C3AED] focus:ring-[#7C3AED] accent-[#7C3AED]"
        />
      </TableCell>
      <TableCell
        className={`font-medium ${
          numberIncoherence
            ? 'text-orange-500'
            : isNumberDeduced
              ? 'text-amber-400 italic'
              : 'text-zinc-100'
        }`}
        title={
          numberIncoherence
            ? `Numéro suspect — ${numberIncoherence.reason}. Attendu ~${numberIncoherence.expected}.`
            : undefined
        }
      >
        <span className="inline-flex items-center gap-1">
          {displayNumber}
          {numberIncoherence && (
            <AlertTriangle className="size-3.5 text-orange-500 shrink-0" />
          )}
        </span>
        {numberIncoherence && (
          <div className="text-[10px] text-orange-400/80 font-normal italic">
            attendu ~{numberIncoherence.expected}
          </div>
        )}
      </TableCell>
      {/* Colonne Date — pour un weekend combiné, stack toutes les
           dates du groupe verticalement (2, 3, ou plus selon config). */}
      <TableCell className={isDateDeduced ? 'text-amber-400 italic' : 'text-zinc-400'}>
        {weekendDates ? (
          <div className="flex flex-col gap-0.5 text-xs text-zinc-300 leading-tight">
            {weekendDates.map((d, i) => (
              <span key={i}>{formatDayLine(d)}</span>
            ))}
          </div>
        ) : (
          displayDate
        )}
      </TableCell>
      {/* Colonne Type — HS / Weekend / Régulier */}
      <TableCell>
        <span
          className={`inline-flex items-center rounded border text-[10px] px-1.5 py-0.5 whitespace-nowrap ${issueTypeLabel.cls}`}
          title={issueTypeLabel.title}
        >
          {issueTypeLabel.label}
        </span>
      </TableCell>
      <TableCell>
        {issue.title && (
          <div className="text-zinc-300 text-sm truncate max-w-[240px]" title={issue.title}>
            {issue.title}
          </div>
        )}
        {issue.subtitle && (
          <div
            className="text-zinc-500 text-xs italic truncate max-w-[240px]"
            title={issue.subtitle}
          >
            {issue.subtitle}
          </div>
        )}
      </TableCell>
      <TableCell className="text-zinc-400 text-xs whitespace-nowrap">
        {issue.price ? issue.price : <span className="text-zinc-700">—</span>}
      </TableCell>
      <TableCell className="font-mono text-xs text-zinc-400">
        {issue.issn ? issue.issn : <span className="text-zinc-700">—</span>}
      </TableCell>
      <TableCell>
        {isInQueue ? (
          <div className="flex flex-col gap-1">
            <div className="flex items-center gap-1.5">
              <Loader2 className="size-3 animate-spin text-[#7C3AED]" />
              <StatusBadge status={queueItem.status} tKey={`queue.status_${queueItem.status}`} className="border border-[#7C3AED] !bg-transparent !text-[#7C3AED]" />
            </div>
            {/* Progress bar */}
            <div className="flex items-center gap-2">
              <div className="flex-1 h-1 rounded-full bg-zinc-800 overflow-hidden max-w-[120px]">
                <div
                  className="h-full rounded-full bg-[#7C3AED] transition-all"
                  style={{ width: `${queueProgress}%` }}
                />
              </div>
              <span className="text-[10px] text-zinc-500">{queueProgress}%</span>
              {queueItem.speed > 0 && (
                <span className="text-[10px] text-zinc-500">{formatSpeed(queueItem.speed)}</span>
              )}
            </div>
          </div>
        ) : (
          <StatusBadge status={issue.status} />
        )}
      </TableCell>
      {/* Colonne File — format/quality/size uniquement (source déportée). */}
      <TableCell className="text-zinc-400 text-sm">
        {issue.file ? (
          <div className="flex items-center gap-2 flex-wrap">
            <span className="uppercase text-zinc-300">{issue.file.format}</span>
            {issue.file.quality && issue.file.quality !== 'unknown' && (
              <>
                <span className="text-zinc-500">|</span>
                <span>{issue.file.quality}</span>
              </>
            )}
            <span className="text-zinc-500">|</span>
            <span>{formatBytes(issue.file.size)}</span>
            {issue.file.releaseGroup && (
              <>
                <span className="text-zinc-500">|</span>
                <span className="text-zinc-500">{issue.file.releaseGroup}</span>
              </>
            )}
          </div>
        ) : isInQueue ? (
          <span className="text-zinc-500 text-xs">
            {queueItem.downloadClient}
            {queueItem.size > 0 && ` — ${formatBytes(queueItem.size)}`}
          </span>
        ) : (
          <span className="text-zinc-600">{t('issues.noFile')}</span>
        )}
      </TableCell>
      {/* Colonne Source — badge type (Pack violet / Torrent ambre) +
           nom court + lien cliquable (pack → sa page, torrent → détail
           fiche technique). Détails complets dans le crayon. */}
      <TableCell className="text-sm">
        {issue.file ? (
          issue.file.sourceType === 'pack' && issue.file.sourcePackId ? (
            <Link
              to={`/pack/${issue.file.sourcePackId}`}
              className="inline-flex items-center gap-1.5 rounded border border-fuchsia-500/30 bg-fuchsia-500/10 hover:bg-fuchsia-500/20 text-fuchsia-200 px-2 py-1 text-xs max-w-[220px]"
              title={`Pack : ${issue.file.sourcePackName ?? '?'} — fichier : ${issue.file.originalFilename}`}
            >
              <Package className="size-3 shrink-0" />
              <span className="truncate">
                {issue.file.sourcePackName ?? 'Pack'}
              </span>
              <ExternalLink className="size-2.5 shrink-0 opacity-60" />
            </Link>
          ) : (
            <span
              className="inline-flex items-center gap-1.5 rounded border border-amber-500/30 bg-amber-500/10 text-amber-200 px-2 py-1 text-xs max-w-[220px]"
              title={
                issue.file.sourceReleaseTitle
                  ? `Torrent : ${issue.file.sourceReleaseTitle}`
                  : `Fichier : ${issue.file.originalFilename}`
              }
            >
              <Download className="size-3 shrink-0" />
              <span className="truncate">
                {issue.file.sourceReleaseTitle ?? issue.file.originalFilename}
              </span>
            </span>
          )
        ) : (
          <span className="text-zinc-600 text-xs">—</span>
        )}
      </TableCell>
      <TableCell>
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon-xs"
            onClick={() => onToggleMonitor(issue.id, !issue.monitored)}
            title={issue.monitored ? t('issues.unmonitor') : t('issues.monitor')}
          >
            {issue.monitored ? (
              <Eye className="size-3.5 text-[#7C3AED]" />
            ) : (
              <EyeOff className="size-3.5 text-zinc-500" />
            )}
          </Button>
          <Button
            variant="ghost"
            size="icon-xs"
            onClick={() => onEdit(issue)}
            title={t('issues.editIssue')}
          >
            <Pencil className="size-3.5 text-zinc-400" />
          </Button>
          {issue.status === 'snatched' && onImport && (
            <Button
              variant="ghost"
              size="icon-xs"
              onClick={() => onImport(issue.id)}
              disabled={importingId === issue.id}
              title={t('issues.importDownload')}
            >
              <Import className={`size-3.5 text-[#7C3AED] ${importingId === issue.id ? 'animate-pulse' : ''}`} />
            </Button>
          )}
          <Button
            variant="ghost"
            size="icon-xs"
            onClick={() => onSearch(issue.id)}
            title={t('issues.searchRelease')}
          >
            <Search className="size-3.5 text-zinc-400" />
          </Button>
          {onWantedSearch && (
            <Button
              variant="ghost"
              size="icon-xs"
              onClick={() => onWantedSearch(issue.id)}
              title="Recherche auto (Prowlarr + IA + rules + auto-grab si winner fort)"
            >
              <Sparkles className="size-3.5 text-purple-400" />
            </Button>
          )}
          <Button
            variant="ghost"
            size="icon-xs"
            onClick={() => onRefresh(issue.id)}
            disabled={refreshingId === issue.id}
            title={t('issues.refreshIssue')}
          >
            <RefreshCw className={`size-3.5 text-zinc-400 ${refreshingId === issue.id ? 'animate-spin' : ''}`} />
          </Button>
          {onHistory && (
            <Button
              variant="ghost"
              size="icon-xs"
              onClick={() => onHistory(issue.id)}
              title={t('issues.viewHistory')}
            >
              <Clock className="size-3.5 text-zinc-400" />
            </Button>
          )}
          {issue.file && onView && (
            <Button
              variant="ghost"
              size="icon-xs"
              onClick={() => onView(issue.id)}
              title={t('issues.viewIssue')}
            >
              <BookOpen className="size-3.5 text-zinc-400" />
            </Button>
          )}
          {issue.file && (
            <Button
              variant="ghost"
              size="icon-xs"
              onClick={() => window.open(`/api/v1/issue/${issue.id}/file`, '_blank')}
              title={t('issues.downloadFile')}
            >
              <Download className="size-3.5 text-zinc-400" />
            </Button>
          )}
          <Button
            variant="ghost"
            size="icon-xs"
            onClick={() => onDeleteFile(issue.id)}
            title={t('issues.deleteFile')}
          >
            <Trash2 className="size-3.5 text-destructive" />
          </Button>
        </div>
      </TableCell>
    </TableRow>
  )
}
