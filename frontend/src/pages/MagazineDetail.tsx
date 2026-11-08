import { Fragment, useState, useMemo, useCallback, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Eye,
  EyeOff,
  Download,
  Loader2,
  RefreshCw,
  Pencil,
  Trash2,
  Search,
  HelpCircle,
  CheckCircle2,
  ArrowDownUp,
  ArrowUp,
  ArrowDown,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Upload,
  Plus,
  X,
  Check,
  FolderOpen,
  Ban,
  Sparkles,
  ExternalLink,
} from 'lucide-react'
import { toast } from 'sonner'

import {
  getMagazine,
  getMagazineCoverUrl,
  updateMagazine,
  uploadMagazineCover,
  deleteMagazine,
  refreshMetadata,
  searchWantedMagazine,
  resyncMagazineIssues,
  addMagazinePattern,
  updateMagazinePattern,
  deleteMagazinePattern,
  convertPatternToExcludeRule,
  addMagazineRule,
  updateMagazineRule,
  deleteMagazineRule,
  type Magazine,
} from '@/api/magazines'
import {
  getIssues,
  getIssueCoverUrl,
  updateIssueMonitored,
  updateIssue,
  batchMonitor,
  deleteIssueFile,
  deleteIssue,
  refreshIssue,
  triggerIssueImport,
  type Issue,
  type IssueUpdate,
} from '@/api/issues'
import {
  searchIssue,
  searchIndexers,
  grabRelease,
  searchInternetArchive,
  downloadFromIA,
  searchAnnasArchive,
  downloadFromAA,
  scanMagazineSceneReleases,
  grabMagazineSceneRelease,
  type SearchResult,
  type MagazineRelease,
} from '@/api/search'
import { getProfiles } from '@/api/quality'
import { getRootFolders } from '@/api/system'
import { IssueRow } from '@/components/IssueRow'
import { IssueViewer } from '@/components/IssueViewer'
import { HistoryModal } from '@/components/HistoryModal'
import { WantedSearchNowModal } from '@/components/WantedSearchNowModal'
import { IssueGroupsEditor } from '@/components/IssueGroupsEditor'
import { IssueTechnicalDetail } from '@/components/IssueTechnicalDetail'
import { shortenPath } from '@/lib/utils'
import { FileManagerModal } from '@/components/FileManagerModal'
import { AIRefreshModal } from '@/components/AIRefreshModal'
import { MagazineActivitiesPanel } from '@/components/MagazineActivitiesPanel'
import { HistoryList } from '@/components/HistoryList'
import { listActivities } from '@/api/activity'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Switch } from '@/components/ui/switch'
import { Skeleton } from '@/components/ui/skeleton'
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
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from '@/components/ui/tabs'
import { useWebSocket } from '@/hooks/useWebSocket'
import { useQueue } from '@/hooks/useQueue'

const RESULTS_PER_PAGE = 50

type StatusFilter = 'all' | 'available' | 'wanted' | 'upcoming'

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(1024))
  return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${units[i]}`
}

function formatPublishDate(iso: string): string {
  const d = new Date(iso)
  if (isNaN(d.getTime())) return iso
  return d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
}

const SCENE_SOURCE_LABELS: Record<string, string> = {
  bookys: 'Bookys',
  telecharger_magazines: 'tm.org',
}

function sortScene(rows: MagazineRelease[], dir: 'asc' | 'desc'): MagazineRelease[] {
  const time = (r: MagazineRelease) =>
    r.publishedAt ? new Date(r.publishedAt).getTime() : r.year ? new Date(r.year, 0).getTime() : 0
  return [...rows].sort((a, b) => (dir === 'asc' ? time(a) - time(b) : time(b) - time(a)))
}

function sortByDate(results: SearchResult[], dir: 'asc' | 'desc'): SearchResult[] {
  return [...results].sort((a, b) => {
    const ta = a.publishDate ? new Date(a.publishDate).getTime() : 0
    const tb = b.publishDate ? new Date(b.publishDate).getTime() : 0
    return dir === 'asc' ? ta - tb : tb - ta
  })
}

export default function MagazineDetail() {
  const { id } = useParams<{ id: string }>()
  const magazineId = Number(id)
  const { t } = useTranslation()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all')
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set())
  const [searchDialogOpen, setSearchDialogOpen] = useState(false)
  const [searchingIssueId, setSearchingIssueId] = useState<number | null>(null)
  const [searchResults, setSearchResults] = useState<SearchResult[]>([])
  const [searching, setSearching] = useState(false)
  const [grabbing, setGrabbing] = useState<string | null>(null)

  // Edit modal state
  const [editOpen, setEditOpen] = useState(false)
  const [editTitle, setEditTitle] = useState('')
  const [editMonitored, setEditMonitored] = useState(true)
  const [editWantedSearchEnabled, setEditWantedSearchEnabled] = useState(true)
  const [editWeekendDays, setEditWeekendDays] = useState<number[]>([])
  const [editIssueGroups, setEditIssueGroups] = useState<
    { days: number[]; type: 'regular' | 'weekend' | 'special'; label: string | null }[]
  >([])
  const [editSortByRecent, setEditSortByRecent] = useState(true)
  const [editMinTitleOverride, setEditMinTitleOverride] = useState<string>('')
  const [editAutoGrabThresholdOverride, setEditAutoGrabThresholdOverride] = useState<string>('')
  const [editQualityProfileId, setEditQualityProfileId] = useState('')
  const [editRootFolderPath, setEditRootFolderPath] = useState('')
  const [editFrequency, setEditFrequency] = useState('monthly')
  const [editMonitoringStartDate, setEditMonitoringStartDate] = useState('')
  const [editExcludedDays, setEditExcludedDays] = useState<number[]>([])
  const [editReleaseWeekday, setEditReleaseWeekday] = useState<number | null>(null)
  const [editUseLatestCover, setEditUseLatestCover] = useState(false)
  const [editCoverIssueId, setEditCoverIssueId] = useState<number | null>(null)
  const [editIssn, setEditIssn] = useState('')
  const [coverUrl, setCoverUrl] = useState('')
  const [coverUploading, setCoverUploading] = useState(false)
  const coverFileRef = useRef<HTMLInputElement>(null)

  // Delete modal state (magazine)
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [deleteFiles, setDeleteFiles] = useState(false)

  // Delete file dialog state (issue)
  const [deleteFileOpen, setDeleteFileOpen] = useState(false)
  const [deleteFileIssueId, setDeleteFileIssueId] = useState<number | null>(null)

  // Edit issue dialog state
  const [editIssueOpen, setEditIssueOpen] = useState(false)
  const [editingIssue, setEditingIssue] = useState<Issue | null>(null)
  const [editIssueNumber, setEditIssueNumber] = useState('')
  const [editIssueVolume, setEditIssueVolume] = useState('')
  const [editIssueTitle, setEditIssueTitle] = useState('')
  const [editIssueSubtitle, setEditIssueSubtitle] = useState('')
  const [editIssuePrice, setEditIssuePrice] = useState('')
  const [editIssueIssn, setEditIssueIssn] = useState('')
  const [editIssueYear, setEditIssueYear] = useState('')
  const [editIssueMonth, setEditIssueMonth] = useState('')
  const [editIssueDay, setEditIssueDay] = useState('')
  const [editIssueSpecial, setEditIssueSpecial] = useState(false)
  const [editIssueStatus, setEditIssueStatus] = useState('')
  const [editIssueQuality, setEditIssueQuality] = useState('')
  const [editIssueFormat, setEditIssueFormat] = useState('')
  const [editIssueReleaseGroup, setEditIssueReleaseGroup] = useState('')
  const [editIssueLanguage, setEditIssueLanguage] = useState('')
  const [editIssueFilename, setEditIssueFilename] = useState('')

  // Collapse upcoming issues per year group
  const [expandedUpcoming, setExpandedUpcoming] = useState<Set<string>>(new Set())

  // Sort state pour la table issues.
  // Défaut : date décroissante (issue la plus récente en haut).
  //
  // Le tri s'applique dans chaque groupe année ET aux upcoming
  // (les deux sub-lists rendues par year). Les groupes d'années restent
  // toujours triés desc au niveau supérieur — c'est la structure du
  // grouping, pas le tri des rows.
  const [issueSortKey, setIssueSortKey] = useState<IssueSortKey>('date')
  const [issueSortDir, setIssueSortDir] = useState<IssueSortDir>('desc')

  const toggleIssueSort = (key: IssueSortKey) => {
    if (issueSortKey === key) {
      setIssueSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setIssueSortKey(key)
      // Nouveau critère : commencer par desc pour date/numéro (récent
      // en haut), asc pour title (A-Z lisible).
      setIssueSortDir(key === 'title' ? 'asc' : 'desc')
    }
  }

  // Refreshing state
  const [refreshing, setRefreshing] = useState(false)
  const [refreshingIssueId, setRefreshingIssueId] = useState<number | null>(null)
  const [aiRefreshOpen, setAiRefreshOpen] = useState(false)
  const [importingIssueId, setImportingIssueId] = useState<number | null>(null)

  // Viewer state
  const [viewerOpen, setViewerOpen] = useState(false)
  const [viewerIssueId, setViewerIssueId] = useState<number | null>(null)

  // History modals
  const [historyMagazineOpen, setHistoryMagazineOpen] = useState(false)
  const [historyIssueOpen, setHistoryIssueOpen] = useState(false)
  const [historyIssueId, setHistoryIssueId] = useState<number | null>(null)

  // "Recherche maintenant" (wanted_search pipeline) — modal ouvert par
  // le bouton Sparkles sur les issue rows. Contient le breakdown pipeline
  // (WantedSearchDetail) chargé en direct via POST /search/wanted/{id}.
  const [wantedSearchIssueId, setWantedSearchIssueId] = useState<number | null>(null)

  // Manual Grab confirmation modal — opened before the actual download
  // so the operator can bind the release to a specific issue / date,
  // overriding the parser-based auto-attribution.
  const [grabConfirm, setGrabConfirm] = useState<SearchResult | null>(null)

  // Manual Research modal state
  const [manualSearchOpen, setManualSearchOpen] = useState(false)
  const [manualSearchQuery, setManualSearchQuery] = useState('')
  const [manualSearchTab, setManualSearchTab] = useState('annasarchive')
  const [manualSearchResults, setManualSearchResults] = useState<SearchResult[]>([])
  const [manualSearching, setManualSearching] = useState(false)
  const [manualSearchPage, setManualSearchPage] = useState(1)
  const [manualSearchSourceFilter, setManualSearchSourceFilter] = useState('')
  const [manualSearchDateSort, setManualSearchDateSort] = useState<'' | 'asc' | 'desc'>('')
  // Silent hit-count for each free-text tab, populated by a
  // background probe on every submit so the operator sees which
  // source actually has data without switching tabs blindly.
  // null = not probed yet (or in-flight).
  const [manualSearchCounts, setManualSearchCounts] = useState<
    Record<string, number | null>
  >({ annasarchive: null, internetarchive: null, indexers: null })
  // Scene magazine indexer state (Bookys + tm.org). Distinct
  // from the SearchResult-shaped tabs above because the row
  // model is different (hoster_links array, status lifecycle,
  // dispatched via JD2 folder-watch instead of qBit / nzbget).
  const [sceneResults, setSceneResults] = useState<MagazineRelease[]>([])
  const [sceneGrabbing, setSceneGrabbing] = useState<Set<number>>(new Set())
  const [searchPage, setSearchPage] = useState(1)
  const [searchSourceFilter, setSearchSourceFilter] = useState('')
  const [searchDateSort, setSearchDateSort] = useState<'' | 'asc' | 'desc'>('')

  // File manager modal state
  const [fileManagerOpen, setFileManagerOpen] = useState(false)

  const { data: magazine, isLoading: magazineLoading } = useQuery({
    queryKey: ['magazine', magazineId],
    queryFn: () => getMagazine(magazineId),
    enabled: !isNaN(magazineId),
  })

  const { data: issues = [], isLoading: issuesLoading } = useQuery({
    queryKey: ['issues', magazineId],
    queryFn: () => getIssues(magazineId),
    enabled: !isNaN(magazineId),
  })

  // Compteur d'activités en cours pour ce magazine — alimente le
  // badge de l'onglet « Activités » (pulsation violet quand > 0).
  const { data: liveActivities = [] } = useQuery({
    queryKey: ['magazine-activities-running', magazineId],
    queryFn: () => listActivities({ magazineId, status: 'running', limit: 20 }),
    enabled: !isNaN(magazineId),
    refetchInterval: 5000,
    refetchIntervalInBackground: false,
  })
  const activityRunningCount = liveActivities.filter(
    (a) => a.status === 'running' || a.status === 'queued',
  ).length

  const { data: profiles = [] } = useQuery({
    queryKey: ['qualityProfiles'],
    queryFn: getProfiles,
  })

  const { data: rootFolders = [] } = useQuery({
    queryKey: ['rootFolders'],
    queryFn: getRootFolders,
  })

  // Queue data for showing download status on issues
  const { queue } = useQueue()
  const queueByIssueId = useMemo(() => {
    const map = new Map<number, (typeof queue)[number]>()
    for (const item of queue) {
      if (item.issueId && item.magazineId === magazineId) {
        map.set(item.issueId, item)
      }
    }
    return map
  }, [queue, magazineId])

  const isLoading = magazineLoading || issuesLoading

  const invalidateIssues = useCallback(
    () => queryClient.invalidateQueries({ queryKey: ['issues', magazineId] }),
    [queryClient, magazineId],
  )

  const invalidateMagazine = useCallback(
    () => queryClient.invalidateQueries({ queryKey: ['magazine', magazineId] }),
    [queryClient, magazineId],
  )

  // Auto-refresh when backend finishes an import (library:updated event)
  const { on } = useWebSocket()
  useEffect(() => {
    const unsub = on('library:updated', () => {
      invalidateIssues()
      invalidateMagazine()
    })
    return unsub
  }, [on, invalidateIssues, invalidateMagazine])

  const monitorMutation = useMutation({
    mutationFn: ({ issueId, monitored }: { issueId: number; monitored: boolean }) =>
      updateIssueMonitored(issueId, monitored),
    onSuccess: () => invalidateIssues(),
    onError: () => toast.error(t('issues.monitorError')),
  })

  const batchMonitorMutation = useMutation({
    mutationFn: ({ issueIds, monitored }: { issueIds: number[]; monitored: boolean }) =>
      batchMonitor(issueIds, monitored),
    onSuccess: () => {
      invalidateIssues()
      setSelectedIds(new Set())
      toast.success(t('issues.batchUpdated'))
    },
    onError: () => toast.error(t('issues.batchError')),
  })

  const deleteFileMutation = useMutation({
    mutationFn: ({ issueId, unmonitor }: { issueId: number; unmonitor: boolean }) =>
      deleteIssueFile(issueId, unmonitor),
    onSuccess: () => {
      invalidateIssues()
      setDeleteFileOpen(false)
      setDeleteFileIssueId(null)
      toast.success(t('issues.fileDeleted'))
    },
    onError: () => toast.error(t('issues.deleteFileError')),
  })

  const deleteIssueMutation = useMutation({
    mutationFn: (issueId: number) => deleteIssue(issueId),
    onSuccess: () => {
      invalidateIssues()
      setDeleteFileOpen(false)
      setDeleteFileIssueId(null)
      toast.success(t('issues.fileDeleted'))
    },
    onError: () => toast.error(t('issues.deleteFileError')),
  })

  const updateIssueMutation = useMutation({
    mutationFn: ({ issueId, data }: { issueId: number; data: IssueUpdate }) =>
      updateIssue(issueId, data),
    onSuccess: () => {
      invalidateIssues()
      setEditIssueOpen(false)
      setEditingIssue(null)
      toast.success(t('issues.issueUpdated'))
    },
    onError: (err: unknown) => {
      const status = (err as { status?: number })?.status
      toast.error(status === 409 ? t('issues.issueNumberConflict') : t('issues.issueUpdateError'))
    },
  })

  const handleEditIssue = (issue: Issue) => {
    setEditingIssue(issue)
    setEditIssueNumber(issue.number != null ? String(issue.number) : '')
    setEditIssueVolume(issue.volume != null ? String(issue.volume) : '')
    setEditIssueTitle(issue.title ?? '')
    setEditIssueSubtitle(issue.subtitle ?? '')
    setEditIssuePrice(issue.price ?? '')
    setEditIssueIssn(issue.issn ?? '')
    setEditIssueYear(issue.year != null ? String(issue.year) : '')
    setEditIssueMonth(issue.month != null ? String(issue.month) : '')
    setEditIssueDay(issue.day != null ? String(issue.day) : '')
    setEditIssueSpecial(issue.isSpecial)
    setEditIssueStatus(issue.status)
    setEditIssueQuality(issue.file?.quality ?? '')
    setEditIssueFormat(issue.file?.format ?? '')
    setEditIssueReleaseGroup(issue.file?.releaseGroup ?? '')
    setEditIssueLanguage(issue.file?.language ?? '')
    setEditIssueFilename(issue.file?.path.split('/').pop() ?? '')
    setEditIssueOpen(true)
  }

  const handleSaveIssue = () => {
    if (!editingIssue) return
    const data: IssueUpdate = {}
    const num = editIssueNumber.trim() ? parseInt(editIssueNumber) : null
    const vol = editIssueVolume.trim() ? parseInt(editIssueVolume) : null
    const yr = editIssueYear.trim() ? parseInt(editIssueYear) : null
    const mo = editIssueMonth.trim() ? parseInt(editIssueMonth) : null
    const dy = editIssueDay.trim() ? parseInt(editIssueDay) : null

    if (num !== editingIssue.number) data.number = num
    if (vol !== editingIssue.volume) data.volume = vol
    if ((editIssueTitle || null) !== editingIssue.title) data.title = editIssueTitle || null
    if ((editIssueSubtitle || null) !== editingIssue.subtitle) data.subtitle = editIssueSubtitle || null
    if ((editIssuePrice || null) !== editingIssue.price) data.price = editIssuePrice || null
    if ((editIssueIssn || null) !== editingIssue.issn) data.issn = editIssueIssn || null
    if (yr !== editingIssue.year) data.year = yr
    if (mo !== editingIssue.month) data.month = mo
    if (dy !== editingIssue.day) data.day = dy
    if (editIssueSpecial !== editingIssue.isSpecial) data.isSpecial = editIssueSpecial
    if (editIssueStatus !== editingIssue.status) data.status = editIssueStatus

    if (editingIssue.file) {
      if (editIssueQuality !== editingIssue.file.quality) data.quality = editIssueQuality || null
      if (editIssueFormat !== editingIssue.file.format) data.format = editIssueFormat || null
      if ((editIssueReleaseGroup || null) !== editingIssue.file.releaseGroup) data.releaseGroup = editIssueReleaseGroup || null
      if ((editIssueLanguage || null) !== editingIssue.file.language) data.language = editIssueLanguage || null
      const currentFilename = editingIssue.file.path.split('/').pop() ?? ''
      if (editIssueFilename && editIssueFilename !== currentFilename) data.originalFilename = editIssueFilename
    }

    if (Object.keys(data).length === 0) {
      setEditIssueOpen(false)
      return
    }
    updateIssueMutation.mutate({ issueId: editingIssue.id, data })
  }

  const updateMagazineMutation = useMutation({
    mutationFn: (data: Partial<Magazine>) => updateMagazine(magazineId, data),
    onSuccess: () => {
      invalidateMagazine()
      invalidateIssues()
      setEditOpen(false)
      toast.success(t('magazineDetail.updated'))
    },
    onError: () => toast.error(t('magazineDetail.updateError')),
  })

  const deleteMagazineMutation = useMutation({
    mutationFn: () => deleteMagazine(magazineId, deleteFiles),
    onSuccess: () => {
      toast.success(t('magazineDetail.deleted'))
      navigate('/')
    },
    onError: () => toast.error(t('magazineDetail.deleteError')),
  })

  // A forecast with status "wanted" is effectively a real wanted issue
  const isUpcoming = (i: Issue) => i.isForecast && i.status !== 'wanted'
  const isWanted = (i: Issue) => i.status === 'wanted' || i.status === 'missing'

  // Group issues by year
  const filteredIssues = useMemo(() => {
    if (statusFilter === 'upcoming') return issues.filter(isUpcoming)
    // All other filters exclude true upcoming forecasts
    const real = issues.filter((i) => !isUpcoming(i))
    if (statusFilter === 'all') return real
    if (statusFilter === 'wanted') return real.filter(isWanted)
    return real.filter((i) => i.status === statusFilter)
  }, [issues, statusFilter])

  const groupedIssues = useMemo(() => {
    const groups: Record<string, Issue[]> = {}
    for (const issue of filteredIssues) {
      const yearKey = issue.year ? String(issue.year) : t('issues.unknownYear')
      if (!groups[yearKey]) groups[yearKey] = []
      groups[yearKey].push(issue)
    }
    const sorted = Object.entries(groups).sort(([a], [b]) => {
      const numA = parseInt(a)
      const numB = parseInt(b)
      if (isNaN(numA) && isNaN(numB)) return 0
      if (isNaN(numA)) return 1
      if (isNaN(numB)) return -1
      return numB - numA
    })
    return sorted
  }, [filteredIssues, t])

  // Status counts — true upcoming forecasts are excluded from "all"
  const statusCounts = useMemo(() => {
    const counts = { all: 0, available: 0, wanted: 0, upcoming: 0 }
    for (const issue of issues) {
      if (isUpcoming(issue)) {
        counts.upcoming++
      } else {
        counts.all++
        if (issue.status === 'available') counts.available++
        else if (isWanted(issue)) counts.wanted++
      }
    }
    return counts
  }, [issues])

  // Deduce missing issue fields from frequency pattern
  const deductions = useMemo(() => {
    const map = new Map<number, { deducedNumber?: number; deducedYear?: number; deducedMonth?: number }>()
    if (!magazine) return map

    const frequencyMonths: Record<string, number> = {
      daily: 1 / 30.44,
      weekly: 7 / 30.44,
      biweekly: 14 / 30.44,
      monthly: 1,
      bimonthly: 2,
      quarterly: 3,
      semiannual: 6,
      annual: 12,
    }

    const freqMonths = frequencyMonths[magazine.frequency]
    if (!freqMonths) return map // irregular or unknown

    // Find best anchor: most recent non-forecast issue with both number and year/month
    let anchor: { number: number; year: number; month: number } | null = null
    for (const issue of issues) {
      if (issue.isForecast || issue.number === null) continue
      let y: number | null = issue.year
      let m: number | null = issue.month
      if (y === null && issue.publicationDate) {
        const d = new Date(issue.publicationDate)
        y = d.getFullYear()
        m = d.getMonth() + 1
      }
      if (y === null) continue
      if (m === null) m = 1 // default to January if only year known
      if (!anchor || issue.number > anchor.number) {
        anchor = { number: issue.number, year: y, month: m }
      }
    }

    if (!anchor) return map

    const anchorTotalMonths = anchor.year * 12 + (anchor.month - 1)

    for (const issue of issues) {
      if (issue.isForecast) continue

      const hasNumber = issue.number !== null
      const hasDate = !!(issue.year || issue.publicationDate)

      if (hasNumber && !hasDate) {
        // Deduce year+month from number
        const totalMonths = anchorTotalMonths + (issue.number! - anchor.number) * freqMonths
        const deducedYear = Math.floor(totalMonths / 12)
        const deducedMonth = Math.round(totalMonths % 12) + 1
        // Handle month overflow from rounding
        if (deducedMonth > 12) {
          map.set(issue.id, { deducedYear: deducedYear + 1, deducedMonth: deducedMonth - 12 })
        } else {
          map.set(issue.id, { deducedYear, deducedMonth })
        }
      } else if (!hasNumber && hasDate) {
        // Deduce number from date
        let y = issue.year
        let m = issue.month
        if (y === null && issue.publicationDate) {
          const d = new Date(issue.publicationDate)
          y = d.getFullYear()
          m = d.getMonth() + 1
        }
        if (y !== null) {
          const issueTotalMonths = y * 12 + ((m ?? 1) - 1)
          const monthsDiff = issueTotalMonths - anchorTotalMonths
          const deducedNumber = anchor.number + Math.round(monthsDiff / freqMonths)
          if (deducedNumber > 0) {
            map.set(issue.id, { deducedNumber })
          }
        }
      }
    }

    return map
  }, [issues, magazine])

  // Détection de numéros incohérents par interpolation des voisins par
  // date. Cas typique : OCR défectueuse sur une couverture décalée qui
  // extrait "1234" alors qu'un hebdo passe de 2743 à 2745.
  //
  // Choix algo important — la tolérance vient du RANGE LOCAL entre le
  // voisin d'avant et celui d'après, PAS de la médiane des diffs. Sur
  // un petit échantillon (3-5 issues) avec un outlier, la médiane des
  // diffs est polluée par l'outlier lui-même (ex: diffs=[1509,1511] →
  // medianStep=1511 → tolérance énorme → outlier jamais détecté).
  // Le range local `|next - prev|` est indépendant de l'issue en cours,
  // donc reste petit même si le milieu est absurde.
  //
  // Pour les extrémités (pas de voisin des deux côtés), on regarde
  // 2 crans plus loin pour reconstituer un step, sinon on skip.
  const numberIncoherences = useMemo(() => {
    const map = new Map<number, { expected: number; reason: string }>()

    const pts: Array<{ id: number; number: number; time: number }> = []
    for (const issue of issues) {
      if (issue.isForecast || issue.number == null) continue
      let d: Date | null = null
      if (issue.publicationDate) d = new Date(issue.publicationDate)
      else if (issue.year && issue.month)
        d = new Date(issue.year, issue.month - 1, issue.day ?? 1)
      if (d && !isNaN(d.getTime())) {
        pts.push({ id: issue.id, number: issue.number, time: d.getTime() })
      }
    }
    // Besoin d'au moins 3 pts : au minimum 2 voisins pour un point
    // du milieu (le cas typique visé).
    if (pts.length < 3) return map
    pts.sort((a, b) => a.time - b.time)

    for (let i = 0; i < pts.length; i++) {
      const p = pts[i]
      const prev = pts[i - 1]
      const next = pts[i + 1]

      let expected: number | null = null
      let localRange = 0
      let reason = ''
      if (prev && next) {
        // Interpolation linéaire pondérée par position temporelle
        const range = next.time - prev.time
        const pos = range > 0 ? (p.time - prev.time) / range : 0.5
        expected = Math.round(prev.number + (next.number - prev.number) * pos)
        // Range = distance en numéro entre les 2 voisins ; sert de
        // référence propre pour la tolérance. Indépendant de p.number.
        localRange = Math.abs(next.number - prev.number)
        reason = `voisins #${prev.number} → #${next.number}`
      } else if (prev) {
        // Extrémité droite : extrapole depuis prev + step estimé
        // depuis prev-1 (si dispo).
        const prev2 = pts[i - 2]
        const step = prev2 ? prev.number - prev2.number : 1
        expected = prev.number + step
        localRange = Math.abs(step)
        reason = `voisin précédent #${prev.number} (step ${step >= 0 ? '+' : ''}${step})`
      } else if (next) {
        // Extrémité gauche
        const next2 = pts[i + 2]
        const step = next2 ? next2.number - next.number : 1
        expected = next.number - step
        localRange = Math.abs(step)
        reason = `voisin suivant #${next.number} (step ${step >= 0 ? '+' : ''}${step})`
      }
      if (expected == null || expected <= 0) continue

      // Tolérance = 5× le range local + plancher 10. Un magazine avec
      // gap éditorial (hors-série non compté, numéro double) reste OK
      // — un OCR qui invente un ordre de grandeur (1234 vs 2744) crève
      // le plafond même quand le voisinage a un step naturel de 2-3.
      const tolerance = Math.max(localRange * 5, 10)
      if (Math.abs(p.number - expected) > tolerance) {
        map.set(p.id, { expected, reason })
      }
    }
    return map
  }, [issues])

  // Estimate frequency from issue numbers and their dates.
  // Uses the ratio (days between issues) / (number difference) to compute
  // how many days per issue number increment, then maps to the closest frequency.
  // Works from just 2 complete issues and refines with more data.
  const estimatedFrequency = useMemo(() => {
    if (!issues.length) return null

    // Collect non-forecast issues with both a number AND a date
    const complete: { number: number; date: Date }[] = []
    for (const issue of issues) {
      if (issue.isForecast || issue.number == null) continue
      let d: Date | null = null
      if (issue.publicationDate) {
        d = new Date(issue.publicationDate)
      } else if (issue.year && issue.month) {
        d = new Date(issue.year, issue.month - 1, issue.day ?? 1)
      }
      if (d && !isNaN(d.getTime())) {
        complete.push({ number: issue.number, date: d })
      }
    }

    if (complete.length < 2) return null

    // Sort by number to pair consecutive-by-number issues
    complete.sort((a, b) => a.number - b.number)

    // Compute days-per-issue-number from all consecutive pairs
    let totalDays = 0
    let totalNumbers = 0
    for (let i = 1; i < complete.length; i++) {
      const numDiff = complete[i].number - complete[i - 1].number
      const daysDiff = (complete[i].date.getTime() - complete[i - 1].date.getTime()) / (1000 * 60 * 60 * 24)
      if (numDiff > 0 && daysDiff > 0) {
        totalDays += daysDiff
        totalNumbers += numDiff
      }
    }

    if (totalNumbers === 0) return null
    const daysPerIssue = totalDays / totalNumbers

    // Map to closest frequency
    const freqMap: [string, number][] = [
      ['daily', 1],
      ['weekly', 7],
      ['biweekly', 14],
      ['monthly', 30],
      ['bimonthly', 61],
      ['quarterly', 91],
      ['semiannual', 182],
      ['annual', 365],
    ]
    let closest = freqMap[0]
    let minDiff = Math.abs(daysPerIssue - closest[1])
    for (const entry of freqMap) {
      const diff = Math.abs(daysPerIssue - entry[1])
      if (diff < minDiff) {
        closest = entry
        minDiff = diff
      }
    }
    return closest[0]
  }, [issues])

  const issuesWithCovers = useMemo(
    () =>
      issues
        .filter((i) => i.coverPath && !i.isForecast)
        .sort((a, b) => (b.number ?? 0) - (a.number ?? 0)),
    [issues],
  )

  const hasDeductions = deductions.size > 0

  const completionPercent = statusCounts.all > 0
    ? Math.round((statusCounts.available / statusCounts.all) * 100)
    : 0

  // Selection handlers
  function handleSelect(issueId: number, checked: boolean) {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (checked) next.add(issueId)
      else next.delete(issueId)
      return next
    })
  }

  function handleSelectAll(checked: boolean) {
    if (checked) {
      setSelectedIds(new Set(issues.map((i) => i.id)))
    } else {
      setSelectedIds(new Set())
    }
  }

  function handleBatchMonitor(monitored: boolean) {
    const ids = Array.from(selectedIds)
    if (ids.length === 0) return
    batchMonitorMutation.mutate({ issueIds: ids, monitored })
  }

  // Edit modal helpers
  function openEdit() {
    if (!magazine) return
    setEditTitle(magazine.title)
    setEditMonitored(magazine.monitored)
    setEditQualityProfileId(String(magazine.qualityProfileId))
    setEditRootFolderPath(rootFolders.find((f) => f.id === magazine.rootFolderId)?.path ?? '')
    setEditFrequency(magazine.frequency)
    setEditMonitoringStartDate(magazine.monitoringStartDate ?? '')
    setEditExcludedDays(magazine.excludedDays ?? [])
    setEditReleaseWeekday(magazine.releaseWeekday ?? null)
    setEditUseLatestCover(magazine.useLatestIssueCover)
    setEditCoverIssueId(null)
    setEditIssn(magazine.issn ?? '')
    setEditWantedSearchEnabled(magazine.wantedSearchEnabled)
    setEditWeekendDays(magazine.weekendDays ?? [])
    // Hydrate depuis issueGroups s'il existe, sinon migration soft
    // depuis weekendDays (1 groupe unique). Permet à l'user de
    // basculer sur l'éditeur multi-groupes sans perte.
    setEditIssueGroups(
      magazine.issueGroups && magazine.issueGroups.length > 0
        ? magazine.issueGroups.map((g) => ({
            days: [...g.days],
            type: (g.type ?? 'regular') as 'regular' | 'weekend' | 'special',
            label: g.label ?? null,
          }))
        : magazine.weekendDays && magazine.weekendDays.length > 0
          // Migration soft : ancien weekend_days → 1 groupe type "weekend"
          ? [{ days: [...magazine.weekendDays], type: 'weekend' as const, label: null }]
          : []
    )
    setEditSortByRecent(magazine.sortByRecentDate ?? true)
    setEditMinTitleOverride(
      magazine.minTitleMatchOverride != null
        ? String(magazine.minTitleMatchOverride)
        : ''
    )
    setEditAutoGrabThresholdOverride(
      magazine.autoGrabThresholdOverride != null
        ? String(magazine.autoGrabThresholdOverride)
        : ''
    )
    setEditOpen(true)
  }

  function handleSaveEdit() {
    const folder = rootFolders.find((f) => f.path === editRootFolderPath)
    updateMagazineMutation.mutate({
      title: editTitle,
      monitored: editMonitored,
      qualityProfileId: Number(editQualityProfileId),
      rootFolderId: folder?.id,
      frequency: editFrequency,
      monitoringStartDate: editMonitoringStartDate || null,
      excludedDays: editExcludedDays,
      releaseWeekday: editReleaseWeekday,
      useLatestIssueCover: editUseLatestCover,
      issn: editIssn.trim() || null,
      // Passer par le formulaire d'édition retire le flag placeholder :
      // le user a explicitement validé les infos.
      isPlaceholder: false,
      wantedSearchEnabled: editWantedSearchEnabled,
      weekendDays: editWeekendDays.length > 0 ? editWeekendDays : null,
      issueGroups: editIssueGroups.length > 0 ? editIssueGroups : null,
      sortByRecentDate: editSortByRecent,
      minTitleMatchOverride: editMinTitleOverride.trim()
        ? Number(editMinTitleOverride)
        : null,
      autoGrabThresholdOverride: editAutoGrabThresholdOverride.trim()
        ? Number(editAutoGrabThresholdOverride)
        : null,
      ...(editCoverIssueId != null ? { coverIssueId: editCoverIssueId } : {}),
    })
  }

  async function handleCoverUpload(formData: FormData) {
    setCoverUploading(true)
    try {
      const updated = await uploadMagazineCover(magazineId, formData)
      queryClient.setQueryData(['magazine', magazineId], updated)
      toast.success(t('magazineDetail.coverUploaded'))
    } catch {
      toast.error(t('magazineDetail.coverUploadError'))
    } finally {
      setCoverUploading(false)
    }
  }

  function handleCoverFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    const fd = new FormData()
    fd.append('file', file)
    handleCoverUpload(fd)
    e.target.value = ''
  }

  function handleCoverUrlLoad() {
    if (!coverUrl.trim()) return
    const fd = new FormData()
    fd.append('url', coverUrl.trim())
    handleCoverUpload(fd)
    setCoverUrl('')
  }

  // Refresh — combine 2 opérations :
  //   1. `refreshMetadata` : recharge titre/publisher/frequency depuis
  //      Wikidata/Google Books/BnF selon la config
  //   2. `resyncMagazineIssues` : purge les issues wanted/upcoming/delayed
  //      SANS fichier et regénère backlog + forecasts avec la config
  //      actuelle (weekend_days, excluded_days). Préserve toujours les
  //      available / imported / snatched.
  // Utile après un changement de config (weekend/excluded) : plus besoin
  // d'un 2ᵉ bouton — l'user clique juste Refresh et tout est cohérent.
  async function handleRefresh() {
    setRefreshing(true)
    const tid = toast.loading('Refresh en cours…')
    try {
      await refreshMetadata(magazineId)
      const sync = await resyncMagazineIssues(magazineId)
      invalidateMagazine()
      invalidateIssues()
      const parts: string[] = []
      if (sync.deleted > 0) parts.push(`${sync.deleted} supprimée(s)`)
      const regen = sync.backlogCreated + sync.forecastsCreated
      if (regen > 0) parts.push(`${regen} régénérée(s)`)
      toast.success(
        parts.length > 0 ? parts.join(' · ') : t('magazineDetail.refreshed'),
        { id: tid, duration: 5000 },
      )
    } catch {
      toast.error(t('magazineDetail.refreshError'), { id: tid })
    } finally {
      setRefreshing(false)
    }
  }

  const [searchingWanted, setSearchingWanted] = useState(false)
  async function handleSearchWanted() {
    setSearchingWanted(true)
    const tid = toast.loading('Lancement recherche wanted…')
    try {
      const res = await searchWantedMagazine(magazineId)
      if (res.queued === 0) {
        toast.info('Aucune issue wanted à rechercher', { id: tid })
      } else {
        toast.success(
          `${res.queued} recherche(s) lancée(s) — voir /activity pour le déroulé`,
          { id: tid, duration: 6000 },
        )
      }
    } catch (e) {
      toast.error(`Échec : ${(e as Error).message}`, { id: tid })
    } finally {
      setSearchingWanted(false)
    }
  }


  async function handleRefreshIssue(issueId: number) {
    setRefreshingIssueId(issueId)
    try {
      await refreshIssue(issueId)
      invalidateIssues()
      toast.success(t('issues.refreshed'))
    } catch {
      toast.error(t('issues.refreshError'))
    } finally {
      setRefreshingIssueId(null)
    }
  }

  async function handleImportIssue(issueId: number) {
    setImportingIssueId(issueId)
    try {
      const result = await triggerIssueImport(issueId)
      invalidateIssues()
      if (result.success) {
        toast.success(t('issues.importSuccess'))
      } else {
        toast.error(result.message || t('issues.importError'))
      }
    } catch {
      toast.error(t('issues.importError'))
    } finally {
      setImportingIssueId(null)
    }
  }

  // Manual Research modal
  function handleOpenManualSearch() {
    if (!magazine) return
    setManualSearchQuery(magazine.title)
    setManualSearchResults([])
    setManualSearching(false)
    setManualSearchOpen(true)
  }

  async function handleManualSearch(tab?: string) {
    const activeTab = tab || manualSearchTab
    if (!manualSearchQuery.trim() && !isSceneTab(activeTab)) return
    setManualSearching(true)
    setManualSearchResults([])
    setSceneResults([])
    setManualSearchPage(1)
    setManualSearchSourceFilter('')
    setManualSearchDateSort('')
    // Reset counts for this query — active tab count is set from
    // its own result below; the other two tabs are probed in
    // background so the operator sees where the hits actually are.
    if (!isSceneTab(activeTab)) {
      setManualSearchCounts({
        annasarchive: null,
        internetarchive: null,
        indexers: null,
      })
      const q = manualSearchQuery
      const probes: Array<[string, Promise<SearchResult[]>]> = [
        ['annasarchive', searchAnnasArchive(q, magazineId)],
        ['internetarchive', searchInternetArchive(q, magazineId)],
        ['indexers', searchIndexers(q, magazineId)],
      ]
      probes
        .filter(([key]) => key !== activeTab)
        .forEach(([key, p]) => {
          p.then(
            (r) =>
              setManualSearchCounts((c) => ({ ...c, [key]: r.length })),
            () =>
              setManualSearchCounts((c) => ({ ...c, [key]: 0 })),
          )
        })
    }
    try {
      if (activeTab === 'annasarchive') {
        const r = await searchAnnasArchive(manualSearchQuery, magazineId)
        setManualSearchResults(r)
        setManualSearchCounts((c) => ({ ...c, annasarchive: r.length }))
      } else if (activeTab === 'internetarchive') {
        const r = await searchInternetArchive(manualSearchQuery, magazineId)
        setManualSearchResults(r)
        setManualSearchCounts((c) => ({ ...c, internetarchive: r.length }))
      } else if (activeTab === 'indexers') {
        const r = await searchIndexers(manualSearchQuery, magazineId)
        setManualSearchResults(r)
        setManualSearchCounts((c) => ({ ...c, indexers: r.length }))
      } else if (isSceneTab(activeTab)) {
        // Scene tabs scrape pressarr's own indexer (Bookys /
        // tm.org) using the magazine's stored title + aliases
        // — the operator-typed query is ignored on purpose so
        // the orchestrator keeps full control over the
        // search-string fan-out.
        setSceneResults(
          await scanMagazineSceneReleases(magazineId, activeTab),
        )
      }
    } catch {
      toast.error(t('issues.searchError'))
    } finally {
      setManualSearching(false)
    }
  }

  function isSceneTab(tab: string): tab is 'bookys' | 'telecharger_magazines' {
    return tab === 'bookys' || tab === 'telecharger_magazines'
  }

  async function handleSceneGrab(release: MagazineRelease) {
    setSceneGrabbing((s) => new Set(s).add(release.id))
    try {
      const updated = await grabMagazineSceneRelease(magazineId, release.id)
      // Replace the row in-place so the status chip flips
      // ``available → grabbed`` without a re-fetch.
      setSceneResults((rows) =>
        rows.map((r) => (r.id === updated.id ? updated : r)),
      )
      toast.success(t('issues.grabbed'))
      queryClient.invalidateQueries({ queryKey: ['activity-counters'] })
      queryClient.invalidateQueries({ queryKey: ['activity-list'] })
    } catch {
      toast.error(t('issues.grabError'))
    } finally {
      setSceneGrabbing((s) => {
        const next = new Set(s)
        next.delete(release.id)
        return next
      })
    }
  }

  function formatSize(bytes?: number | null): string | null {
    if (!bytes || bytes < 1024) return null
    const units = ['B', 'KB', 'MB', 'GB']
    let i = 0
    let value = bytes
    while (value >= 1024 && i < units.length - 1) {
      value /= 1024
      i++
    }
    return `${value.toFixed(1)} ${units[i]}`
  }

  // Search
  async function handleSearch(issueId: number) {
    setSearchingIssueId(issueId)
    setSearchResults([])
    setSearchPage(1)
    setSearchSourceFilter('')
    setSearchDateSort('')
    setSearchDialogOpen(true)
    setSearching(true)
    try {
      const results = await searchIssue(issueId)
      setSearchResults(results)
    } catch {
      toast.error(t('issues.searchError'))
    } finally {
      setSearching(false)
    }
  }

  async function handleGrab(
    result: SearchResult,
    fromManualSearch = false,
    overrides?: { targetIssueId?: number; targetDate?: string },
  ) {
    if (!fromManualSearch && !searchingIssueId && !magazine) return
    const targetIssueId = searchingIssueId ?? 0
    setGrabbing(result.guid)
    try {
      if (result.protocol === 'aa') {
        await downloadFromAA(
          result.guid, result.title,
          targetIssueId || undefined, magazineId, overrides,
        )
      } else if (result.protocol === 'ia') {
        await downloadFromIA(
          result.guid, `${result.guid}.pdf`, result.title,
          targetIssueId || undefined, magazineId, overrides,
        )
      } else {
        await grabRelease(
          targetIssueId,
          result.downloadUrl,
          result.title,
          result.protocol,
          result.guid,
          magazineId,
          overrides,
        )
      }
      toast.success(t('issues.grabbed'))
      if (fromManualSearch) {
        setManualSearchOpen(false)
        setGrabConfirm(null)
      } else {
        setSearchDialogOpen(false)
      }
      invalidateIssues()
      // Fait apparaître l'activité tout de suite dans la sidebar +
      // page /activity sans attendre le prochain poll (5 s sidebar,
      // 4 s page — la fenêtre "recent terminal" backend fait le reste
      // si le grab a été très rapide).
      queryClient.invalidateQueries({ queryKey: ['activity-counters'] })
      queryClient.invalidateQueries({ queryKey: ['activity-list'] })
    } catch {
      toast.error(t('issues.grabError'))
    } finally {
      setGrabbing(null)
    }
  }

  const allSelected = issues.length > 0 && selectedIds.size === issues.length

  if (isLoading) {
    return (
      <div className="p-4 lg:p-8">
        <div className="flex gap-6 mb-8">
          <Skeleton className="w-32 h-44 bg-zinc-800 rounded-lg shrink-0" />
          <div className="flex-1 space-y-3">
            <Skeleton className="h-8 w-64 bg-zinc-800" />
            <Skeleton className="h-4 w-48 bg-zinc-800" />
            <Skeleton className="h-4 w-32 bg-zinc-800" />
          </div>
        </div>
        <div className="flex gap-2 mb-6">
          {[1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-9 w-24 bg-zinc-800" />
          ))}
        </div>
        <div className="space-y-2">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <Skeleton key={i} className="h-12 bg-zinc-800" />
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="p-4 lg:p-8">
      {/* Cover + Metadata Header */}
      {magazine && (
        <div className="flex gap-6 mb-8">
          {/* Cover */}
          <div className="w-32 shrink-0">
            <div className="aspect-[3/4] rounded-lg bg-zinc-900 overflow-hidden">
              {magazine.coverPath ? (
                <img
                  src={getMagazineCoverUrl(magazine.id, magazine.coverPath ?? undefined)}
                  alt={magazine.title}
                  className="h-full w-full object-cover"
                />
              ) : (
                <div className="flex items-center justify-center h-full text-zinc-600 text-sm">
                  {t('library.noCover')}
                </div>
              )}
            </div>
          </div>

          {/* Metadata */}
          <div className="flex-1 min-w-0">
            <div className="flex items-start justify-between">
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <h1 className="text-2xl font-bold text-zinc-100">{magazine.title}</h1>
                  <Badge variant={magazine.monitored ? 'default' : 'secondary'} className={magazine.monitored ? 'bg-[#7C3AED] hover:bg-[#7C3AED] text-white' : ''}>
                    {magazine.monitored ? t('library.monitored') : t('library.unmonitored')}
                  </Badge>
                  {magazine.isPlaceholder && (
                    <Badge className="bg-amber-500/90 text-amber-950 border border-amber-300/60 text-[10px]">
                      À compléter
                    </Badge>
                  )}
                </div>
                <div className="flex items-center gap-2 mt-1 text-sm text-zinc-400 flex-wrap">
                  {magazine.publisher && (
                    <span>{magazine.publisher}</span>
                  )}
                  {magazine.frequency && (
                    <>
                      <span className="text-zinc-700">|</span>
                      <span className="capitalize">{magazine.frequency}</span>
                    </>
                  )}
                  {magazine.issn && (
                    <>
                      <span className="text-zinc-700">|</span>
                      <span className="font-mono text-xs">ISSN {magazine.issn}</span>
                    </>
                  )}
                </div>
                {magazine.description && (
                  <p className="text-sm text-zinc-500 mt-2 line-clamp-2">
                    {magazine.description}
                  </p>
                )}
              </div>

              {/* Action buttons — desktop only */}
              <div className="hidden sm:flex items-center gap-2 shrink-0">
                <Button variant="outline" size="sm" onClick={openEdit}>
                  <Pencil className="size-3.5" />
                  {t('common.edit')}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleRefresh}
                  disabled={refreshing}
                  title="Recharge les métadonnées (Wikidata/Google Books/BnF) ET régularise la liste des issues (purge doublons wanted, regénère selon la config actuelle — weekend_days, excluded_days). Préserve les available."
                >
                  {refreshing ? (
                    <Loader2 className="size-3.5 animate-spin" />
                  ) : (
                    <RefreshCw className="size-3.5" />
                  )}
                  {t('magazineDetail.refresh')}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setFileManagerOpen(true)}
                >
                  <FolderOpen className="size-3.5" />
                  {t('magazineDetail.fileManager')}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleOpenManualSearch}
                >
                  <Search className="size-3.5" />
                  {t('magazineDetail.manualResearch')}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleSearchWanted}
                  disabled={searchingWanted}
                  title="Lance le pipeline wanted_search (Prowlarr + IA + rules + auto-grab) sur toutes les issues wanted de ce magazine"
                >
                  {searchingWanted ? (
                    <Loader2 className="size-3.5 animate-spin text-purple-400" />
                  ) : (
                    <Sparkles className="size-3.5 text-purple-400" />
                  )}
                  Recherche wanted
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setAiRefreshOpen(true)}
                  title="Refresh multi-issues : métadonnées classiques + IA texte + IA vision"
                >
                  <Sparkles className="size-3.5 text-purple-400" />
                  Refresh IA…
                </Button>
<Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setDeleteFiles(false)
                    setDeleteOpen(true)
                  }}
                  className="text-destructive hover:text-destructive"
                >
                  <Trash2 className="size-3.5" />
                  {t('common.delete')}
                </Button>
              </div>
            </div>

            {/* Action buttons — mobile only, below cover+description */}
            <div className="flex flex-wrap items-center gap-2 mt-3 sm:hidden">
              <Button variant="outline" size="sm" onClick={openEdit}>
                <Pencil className="size-3.5" />
                {t('common.edit')}
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={handleRefresh}
                disabled={refreshing}
              >
                <RefreshCw className={`size-3.5 ${refreshing ? 'animate-spin' : ''}`} />
                {t('magazineDetail.refresh')}
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setFileManagerOpen(true)}
              >
                <FolderOpen className="size-3.5" />
                {t('magazineDetail.fileManager')}
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={handleOpenManualSearch}
              >
                <Search className="size-3.5" />
                {t('magazineDetail.manualResearch')}
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={handleSearchWanted}
                disabled={searchingWanted}
                title="Lance le pipeline wanted_search (Prowlarr + IA + rules + auto-grab) sur toutes les issues wanted de ce magazine"
              >
                {searchingWanted ? (
                  <Loader2 className="size-3.5 animate-spin text-purple-400" />
                ) : (
                  <Sparkles className="size-3.5 text-purple-400" />
                )}
                Recherche wanted
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setAiRefreshOpen(true)}
                title="Refresh multi-issues avec métadonnées + IA"
              >
                <Sparkles className="size-3.5 text-purple-400" />
                Refresh IA…
              </Button>
<Button
                variant="outline"
                size="sm"
                onClick={() => {
                  setDeleteFiles(false)
                  setDeleteOpen(true)
                }}
                className="text-destructive hover:text-destructive"
              >
                <Trash2 className="size-3.5" />
                {t('common.delete')}
              </Button>
            </div>

            {/* Statistics overview */}
            <div className="flex items-center gap-4 mt-4">
              <div className="flex items-center gap-3 text-sm">
                <span className="text-zinc-400">
                  {t('magazineDetail.totalIssues')}: <span className="text-zinc-100">{statusCounts.all}</span>
                </span>
                <span className="text-zinc-400">
                  {t('status.available')}: <span className="text-green-400">{statusCounts.available}</span>
                </span>
                <span className="text-zinc-400">
                  {t('status.wanted')}: <span className="text-red-400">{statusCounts.wanted}</span>
                </span>
                <span className="text-zinc-400">
                  {t('magazineDetail.completion')}: <span className="text-[#7C3AED]">{completionPercent}%</span>
                </span>
              </div>
            </div>

            {/* Progress bar */}
            <div className="mt-3 h-1.5 rounded-full bg-zinc-800 overflow-hidden max-w-md">
              <div
                className="h-full rounded-full bg-[#7C3AED] transition-all"
                style={{ width: `${completionPercent}%` }}
              />
            </div>

          </div>
        </div>
      )}

      {/* Placeholder banner — magazine auto-créé par un pack.
          Invite l'utilisateur à finaliser frequency + root folder +
          quality. Clic sur "Compléter" ouvre le modal d'édition. */}
      {magazine?.isPlaceholder && (
        <div className="mb-4 rounded-lg border border-amber-500/40 bg-amber-500/10 p-3 flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <div className="text-sm font-medium text-amber-200">
              Magazine créé automatiquement — à finaliser
            </div>
            <div className="text-xs text-amber-300/80 mt-1">
              Ce magazine a été créé par un pack. Vérifie et complète
              la fréquence, le root folder, la qualité et le titre
              avant de laisser tourner les auto-grabs.
            </div>
          </div>
          <Button
            size="sm"
            onClick={openEdit}
            className="bg-amber-500 text-amber-950 hover:bg-amber-400 shrink-0"
          >
            Compléter
          </Button>
        </div>
      )}

      {/* Main Tabs: Issues / Patterns / Rules / Activités */}
      <Tabs defaultValue="issues">
        <TabsList className="bg-zinc-900 border-zinc-800 mb-4">
          <TabsTrigger value="issues">{t('magazineDetail.tabIssues')}</TabsTrigger>
          <TabsTrigger value="patterns">
            {t('magazineDetail.tabPatterns')}
            {magazine && magazine.patterns?.length > 0 && (
              <Badge variant="secondary" className="ml-1.5 text-xs px-1.5">{magazine.patterns.length}</Badge>
            )}
          </TabsTrigger>
          <TabsTrigger value="rules">
            {t('magazineDetail.tabRules')}
            {magazine && magazine.rules?.length > 0 && (
              <Badge variant="secondary" className="ml-1.5 text-xs px-1.5">{magazine.rules.length}</Badge>
            )}
          </TabsTrigger>
          <TabsTrigger value="activity">
            Activités
            {activityRunningCount > 0 && (
              <span
                className="ml-1.5 inline-flex items-center gap-1 rounded-full bg-violet-500/20 text-violet-200 border border-violet-500/40 text-[10px] px-1.5 py-0.5"
                title={`${activityRunningCount} en cours`}
              >
                <span className="size-1.5 rounded-full bg-violet-400 animate-pulse" />
                {activityRunningCount}
              </span>
            )}
          </TabsTrigger>
          <TabsTrigger value="history">Historique</TabsTrigger>
        </TabsList>

        <TabsContent value="issues">
      {/* Status Filters */}
      <div className="flex flex-wrap items-center gap-2 mb-6">
        {(['all', 'available', 'wanted', 'upcoming'] as StatusFilter[]).map((filter) => (
          <Button
            key={filter}
            variant={statusFilter === filter ? 'default' : 'outline'}
            size="sm"
            onClick={() => setStatusFilter(filter)}
            className={statusFilter === filter ? 'bg-[#7C3AED] hover:bg-[#7C3AED]/90' : ''}
          >
            {filter === 'all' ? t('issues.all') : t(`status.${filter}`)}
            <Badge
              variant="secondary"
              className="ml-1.5 text-xs px-1.5"
            >
              {statusCounts[filter]}
            </Badge>
          </Button>
        ))}
      </div>

      {/* Batch Actions */}
      {selectedIds.size > 0 && (
        <div className="flex items-center gap-3 mb-4 px-3 py-2 rounded-md bg-zinc-900 border border-zinc-800">
          <span className="text-sm text-zinc-400">
            {t('issues.selected', { count: selectedIds.size })}
          </span>
          <Button
            variant="outline"
            size="sm"
            onClick={() => handleBatchMonitor(true)}
            disabled={batchMonitorMutation.isPending}
          >
            <Eye className="size-3.5" />
            {t('issues.monitorAll')}
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => handleBatchMonitor(false)}
            disabled={batchMonitorMutation.isPending}
          >
            <EyeOff className="size-3.5" />
            {t('issues.unmonitorAll')}
          </Button>
        </div>
      )}

      {/* Deduction legend */}
      {hasDeductions && (
        <div className="flex items-center gap-2 mb-3 text-xs text-amber-400">
          <span className="inline-block w-2 h-2 rounded-full bg-amber-400" />
          <span className="italic">{t('issues.deducedLegend')}</span>
        </div>
      )}

      {/* Issues Table */}
      {groupedIssues.length === 0 ? (
        <p className="text-zinc-500 text-center py-8">
          {t('issues.noIssues')}
        </p>
      ) : (
        <div className="space-y-6">
          {groupedIssues.map(([year, yearIssues]) => (
            <div key={year}>
              <h2 className="text-lg font-semibold text-zinc-300 mb-3 border-b border-zinc-800 pb-2">
                {year}
                <span className="ml-2 text-sm font-normal text-zinc-500">
                  ({yearIssues.length})
                </span>
              </h2>
              <Table>
                <TableHeader>
                  <TableRow className="border-zinc-800 hover:bg-transparent">
                    <TableHead className="w-10 text-zinc-400">
                      <input
                        type="checkbox"
                        checked={allSelected}
                        onChange={(e) => handleSelectAll(e.target.checked)}
                        className="size-4 rounded border-zinc-600 bg-zinc-900 accent-[#7C3AED]"
                      />
                    </TableHead>
                    <SortableHead
                      label={t('issues.number')}
                      sortKey="number"
                      currentKey={issueSortKey}
                      currentDir={issueSortDir}
                      onSort={toggleIssueSort}
                    />
                    <SortableHead
                      label={t('issues.date')}
                      sortKey="date"
                      currentKey={issueSortKey}
                      currentDir={issueSortDir}
                      onSort={toggleIssueSort}
                    />
                    <TableHead className="text-zinc-400">Type</TableHead>
                    <SortableHead
                      label={t('issues.issueTitle')}
                      sortKey="title"
                      currentKey={issueSortKey}
                      currentDir={issueSortDir}
                      onSort={toggleIssueSort}
                    />
                    <TableHead className="text-zinc-400">Prix</TableHead>
                    <TableHead className="text-zinc-400">ISSN</TableHead>
                    <SortableHead
                      label={t('issues.status')}
                      sortKey="status"
                      currentKey={issueSortKey}
                      currentDir={issueSortDir}
                      onSort={toggleIssueSort}
                    />
                    <TableHead className="text-zinc-400">{t('issues.fileInfo')}</TableHead>
                    <TableHead className="text-zinc-400">Source</TableHead>
                    <TableHead className="text-zinc-400">{t('issues.actions')}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {(() => {
                    const regular = sortIssues(
                      yearIssues.filter((i) => !i.isForecast || i.status === 'wanted'),
                      issueSortKey, issueSortDir,
                    )
                    const upcoming = sortIssues(
                      yearIssues.filter((i) => i.isForecast && i.status !== 'wanted'),
                      issueSortKey, issueSortDir,
                    )
                    const isExpanded = expandedUpcoming.has(year)

                    const renderRow = (issue: typeof yearIssues[number]) => (
                      <IssueRow
                        key={issue.id}
                        issue={issue}
                        selected={selectedIds.has(issue.id)}
                        queueItem={queueByIssueId.get(issue.id)}
                        deduced={deductions.get(issue.id)}
                        numberIncoherence={numberIncoherences.get(issue.id)}
                        weekendDays={magazine?.weekendDays ?? undefined}
                        issueGroups={magazine?.issueGroups ?? undefined}
                        onSelect={handleSelect}
                        onToggleMonitor={(issueId, monitored) =>
                          monitorMutation.mutate({ issueId, monitored })
                        }
                        onEdit={handleEditIssue}
                        onDeleteFile={(issueId) => {
                          setDeleteFileIssueId(issueId)
                          setDeleteFileOpen(true)
                        }}
                        onSearch={handleSearch}
                        onWantedSearch={(id) => setWantedSearchIssueId(id)}
                        onRefresh={handleRefreshIssue}
                        onImport={handleImportIssue}
                        onView={(id) => { setViewerIssueId(id); setViewerOpen(true) }}
                        onHistory={(id) => { setHistoryIssueId(id); setHistoryIssueOpen(true) }}
                        refreshingId={refreshingIssueId}
                        importingId={importingIssueId}
                      />
                    )

                    return (
                      <>
                        {regular.map(renderRow)}
                        {upcoming.length > 0 && (
                          <>
                            <TableRow
                              className="border-zinc-800 cursor-pointer hover:bg-zinc-900/50"
                              onClick={() => {
                                setExpandedUpcoming((prev) => {
                                  const next = new Set(prev)
                                  if (next.has(year)) next.delete(year)
                                  else next.add(year)
                                  return next
                                })
                              }}
                            >
                              <TableCell colSpan={11} className="py-2">
                                <div className="flex items-center gap-2 text-sm text-zinc-400">
                                  {isExpanded
                                    ? <ChevronDown className="size-4" />
                                    : <ChevronRight className="size-4" />
                                  }
                                  <span>
                                    {t('issues.upcomingCollapsed', { count: upcoming.length })}
                                  </span>
                                </div>
                              </TableCell>
                            </TableRow>
                            {isExpanded && upcoming.map(renderRow)}
                          </>
                        )}
                      </>
                    )
                  })()}
                </TableBody>
              </Table>
            </div>
          ))}
        </div>
      )}

      {/* Search Results Dialog */}
      <Dialog open={searchDialogOpen} onOpenChange={setSearchDialogOpen}>
        <DialogContent className="sm:max-w-2xl bg-zinc-950 border-zinc-800 max-h-[80vh] overflow-hidden flex flex-col">
          <DialogHeader>
            <DialogTitle className="text-zinc-100">
              {t('issues.searchResults')}
            </DialogTitle>
          </DialogHeader>

          {(() => {
            const sources = [...new Set(searchResults.map((r) => r.source || r.indexer).filter(Boolean))]
            const bySource = searchSourceFilter
              ? searchResults.filter((r) => (r.source || r.indexer) === searchSourceFilter)
              : searchResults
            const filtered = searchDateSort ? sortByDate(bySource, searchDateSort) : bySource
            const totalPages = Math.ceil(filtered.length / RESULTS_PER_PAGE)
            const nextDateSort = searchDateSort === '' ? 'desc' : searchDateSort === 'desc' ? 'asc' : ''
            const dateSortLabel = searchDateSort === 'desc' ? t('issues.sortDateDesc') : searchDateSort === 'asc' ? t('issues.sortDateAsc') : t('issues.sortDefault')
            return (
              <>
                {searchResults.length > 0 && (
                  <div className="flex flex-wrap items-center gap-1.5 pb-2">
                    {sources.length > 1 && (
                      <Badge
                        variant={searchSourceFilter === '' ? 'default' : 'outline'}
                        className="cursor-pointer text-xs"
                        onClick={() => { setSearchSourceFilter(''); setSearchPage(1) }}
                      >
                        {t('issues.all')} ({searchResults.length})
                      </Badge>
                    )}
                    {sources.map((src) => {
                      const count = searchResults.filter((r) => (r.source || r.indexer) === src).length
                      return (
                        <Badge
                          key={src}
                          variant={searchSourceFilter === src ? 'default' : 'outline'}
                          className="cursor-pointer text-xs"
                          onClick={() => { setSearchSourceFilter(src); setSearchPage(1) }}
                        >
                          {src} ({count})
                        </Badge>
                      )
                    })}
                    <Button
                      variant="ghost"
                      size="sm"
                      className="ml-auto h-6 px-2 text-xs text-zinc-400"
                      onClick={() => { setSearchDateSort(nextDateSort as '' | 'asc' | 'desc'); setSearchPage(1) }}
                    >
                      <ArrowDownUp className="size-3 mr-1" />
                      {dateSortLabel}
                    </Button>
                  </div>
                )}
                <div className="flex-1 overflow-y-auto">
                  {searching ? (
                    <div className="flex items-center justify-center py-12">
                      <Loader2 className="size-6 animate-spin text-zinc-400" />
                      <span className="ml-2 text-zinc-400">{t('issues.searching')}</span>
                    </div>
                  ) : filtered.length === 0 ? (
                    <p className="text-zinc-500 text-center py-8">
                      {t('common.noResults')}
                    </p>
                  ) : (
                    <div className="divide-y divide-zinc-800">
                      {filtered
                        .slice((searchPage - 1) * RESULTS_PER_PAGE, searchPage * RESULTS_PER_PAGE)
                        .map((result) => (
                        <div
                          key={result.guid}
                          className={`flex items-center justify-between py-3 px-2 hover:bg-zinc-900/50 rounded ${
                            result.isBlocklisted ? 'opacity-40' : ''
                          }`}
                        >
                          <div className="flex-1 min-w-0 mr-4">
                            <p className="text-sm text-zinc-100 truncate">{result.title}</p>
                            <div className="flex items-center gap-2 mt-1 text-xs text-zinc-500">
                              {result.source ? (
                                <span>{result.source}</span>
                              ) : (
                                <span>{result.indexer}</span>
                              )}
                              {result.size > 0 && (
                                <>
                                  <span>|</span>
                                  <span>{formatBytes(result.size)}</span>
                                </>
                              )}
                              {result.quality && result.quality !== 'unknown' && (
                                <>
                                  <span>|</span>
                                  <span>{result.quality}</span>
                                </>
                              )}
                              {result.language && result.language !== 'unknown' && (
                                <>
                                  <span>|</span>
                                  <span>{result.language}</span>
                                </>
                              )}
                              {result.seeders !== null && result.seeders > 0 && (
                                <>
                                  <span>|</span>
                                  <span>
                                    {result.seeders} {result.protocol === 'ia' ? 'downloads' : t('issues.seeders')}
                                  </span>
                                </>
                              )}
                              {result.publishDate && (
                                <>
                                  <span>|</span>
                                  <span>{formatPublishDate(result.publishDate)}</span>
                                </>
                              )}
                              {!result.publishDate && result.age > 0 && (
                                <>
                                  <span>|</span>
                                  <span>{result.age}d</span>
                                </>
                              )}
                            </div>
                          </div>
                          <Button
                            variant="outline"
                            size="sm"
                            disabled={result.isBlocklisted || grabbing === result.guid}
                            onClick={() => handleGrab(result)}
                          >
                            {grabbing === result.guid ? (
                              <Loader2 className="size-3.5 animate-spin" />
                            ) : (
                              <Download className="size-3.5" />
                            )}
                            {t('issues.grab')}
                          </Button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
                {totalPages > 1 && (
                  <div className="flex items-center justify-center gap-2 pt-3 border-t border-zinc-800">
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={searchPage <= 1}
                      onClick={() => setSearchPage((p) => p - 1)}
                    >
                      <ChevronLeft className="size-4" />
                    </Button>
                    <span className="text-xs text-zinc-400">
                      {t('issues.page', { page: searchPage, totalPages })}
                    </span>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={searchPage >= totalPages}
                      onClick={() => setSearchPage((p) => p + 1)}
                    >
                      <ChevronRight className="size-4" />
                    </Button>
                  </div>
                )}
              </>
            )
          })()}
        </DialogContent>
      </Dialog>
        </TabsContent>

        <TabsContent value="patterns">
          {magazine && <MagazinePatternsTab magazine={magazine} magazineId={magazineId} />}
        </TabsContent>

        <TabsContent value="rules">
          {magazine && <MagazineRulesTab magazine={magazine} magazineId={magazineId} />}
        </TabsContent>

        <TabsContent value="activity">
          <MagazineActivitiesPanel magazineId={magazineId} limit={50} />
        </TabsContent>

        <TabsContent value="history">
          <HistoryList magazineId={magazineId} pageSize={20} />
        </TabsContent>
      </Tabs>

      {/* Manual Research Modal */}
      <Dialog open={manualSearchOpen} onOpenChange={setManualSearchOpen}>
        <DialogContent className="sm:max-w-3xl bg-zinc-950 border-zinc-800 max-h-[85vh] overflow-hidden flex flex-col">
          <DialogHeader>
            <DialogTitle className="text-zinc-100">
              {t('magazineDetail.manualResearch')}
            </DialogTitle>
          </DialogHeader>

          <Tabs
            value={manualSearchTab}
            onValueChange={(val) => {
              setManualSearchTab(val)
              setManualSearchResults([])
              setManualSearchPage(1)
              setManualSearchSourceFilter('')
              setManualSearchDateSort('')
              // Auto-fetch on tab switch so the user doesn't have
              // to re-submit — the background probe already told us
              // whether this tab has hits, but not the actual rows.
              if (
                !isSceneTab(val) &&
                manualSearchQuery.trim() &&
                (manualSearchCounts[val] ?? 0) > 0
              ) {
                handleManualSearch(val)
              }
            }}
            className="flex-1 overflow-hidden flex flex-col"
          >
            <TabsList className="w-full">
              <TabsTrigger value="annasarchive">
                {t('magazineDetail.tabAnnasArchive')}
                <TabCountBadge n={manualSearchCounts.annasarchive} />
              </TabsTrigger>
              <TabsTrigger value="internetarchive">
                {t('magazineDetail.tabInternetArchive')}
                <TabCountBadge n={manualSearchCounts.internetarchive} />
              </TabsTrigger>
              <TabsTrigger value="indexers">
                {t('magazineDetail.tabIndexers')}
                <TabCountBadge n={manualSearchCounts.indexers} />
              </TabsTrigger>
              <TabsTrigger value="bookys">Bookys</TabsTrigger>
              <TabsTrigger value="telecharger_magazines">
                tm.org
              </TabsTrigger>
            </TabsList>

            {/* Search bar — only meaningful on the three
                free-text tabs. Scene-indexer tabs always scrape
                with the magazine's stored title (+ aliases) so
                the orchestrator stays in charge of the
                search-string fan-out; their button just says
                "Scan". */}
            {!isSceneTab(manualSearchTab) ? (
              <div className="flex gap-2 mt-3">
                <Input
                  value={manualSearchQuery}
                  onChange={(e) => setManualSearchQuery(e.target.value)}
                  placeholder={t('magazineDetail.searchPlaceholder')}
                  className="bg-zinc-900 border-zinc-700 text-zinc-100 flex-1"
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') handleManualSearch()
                  }}
                />
                <Button
                  onClick={() => handleManualSearch()}
                  disabled={manualSearching || !manualSearchQuery.trim()}
                >
                  {manualSearching ? (
                    <Loader2 className="size-4 animate-spin" />
                  ) : (
                    <Search className="size-4" />
                  )}
                  {t('common.search')}
                </Button>
              </div>
            ) : (
              <div className="flex gap-2 mt-3">
                <div className="flex-1 text-xs text-zinc-400 self-center">
                  Scrapes pressarr's configured{' '}
                  {manualSearchTab === 'bookys'
                    ? 'Bookys'
                    : 'telecharger-magazines.org'}{' '}
                  indexer for this magazine's title + aliases.
                </div>
                <Button
                  onClick={() => handleManualSearch()}
                  disabled={manualSearching}
                >
                  {manualSearching ? (
                    <Loader2 className="size-4 animate-spin" />
                  ) : (
                    <Search className="size-4" />
                  )}
                  Scan
                </Button>
              </div>
            )}

            {/* Scene-tab results — laid out like the indexer rows
                below, but their own render path: the row model
                (hoster links, status lifecycle) differs. */}
            {isSceneTab(manualSearchTab) &&
              (() => {
                const sorted = manualSearchDateSort
                  ? sortScene(sceneResults, manualSearchDateSort)
                  : sceneResults
                const nextDateSort =
                  manualSearchDateSort === '' ? 'desc' : manualSearchDateSort === 'desc' ? 'asc' : ''
                const dateSortLabel =
                  manualSearchDateSort === 'desc'
                    ? t('issues.sortDateDesc')
                    : manualSearchDateSort === 'asc'
                      ? t('issues.sortDateAsc')
                      : t('issues.sortDefault')
                return (
                  <>
                    {sceneResults.length > 0 && (
                      <div className="flex flex-wrap items-center gap-1.5 mt-3">
                        <span className="text-xs text-zinc-500">
                          {sceneResults.length} releases
                        </span>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="ml-auto h-6 px-2 text-xs text-zinc-400"
                          onClick={() =>
                            setManualSearchDateSort(nextDateSort as '' | 'asc' | 'desc')
                          }
                        >
                          <ArrowDownUp className="size-3 mr-1" />
                          {dateSortLabel}
                        </Button>
                      </div>
                    )}
                    <div className="mt-3 flex-1 overflow-y-auto">
                      {manualSearching ? (
                        <div className="flex items-center justify-center py-12">
                          <Loader2 className="size-6 animate-spin text-zinc-400" />
                          <span className="ml-2 text-zinc-400">{t('issues.searching')}</span>
                        </div>
                      ) : sorted.length === 0 ? (
                        <div className="rounded border border-dashed border-zinc-700 p-6 text-center text-sm text-zinc-400">
                          No releases yet. Click "Scan" to query the indexer.
                        </div>
                      ) : (
                        <div className="divide-y divide-zinc-800">
                          {sorted.map((r) => {
                            const size = formatSize(r.sizeBytes)
                            const isGrabbing = sceneGrabbing.has(r.id)
                            // Allow re-grab on ``grabbed`` too so the
                            // operator can re-dispatch when JD2 didn't
                            // pick up the previous crawljob (e.g. Folder
                            // Watch was off). Only ``imported`` hides
                            // the button — by then the file is in the
                            // library and there's nothing left to do.
                            const canGrab = r.status !== 'imported'
                            const grabLabel = r.status === 'grabbed' ? 'Re-grab' : t('issues.grab')
                            const meta = [
                              SCENE_SOURCE_LABELS[r.source] ?? r.source,
                              size,
                              r.fileFormat?.toUpperCase(),
                              r.language,
                              r.publishedAt ? formatPublishDate(r.publishedAt) : r.year,
                            ].filter(Boolean)
                            return (
                              <div
                                key={r.id}
                                className="flex flex-wrap items-center justify-between gap-2 py-3 px-2 hover:bg-zinc-900/50 rounded"
                              >
                                <div className="min-w-0 flex-1">
                                  <p className="text-sm text-zinc-100 break-words">
                                    {r.title}
                                    {r.status !== 'available' && (
                                      <Badge
                                        variant={
                                          r.status === 'imported'
                                            ? 'default'
                                            : r.status === 'grabbed'
                                              ? 'secondary'
                                              : 'destructive'
                                        }
                                        className="ml-2 align-middle text-[10px] uppercase tracking-wider"
                                      >
                                        {r.status}
                                      </Badge>
                                    )}
                                  </p>
                                  <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 mt-1 text-xs text-zinc-500">
                                    {meta.map((m, i) => (
                                      <Fragment key={i}>
                                        {i > 0 && <span>|</span>}
                                        <span>{m}</span>
                                      </Fragment>
                                    ))}
                                  </div>
                                  {r.hosterLinks.length > 0 && (
                                    <p className="mt-1 text-xs text-zinc-500 break-words">
                                      {r.hosterLinks.map((h) => h.hoster).join(' · ')}
                                    </p>
                                  )}
                                  {r.statusMessage && r.status === 'failed' && (
                                    <p className="mt-1 text-xs text-red-300">{r.statusMessage}</p>
                                  )}
                                </div>
                                <div className="flex flex-wrap gap-1.5">
                                  <Button variant="outline" size="sm" asChild>
                                    <a href={r.sourceUrl} target="_blank" rel="noreferrer">
                                      <ExternalLink className="size-3.5" />
                                    </a>
                                  </Button>
                                  {canGrab && (
                                    <Button
                                      variant="outline"
                                      size="sm"
                                      onClick={() => handleSceneGrab(r)}
                                      disabled={isGrabbing}
                                    >
                                      {isGrabbing ? (
                                        <Loader2 className="size-3.5 animate-spin" />
                                      ) : (
                                        <Download className="size-3.5" />
                                      )}
                                      {grabLabel}
                                    </Button>
                                  )}
                                </div>
                              </div>
                            )
                          })}
                        </div>
                      )}
                    </div>
                  </>
                )
              })()}

            {/* Results area (the existing SearchResult render
                path — only renders on the 3 free-text tabs;
                scene tabs handle their own list above). */}
            {!isSceneTab(manualSearchTab) &&
              (() => {
              const sources = [...new Set(manualSearchResults.map((r) => r.source || r.indexer).filter(Boolean))]
              const bySource = manualSearchSourceFilter
                ? manualSearchResults.filter((r) => (r.source || r.indexer) === manualSearchSourceFilter)
                : manualSearchResults
              const filtered = manualSearchDateSort ? sortByDate(bySource, manualSearchDateSort) : bySource
              const totalPages = Math.ceil(filtered.length / RESULTS_PER_PAGE)
              const nextDateSort = manualSearchDateSort === '' ? 'desc' : manualSearchDateSort === 'desc' ? 'asc' : ''
              const dateSortLabel = manualSearchDateSort === 'desc' ? t('issues.sortDateDesc') : manualSearchDateSort === 'asc' ? t('issues.sortDateAsc') : t('issues.sortDefault')
              return (
                <>
                  {manualSearchResults.length > 0 && (
                    <div className="flex flex-wrap items-center gap-1.5 mt-3">
                      {sources.length > 1 && (
                        <Badge
                          variant={manualSearchSourceFilter === '' ? 'default' : 'outline'}
                          className="cursor-pointer text-xs"
                          onClick={() => { setManualSearchSourceFilter(''); setManualSearchPage(1) }}
                        >
                          {t('issues.all')} ({manualSearchResults.length})
                        </Badge>
                      )}
                      {sources.map((src) => {
                        const count = manualSearchResults.filter((r) => (r.source || r.indexer) === src).length
                        return (
                          <Badge
                            key={src}
                            variant={manualSearchSourceFilter === src ? 'default' : 'outline'}
                            className="cursor-pointer text-xs"
                            onClick={() => { setManualSearchSourceFilter(src); setManualSearchPage(1) }}
                          >
                            {src} ({count})
                          </Badge>
                        )
                      })}
                      <Button
                        variant="ghost"
                        size="sm"
                        className="ml-auto h-6 px-2 text-xs text-zinc-400"
                        onClick={() => { setManualSearchDateSort(nextDateSort as '' | 'asc' | 'desc'); setManualSearchPage(1) }}
                      >
                        <ArrowDownUp className="size-3 mr-1" />
                        {dateSortLabel}
                      </Button>
                    </div>
                  )}
                  <div className="flex-1 overflow-y-auto mt-3">
                    {manualSearching ? (
                      <div className="flex items-center justify-center py-12">
                        <Loader2 className="size-6 animate-spin text-zinc-400" />
                        <span className="ml-2 text-zinc-400">{t('issues.searching')}</span>
                      </div>
                    ) : filtered.length === 0 && manualSearchResults.length === 0 ? (
                      <div className="py-8 space-y-2 text-center">
                        <p className="text-zinc-500">
                          {t('magazineDetail.manualSearchHint')}
                        </p>
                        <OtherTabsHint
                          activeTab={manualSearchTab}
                          counts={manualSearchCounts}
                          onSwitch={(tab) => {
                            setManualSearchTab(tab)
                            setManualSearchResults([])
                            setManualSearchPage(1)
                            setManualSearchSourceFilter('')
                            setManualSearchDateSort('')
                            if (manualSearchQuery.trim()) handleManualSearch(tab)
                          }}
                        />
                      </div>
                    ) : filtered.length === 0 ? (
                      <div className="py-8 space-y-2 text-center">
                        <p className="text-zinc-500">
                          {t('common.noResults')}
                        </p>
                        <OtherTabsHint
                          activeTab={manualSearchTab}
                          counts={manualSearchCounts}
                          onSwitch={(tab) => {
                            setManualSearchTab(tab)
                            setManualSearchResults([])
                            setManualSearchPage(1)
                            setManualSearchSourceFilter('')
                            setManualSearchDateSort('')
                            if (manualSearchQuery.trim()) handleManualSearch(tab)
                          }}
                        />
                      </div>
                    ) : (
                      <div className="divide-y divide-zinc-800">
                        {filtered
                          .slice((manualSearchPage - 1) * RESULTS_PER_PAGE, manualSearchPage * RESULTS_PER_PAGE)
                          .map((result) => (
                          <div
                            key={result.guid}
                            className={`flex items-center justify-between py-3 px-2 hover:bg-zinc-900/50 rounded ${
                              result.isBlocklisted ? 'opacity-40' : ''
                            }`}
                          >
                            <div className="min-w-0">
                              <p className="text-sm text-zinc-100 break-words">{result.title}</p>
                              <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 mt-1 text-xs text-zinc-500">
                                {result.source ? (
                                  <span>{result.source}</span>
                                ) : (
                                  <span>{result.indexer}</span>
                                )}
                                {result.size > 0 && (
                                  <>
                                    <span>|</span>
                                    <span>{formatBytes(result.size)}</span>
                                  </>
                                )}
                                {result.quality && result.quality !== 'unknown' && (
                                  <>
                                    <span>|</span>
                                    <span>{result.quality}</span>
                                  </>
                                )}
                                {result.language && result.language !== 'unknown' && (
                                  <>
                                    <span>|</span>
                                    <span>{result.language}</span>
                                  </>
                                )}
                                {result.seeders !== null && result.seeders > 0 && (
                                  <>
                                    <span>|</span>
                                    <span>
                                      {result.seeders} {result.protocol === 'ia' ? 'downloads' : t('issues.seeders')}
                                    </span>
                                  </>
                                )}
                                {result.publishDate && (
                                  <>
                                    <span>|</span>
                                    <span>{formatPublishDate(result.publishDate)}</span>
                                  </>
                                )}
                              </div>
                            </div>
                            <div className="flex flex-wrap gap-1.5 mt-2">
                              <Button
                                variant="outline"
                                size="sm"
                                disabled={result.isBlocklisted || grabbing === result.guid}
                                onClick={() => setGrabConfirm(result)}
                              >
                                {grabbing === result.guid ? (
                                  <Loader2 className="size-3.5 animate-spin" />
                                ) : (
                                  <Download className="size-3.5" />
                                )}
                                {t('issues.grab')}
                              </Button>
                              <Button
                                variant="outline"
                                size="sm"
                                disabled={magazine?.patterns?.some((p) => p.pattern === result.title)}
                                onClick={async () => {
                                  try {
                                    await addMagazinePattern(magazineId, {
                                      pattern: result.title,
                                      source: result.source || result.indexer || undefined,
                                    })
                                    toast.success(t('magazineDetail.patternSaved'))
                                    queryClient.invalidateQueries({ queryKey: ['magazine', magazineId] })
                                  } catch {
                                    toast.error(t('magazineDetail.patternAddError'))
                                  }
                                }}
                              >
                                {magazine?.patterns?.some((p) => p.pattern === result.title) ? (
                                  <Check className="size-3.5 text-green-400" />
                                ) : (
                                  <Plus className="size-3.5" />
                                )}
                                {t('magazineDetail.saveAsPattern')}
                              </Button>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                  {totalPages > 1 && (
                    <div className="flex items-center justify-center gap-2 pt-3 border-t border-zinc-800">
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={manualSearchPage <= 1}
                        onClick={() => setManualSearchPage((p) => p - 1)}
                      >
                        <ChevronLeft className="size-4" />
                      </Button>
                      <span className="text-xs text-zinc-400">
                        {t('issues.page', { page: manualSearchPage, totalPages })}
                      </span>
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={manualSearchPage >= totalPages}
                        onClick={() => setManualSearchPage((p) => p + 1)}
                      >
                        <ChevronRight className="size-4" />
                      </Button>
                    </div>
                  )}
                </>
              )
            })()}

            {/* TabsContent just for accessibility - content is shared above */}
            <TabsContent value="annasarchive" className="hidden" />
            <TabsContent value="internetarchive" className="hidden" />
            <TabsContent value="indexers" className="hidden" />
            <TabsContent value="bookys" className="hidden" />
            <TabsContent value="telecharger_magazines" className="hidden" />
          </Tabs>
        </DialogContent>
      </Dialog>

      {/* Edit Modal */}
      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent className="sm:max-w-lg bg-zinc-950 border-zinc-800 max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="text-zinc-100">
              {t('magazineDetail.editTitle')}
            </DialogTitle>
          </DialogHeader>

          <Tabs defaultValue="general" className="w-full">
            <TabsList className="w-full">
              <TabsTrigger value="general" className="flex-1">{t('magazineDetail.tabGeneral')}</TabsTrigger>
              <TabsTrigger value="cover" className="flex-1">{t('magazineDetail.tabCover')}</TabsTrigger>
            </TabsList>

            <TabsContent value="general">
              <div className="grid gap-4 py-2">
                <div className="grid gap-1.5">
                  <label className="text-sm font-medium text-zinc-300">
                    {t('addMagazine.magazineTitle')}
                  </label>
                  <Input
                    value={editTitle}
                    onChange={(e) => setEditTitle(e.target.value)}
                    className="bg-zinc-900 border-zinc-700 text-zinc-100"
                  />
                </div>

                <div className="flex items-center justify-between">
                  <label className="text-sm font-medium text-zinc-300">
                    {t('library.monitored')}
                  </label>
                  <Switch
                    checked={editMonitored}
                    onCheckedChange={(checked) => setEditMonitored(checked === true)}
                  />
                </div>

                <div className="flex items-center justify-between">
                  <div className="flex-1 pr-3">
                    <label className="text-sm font-medium text-zinc-300 block">
                      Recherche auto (wanted)
                    </label>
                    <p className="text-xs text-zinc-500 mt-0.5">
                      Pipeline auto Prowlarr + IA + rules. OFF = ce
                      magazine est ignoré par le scheduler et les
                      auto-triggers. Les recherches manuelles restent
                      possibles.
                    </p>
                  </div>
                  <Switch
                    checked={editWantedSearchEnabled}
                    onCheckedChange={(checked) => setEditWantedSearchEnabled(checked === true)}
                  />
                </div>

                <div className="border-t border-zinc-800 pt-3 space-y-4">
                  <div>
                    <h3 className="text-sm font-semibold text-zinc-200">
                      Recherche automatique
                    </h3>
                    <p className="text-xs text-zinc-500 mt-0.5">
                      Comportement du pipeline wanted → auto-grab pour ce magazine.
                    </p>
                  </div>

                  <div className="flex items-center justify-between">
                    <div className="flex-1 pr-3">
                      <label className="text-sm font-medium text-zinc-300 block">
                        Trier les résultats du plus récent au plus ancien
                      </label>
                      <p className="text-xs text-zinc-500 mt-0.5">
                        Le ranker IA voit d'abord les releases récents.
                        Défaut ON.
                      </p>
                    </div>
                    <Switch
                      checked={editSortByRecent}
                      onCheckedChange={(checked) => setEditSortByRecent(checked === true)}
                    />
                  </div>

                  {/* Bloc « Conditions pour auto-grab » — regroupe les
                      2 gates cumulatives avec un header explicite pour
                      lever la confusion : ce sont 2 filtres différents
                      qui doivent TOUS DEUX passer pour déclencher un
                      grab automatique. */}
                  <div className="rounded-lg border border-zinc-800 bg-zinc-900/30 p-3 grid gap-4">
                    <div>
                      <div className="text-sm font-semibold text-zinc-200">
                        Conditions pour auto-grab
                      </div>
                      <div className="text-[11px] text-zinc-500 mt-0.5">
                        Les 2 filtres ci-dessous sont <strong>cumulatifs</strong> :
                        le release doit passer <strong>les deux</strong> pour
                        que l'auto-grab se déclenche.
                      </div>
                    </div>

                    {/* Gate 1 : fuzzy titre release vs titre magazine */}
                    <div className="grid gap-1.5">
                      <div className="flex items-baseline justify-between">
                        <label className="text-sm font-medium text-zinc-300">
                          1. Similarité du titre release / magazine
                        </label>
                        <span className="text-xs font-mono text-zinc-400 tabular-nums">
                          {editMinTitleOverride === ''
                            ? 'Auto (80 %)'
                            : `${editMinTitleOverride} %`}
                        </span>
                      </div>
                      <input
                        type="range"
                        min={0}
                        max={100}
                        step={5}
                        value={editMinTitleOverride === '' ? 80 : Number(editMinTitleOverride)}
                        onChange={(e) => setEditMinTitleOverride(e.target.value)}
                        className="w-full accent-purple-500 h-2 rounded-lg bg-zinc-800 cursor-pointer"
                      />
                      <div className="flex justify-between text-[10px] text-zinc-600 tabular-nums">
                        <span>Souple (0)</span>
                        <span>Strict (100)</span>
                      </div>
                      <div className="flex items-start justify-between gap-2">
                        <p className="text-xs text-zinc-500 flex-1">
                          Compare fuzzy (Levenshtein) <strong>le nom
                          du fichier release</strong> vs <strong>le
                          titre du magazine</strong>. Bloque les grabs
                          off-topic : « Le Monde du Plein Air » vs
                          « Le Monde » donne ~35 %, refusé à 80. Monte
                          (90+) pour un mag ambigu, baisse (60-70) si le
                          nom est court ou stylisé.
                        </p>
                        {editMinTitleOverride !== '' && (
                          <button
                            type="button"
                            onClick={() => setEditMinTitleOverride('')}
                            className="text-xs text-purple-400 hover:text-purple-300 shrink-0"
                          >
                            Reset auto
                          </button>
                        )}
                      </div>
                    </div>

                    {/* Gate 2 : score composite Python + IA */}
                    <div className="grid gap-1.5">
                      <div className="flex items-baseline justify-between">
                        <label className="text-sm font-medium text-zinc-300">
                          2. Score composite Python + IA
                        </label>
                        <span className="text-xs font-mono text-zinc-400 tabular-nums">
                          {editAutoGrabThresholdOverride === ''
                            ? 'Auto (défaut global)'
                            : `${editAutoGrabThresholdOverride} %`}
                        </span>
                      </div>
                      <input
                        type="range"
                        min={0}
                        max={100}
                        step={1}
                        value={editAutoGrabThresholdOverride === '' ? 78 : Number(editAutoGrabThresholdOverride)}
                        onChange={(e) => setEditAutoGrabThresholdOverride(e.target.value)}
                        className="w-full accent-purple-500 h-2 rounded-lg bg-zinc-800 cursor-pointer"
                      />
                      <div className="flex justify-between text-[10px] text-zinc-600 tabular-nums">
                        <span>Permissif (0)</span>
                        <span>Strict (100)</span>
                      </div>
                      <div className="flex items-start justify-between gap-2">
                        <p className="text-xs text-zinc-500 flex-1">
                          Score <strong>composite</strong> agrégé par le
                          pipeline : parser Python (date, numéro, format,
                          quality, seeders) fusionné avec le verdict IA
                          ranker. Détermine la <strong>confiance globale</strong>
                          dans le winner. Baisse (65) pour un mag facile
                          à retrouver, monte (85+) pour un mag qui doit
                          rester prudent.
                        </p>
                        {editAutoGrabThresholdOverride !== '' && (
                          <button
                            type="button"
                            onClick={() => setEditAutoGrabThresholdOverride('')}
                            className="text-xs text-purple-400 hover:text-purple-300 shrink-0"
                          >
                            Reset auto
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                </div>


                <div className="grid gap-1.5">
                  <label className="text-sm font-medium text-zinc-300">
                    {t('addMagazine.qualityProfile')}
                  </label>
                  <Select value={editQualityProfileId} onValueChange={setEditQualityProfileId}>
                    <SelectTrigger className="bg-zinc-900 border-zinc-700 text-zinc-100 w-full">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {profiles.map((profile) => (
                        <SelectItem key={profile.id} value={String(profile.id)}>
                          {profile.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="grid gap-1.5">
                  <label className="text-sm font-medium text-zinc-300">ISSN</label>
                  <Input
                    value={editIssn}
                    onChange={(e) => setEditIssn(e.target.value)}
                    placeholder="1234-5678"
                    maxLength={9}
                    className="bg-zinc-900 border-zinc-700 text-zinc-100 font-mono"
                  />
                  <p className="text-xs text-zinc-500">
                    Numéro international standard du périodique (format 1234-5678). Utilisé par les recherches et l'enrichissement IA.
                  </p>
                </div>

                <div className="grid gap-1.5">
                  <label className="text-sm font-medium text-zinc-300">
                    {t('addMagazine.frequency')}
                  </label>
                  <Select value={editFrequency} onValueChange={setEditFrequency}>
                    <SelectTrigger className="bg-zinc-900 border-zinc-700 text-zinc-100 w-full">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="daily">{t('addMagazine.daily')}</SelectItem>
                      <SelectItem value="weekly">{t('addMagazine.weekly')}</SelectItem>
                      <SelectItem value="biweekly">{t('addMagazine.biweekly')}</SelectItem>
                      <SelectItem value="monthly">{t('addMagazine.monthly')}</SelectItem>
                      <SelectItem value="bimonthly">{t('addMagazine.bimonthly')}</SelectItem>
                      <SelectItem value="quarterly">{t('addMagazine.quarterly')}</SelectItem>
                      <SelectItem value="semiannual">{t('addMagazine.semiannual')}</SelectItem>
                      <SelectItem value="annual">{t('addMagazine.annual')}</SelectItem>
                      <SelectItem value="irregular">{t('addMagazine.irregular')}</SelectItem>
                    </SelectContent>
                  </Select>
                  {(() => {
                    const forecastableCount = issues.filter(
                      (i) => !i.isForecast && i.number !== null && (i.year !== null || i.publicationDate !== null)
                    ).length
                    return forecastableCount >= 2 ? (
                      <div className="flex items-center gap-1.5 text-xs text-emerald-400">
                        <CheckCircle2 className="h-3.5 w-3.5" />
                        <span>{t('magazineDetail.forecastConfirmed', { count: forecastableCount })}</span>
                      </div>
                    ) : (
                      <div className="flex items-center gap-1.5 text-xs text-zinc-400">
                        <HelpCircle className="h-3.5 w-3.5" />
                        <span>{t('magazineDetail.forecastInsufficient')}</span>
                      </div>
                    )
                  })()}
                  {estimatedFrequency && (
                    estimatedFrequency === editFrequency ? (
                      <div className="text-xs text-emerald-400">
                        {t('magazineDetail.estimatedFrequency', { frequency: t(`addMagazine.${estimatedFrequency}`) })}
                      </div>
                    ) : (
                      <div className="text-xs text-amber-400">
                        {t('magazineDetail.frequencyMismatch', {
                          estimated: t(`addMagazine.${estimatedFrequency}`),
                          current: t(`addMagazine.${editFrequency}`),
                        })}
                      </div>
                    )
                  )}
                  {editFrequency === 'daily' && (
                    <div className="grid gap-4 mt-2">
                      {/* Jours exclus — pas d'édition ce jour-là. */}
                      <div className="grid gap-1.5">
                        <label className="text-sm font-medium text-zinc-300">
                          Jours sans publication
                        </label>
                        <div className="flex gap-1 flex-wrap">
                          {[
                            [0, 'addMagazine.mon'],
                            [1, 'addMagazine.tue'],
                            [2, 'addMagazine.wed'],
                            [3, 'addMagazine.thu'],
                            [4, 'addMagazine.fri'],
                            [5, 'addMagazine.sat'],
                            [6, 'addMagazine.sun'],
                          ].map(([day, key]) => {
                            const d = day as number
                            const isEx = editExcludedDays.includes(d)
                            return (
                              <button
                                key={d}
                                type="button"
                                onClick={() => {
                                  const next = isEx
                                    ? editExcludedDays.filter((x) => x !== d)
                                    : [...editExcludedDays, d]
                                  setEditExcludedDays(next)
                                  // Si on ajoute à excluded, retire des groupes
                                  if (!isEx) {
                                    setEditIssueGroups(
                                      editIssueGroups
                                        .map((g) => ({
                                          ...g,
                                          days: g.days.filter((x) => x !== d),
                                        }))
                                        .filter((g) => g.days.length > 0),
                                    )
                                  }
                                }}
                                className={
                                  'px-2 py-1 text-xs rounded border transition-colors ' +
                                  (isEx
                                    ? 'bg-red-900/50 border-red-700 text-red-300'
                                    : 'bg-zinc-900 border-zinc-700 text-zinc-400 hover:border-zinc-600')
                                }
                              >
                                {t(key as string)}
                              </button>
                            )
                          })}
                        </div>
                        <p className="text-xs text-zinc-500">
                          Jours rouges = pas d'édition (ex. dimanche pour
                          la plupart des quotidiens FR).
                        </p>
                      </div>

                      {/* Groupes d'issues combinées — multi. */}
                      <div className="grid gap-1.5">
                        <label className="text-sm font-medium text-zinc-300">
                          Groupes d'issues combinées
                        </label>
                        <p className="text-xs text-zinc-500">
                          Regroupe plusieurs jours consécutifs en <strong>1
                          seule issue</strong> émise sur le dernier jour du
                          groupe. Ex. Le Monde : groupe (dim + lun) pour
                          l'édition weekend combinée, groupe (sam) taggé
                          « WEEK-END » pour l'édition papier séparée du
                          samedi.
                        </p>
                        <IssueGroupsEditor
                          groups={editIssueGroups}
                          excluded={editExcludedDays}
                          onChange={(next) =>
                            setEditIssueGroups(next.map((g) => ({ ...g, label: g.label ?? null })))
                          }
                        />
                      </div>
                    </div>
                  )}
                  {['weekly', 'biweekly'].includes(editFrequency) && (
                    <div className="grid gap-1.5 mt-2">
                      <label className="text-sm font-medium text-zinc-300">
                        Jour de publication
                      </label>
                      <div className="flex flex-wrap gap-1">
                        <button
                          type="button"
                          onClick={() => setEditReleaseWeekday(null)}
                          className={`px-2 py-1 text-xs rounded border ${
                            editReleaseWeekday == null
                              ? 'bg-purple-900/50 border-purple-600 text-purple-200'
                              : 'bg-zinc-900 border-zinc-700 text-zinc-400'
                          }`}
                        >
                          Auto
                        </button>
                        {([
                          [0, 'addMagazine.mon'],
                          [1, 'addMagazine.tue'],
                          [2, 'addMagazine.wed'],
                          [3, 'addMagazine.thu'],
                          [4, 'addMagazine.fri'],
                          [5, 'addMagazine.sat'],
                          [6, 'addMagazine.sun'],
                        ] as [number, string][]).map(([day, key]) => (
                          <button
                            key={day}
                            type="button"
                            onClick={() => setEditReleaseWeekday(day)}
                            className={`px-2 py-1 text-xs rounded border ${
                              editReleaseWeekday === day
                                ? 'bg-purple-900/50 border-purple-600 text-purple-200'
                                : 'bg-zinc-900 border-zinc-700 text-zinc-400'
                            }`}
                          >
                            {t(key)}
                          </button>
                        ))}
                      </div>
                      <p className="text-xs text-zinc-500">
                        Auto = déduit du dernier numéro connu ou de la date de début de suivi. Sinon les prévisions s'alignent sur ce jour.
                      </p>
                    </div>
                  )}
                </div>

                <div className="grid gap-1.5">
                  <label className="text-sm font-medium text-zinc-300">
                    {t('addMagazine.rootFolder')}
                  </label>
                  <Select value={editRootFolderPath} onValueChange={setEditRootFolderPath}>
                    <SelectTrigger
                      className="bg-zinc-900 border-zinc-700 text-zinc-100 w-full min-w-0 max-w-full [&>span]:truncate"
                      title={editRootFolderPath}
                    >
                      <SelectValue>
                        {editRootFolderPath ? shortenPath(editRootFolderPath, 40) : ''}
                      </SelectValue>
                    </SelectTrigger>
                    <SelectContent>
                      {rootFolders.map((folder) => (
                        <SelectItem key={folder.id} value={folder.path}>
                          {shortenPath(folder.path, 50)}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="grid gap-1.5">
                  <label className="text-sm font-medium text-zinc-300">
                    {t('magazineDetail.monitoringStartDate')}
                  </label>
                  <Input
                    type="date"
                    value={editMonitoringStartDate}
                    onChange={(e) => setEditMonitoringStartDate(e.target.value)}
                    className="bg-zinc-900 border-zinc-700 text-zinc-100"
                  />
                </div>
              </div>
            </TabsContent>

            <TabsContent value="cover">
              <div className="grid gap-4 py-2">
                <div className="flex items-center justify-between">
                  <div>
                    <label className="text-sm font-medium text-zinc-300">
                      {t('magazineDetail.useLatestIssueCover')}
                    </label>
                    <p className="text-xs text-zinc-500">
                      {t('magazineDetail.useLatestIssueCoverDesc')}
                    </p>
                  </div>
                  <Switch
                    checked={editUseLatestCover}
                    onCheckedChange={(checked) => setEditUseLatestCover(checked === true)}
                  />
                </div>

                {!editUseLatestCover && (
                  <div className="grid gap-1.5">
                    <label className="text-sm font-medium text-zinc-300">
                      {t('magazineDetail.selectCover')}
                    </label>
                    {issuesWithCovers.length === 0 ? (
                      <p className="text-sm text-zinc-500">{t('magazineDetail.noIssueCovers')}</p>
                    ) : (
                      <div className="grid grid-cols-4 gap-2 max-h-72 overflow-y-auto pr-1">
                        {issuesWithCovers.map((issue) => {
                          const isSelected = editCoverIssueId === issue.id
                          const isCurrent = editCoverIssueId == null && magazine?.coverPath === issue.coverPath
                          return (
                            <button
                              key={issue.id}
                              type="button"
                              onClick={() => setEditCoverIssueId(issue.id)}
                              className={`rounded border-2 overflow-hidden transition-colors ${
                                isSelected
                                  ? 'border-blue-500'
                                  : isCurrent
                                    ? 'border-emerald-500'
                                    : 'border-zinc-700 hover:border-zinc-500'
                              }`}
                            >
                              <img
                                src={getIssueCoverUrl(issue.id)}
                                alt={`#${issue.number ?? '?'}`}
                                className="w-full aspect-[3/4] object-cover"
                              />
                              <div className="text-xs text-center text-zinc-400 py-0.5">
                                #{issue.number ?? '?'}
                              </div>
                            </button>
                          )
                        })}
                      </div>
                    )}
                  </div>
                )}

                {!editUseLatestCover && (
                  <>
                    <div className="relative flex items-center py-2">
                      <div className="flex-grow border-t border-zinc-700" />
                      <span className="mx-3 text-xs text-zinc-500 shrink-0">
                        {t('magazineDetail.orSeparator')}
                      </span>
                      <div className="flex-grow border-t border-zinc-700" />
                    </div>

                    <div className="flex items-center gap-2">
                      <input
                        ref={coverFileRef}
                        type="file"
                        accept="image/jpeg,image/png,image/webp"
                        className="hidden"
                        onChange={handleCoverFileChange}
                      />
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        disabled={coverUploading}
                        onClick={() => coverFileRef.current?.click()}
                      >
                        {coverUploading ? (
                          <Loader2 className="h-4 w-4 animate-spin mr-1" />
                        ) : (
                          <Upload className="h-4 w-4 mr-1" />
                        )}
                        {t('magazineDetail.uploadCover')}
                      </Button>
                    </div>

                    <div className="flex items-center gap-2">
                      <Input
                        placeholder={t('magazineDetail.coverUrl')}
                        value={coverUrl}
                        onChange={(e) => setCoverUrl(e.target.value)}
                        className="bg-zinc-900 border-zinc-700 text-zinc-100 flex-1"
                        onKeyDown={(e) => e.key === 'Enter' && handleCoverUrlLoad()}
                      />
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        disabled={coverUploading || !coverUrl.trim()}
                        onClick={handleCoverUrlLoad}
                      >
                        {t('magazineDetail.coverUrlLoad')}
                      </Button>
                    </div>
                  </>
                )}
              </div>
            </TabsContent>
          </Tabs>

          <DialogFooter>
            <Button variant="outline" onClick={() => setEditOpen(false)}>
              {t('common.cancel')}
            </Button>
            <Button
              onClick={handleSaveEdit}
              disabled={!editTitle.trim() || updateMagazineMutation.isPending}
            >
              {t('common.save')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Issue Dialog — 2 onglets : Métadonnées + Fiche technique */}
      <Dialog open={editIssueOpen} onOpenChange={(open) => {
        setEditIssueOpen(open)
        if (!open) setEditingIssue(null)
      }}>
        <DialogContent className="sm:max-w-2xl bg-zinc-950 border-zinc-800 max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="text-zinc-100">
              {t('issues.editIssueTitle')}
              {editingIssue?.number != null && (
                <span className="text-sm text-zinc-500 ml-2 font-normal">
                  #{editingIssue.number}
                </span>
              )}
            </DialogTitle>
          </DialogHeader>
          <Tabs defaultValue="metadata" className="w-full">
            <TabsList className="w-full">
              <TabsTrigger value="metadata" className="flex-1">Métadonnées</TabsTrigger>
              <TabsTrigger value="technical" className="flex-1">Fiche technique</TabsTrigger>
            </TabsList>
            <TabsContent value="metadata" className="pt-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-zinc-400">{t('issues.editNumber')}</label>
              <Input
                type="number"
                value={editIssueNumber}
                onChange={(e) => setEditIssueNumber(e.target.value)}
                className="bg-zinc-900 border-zinc-700 text-zinc-100"
              />
            </div>
            <div>
              <label className="text-xs text-zinc-400">{t('issues.editVolume')}</label>
              <Input
                type="number"
                value={editIssueVolume}
                onChange={(e) => setEditIssueVolume(e.target.value)}
                className="bg-zinc-900 border-zinc-700 text-zinc-100"
              />
            </div>
            <div className="col-span-2">
              <label className="text-xs text-zinc-400">{t('issues.editTitle')}</label>
              <Input
                value={editIssueTitle}
                onChange={(e) => setEditIssueTitle(e.target.value)}
                className="bg-zinc-900 border-zinc-700 text-zinc-100"
              />
            </div>
            <div className="col-span-2">
              <label className="text-xs text-zinc-400">Sous-titre</label>
              <Input
                value={editIssueSubtitle}
                onChange={(e) => setEditIssueSubtitle(e.target.value)}
                placeholder="Accroche éditoriale sous le titre"
                className="bg-zinc-900 border-zinc-700 text-zinc-100"
              />
            </div>
            <div>
              <label className="text-xs text-zinc-400">Prix</label>
              <Input
                value={editIssuePrice}
                onChange={(e) => setEditIssuePrice(e.target.value)}
                placeholder="3,50 €"
                className="bg-zinc-900 border-zinc-700 text-zinc-100"
              />
            </div>
            <div>
              <label className="text-xs text-zinc-400">ISSN</label>
              <Input
                value={editIssueIssn}
                onChange={(e) => setEditIssueIssn(e.target.value)}
                placeholder="1234-5678"
                maxLength={9}
                className="bg-zinc-900 border-zinc-700 text-zinc-100 font-mono"
              />
            </div>
            <div>
              <label className="text-xs text-zinc-400">{t('issues.editYear')}</label>
              <Input
                type="number"
                value={editIssueYear}
                onChange={(e) => setEditIssueYear(e.target.value)}
                className="bg-zinc-900 border-zinc-700 text-zinc-100"
              />
            </div>
            <div>
              <label className="text-xs text-zinc-400">{t('issues.editMonth')}</label>
              <Input
                type="number"
                min={1}
                max={12}
                value={editIssueMonth}
                onChange={(e) => setEditIssueMonth(e.target.value)}
                className="bg-zinc-900 border-zinc-700 text-zinc-100"
              />
            </div>
            <div>
              <label className="text-xs text-zinc-400">{t('issues.editDay')}</label>
              <Input
                type="number"
                min={1}
                max={31}
                value={editIssueDay}
                onChange={(e) => setEditIssueDay(e.target.value)}
                className="bg-zinc-900 border-zinc-700 text-zinc-100"
              />
            </div>
            <div className="col-span-2 flex items-center gap-2">
              <Switch
                checked={editIssueSpecial}
                onCheckedChange={setEditIssueSpecial}
              />
              <label className="text-sm text-zinc-300">{t('issues.editSpecial')}</label>
            </div>
            <div className="col-span-2">
              <label className="text-xs text-zinc-400">{t('issues.editStatus')}</label>
              <Select value={editIssueStatus} onValueChange={setEditIssueStatus}>
                <SelectTrigger className="bg-zinc-900 border-zinc-700 text-zinc-100">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="wanted">{t('status.wanted')}</SelectItem>
                  <SelectItem value="missing">{t('status.missing')}</SelectItem>
                  <SelectItem value="snatched">{t('status.snatched')}</SelectItem>
                  <SelectItem value="available">{t('status.available')}</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {/* Queue/grab info for snatched issues */}
            {editingIssue && !editingIssue.file && editingIssue.status === 'snatched' && (() => {
              const qi = queueByIssueId.get(editingIssue.id)
              return qi ? (
                <div className="col-span-2">
                  <label className="text-xs text-zinc-400">{t('issues.grabSource')}</label>
                  <p className="text-sm text-zinc-300 bg-zinc-900 border border-zinc-700 rounded-md px-3 py-2 break-all">
                    {qi.title}
                  </p>
                  <p className="text-xs text-zinc-500 mt-1">
                    {qi.downloadClient} — {qi.status} ({qi.progress}%)
                  </p>
                </div>
              ) : (
                <div className="col-span-2">
                  <p className="text-xs text-amber-400">{t('issues.noActiveDownload')}</p>
                </div>
              )
            })()}
            {editingIssue?.file && (
              <>
                <div className="col-span-2">
                  <label className="text-xs text-zinc-400">{t('issues.editFilename')}</label>
                  <Input
                    value={editIssueFilename}
                    onChange={(e) => setEditIssueFilename(e.target.value)}
                    className="bg-zinc-900 border-zinc-700 text-zinc-100"
                  />
                </div>
                <div>
                  <label className="text-xs text-zinc-400">{t('issues.editQuality')}</label>
                  <Input
                    value={editIssueQuality}
                    onChange={(e) => setEditIssueQuality(e.target.value)}
                    className="bg-zinc-900 border-zinc-700 text-zinc-100"
                  />
                </div>
                <div>
                  <label className="text-xs text-zinc-400">{t('issues.editFormat')}</label>
                  <Input
                    value={editIssueFormat}
                    onChange={(e) => setEditIssueFormat(e.target.value)}
                    className="bg-zinc-900 border-zinc-700 text-zinc-100"
                  />
                </div>
                <div>
                  <label className="text-xs text-zinc-400">{t('issues.editReleaseGroup')}</label>
                  <Input
                    value={editIssueReleaseGroup}
                    onChange={(e) => setEditIssueReleaseGroup(e.target.value)}
                    className="bg-zinc-900 border-zinc-700 text-zinc-100"
                  />
                </div>
                <div>
                  <label className="text-xs text-zinc-400">{t('issues.editLanguage')}</label>
                  <Input
                    value={editIssueLanguage}
                    onChange={(e) => setEditIssueLanguage(e.target.value)}
                    className="bg-zinc-900 border-zinc-700 text-zinc-100"
                  />
                </div>
              </>
            )}
          </div>
            </TabsContent>
            <TabsContent value="technical" className="pt-3">
              <IssueTechnicalDetail issueId={editingIssue?.id ?? null} />
            </TabsContent>
          </Tabs>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditIssueOpen(false)}>
              {t('common.cancel')}
            </Button>
            <Button
              onClick={handleSaveIssue}
              disabled={updateIssueMutation.isPending}
            >
              {t('common.save')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Issue / File Confirmation Dialog */}
      <Dialog open={deleteFileOpen} onOpenChange={(open) => {
        setDeleteFileOpen(open)
        if (!open) setDeleteFileIssueId(null)
      }}>
        <DialogContent className="sm:max-w-md bg-zinc-950 border-zinc-800">
          {(() => {
            const targetIssue = issues.find((i) => i.id === deleteFileIssueId)
            const hasFile = !!targetIssue?.file
            const isBusy = deleteFileMutation.isPending || deleteIssueMutation.isPending
            return (
              <>
                <DialogHeader>
                  <DialogTitle className="text-zinc-100">
                    {hasFile ? t('issues.deleteFileTitle') : t('issues.deleteIssueTitle')}
                  </DialogTitle>
                </DialogHeader>
                <p className="text-sm text-zinc-400">
                  {hasFile ? t('issues.deleteFileConfirm') : t('issues.deleteIssueConfirm')}
                </p>
                <div className="flex flex-col gap-2 mt-2">
                  {hasFile && (
                    <>
                      <Button
                        variant="outline"
                        className="justify-start text-left h-auto py-3"
                        disabled={isBusy}
                        onClick={() => {
                          if (deleteFileIssueId != null)
                            deleteFileMutation.mutate({ issueId: deleteFileIssueId, unmonitor: false })
                        }}
                      >
                        <div>
                          <div className="font-medium text-zinc-100">{t('issues.deleteFileOnly')}</div>
                          <div className="text-xs text-zinc-500 font-normal">{t('issues.deleteFileOnlyDesc')}</div>
                        </div>
                      </Button>
                      <Button
                        variant="outline"
                        className="justify-start text-left h-auto py-3"
                        disabled={isBusy}
                        onClick={() => {
                          if (deleteFileIssueId != null)
                            deleteFileMutation.mutate({ issueId: deleteFileIssueId, unmonitor: true })
                        }}
                      >
                        <div>
                          <div className="font-medium text-zinc-100">{t('issues.deleteFileAndUnmonitor')}</div>
                          <div className="text-xs text-zinc-500 font-normal">{t('issues.deleteFileAndUnmonitorDesc')}</div>
                        </div>
                      </Button>
                    </>
                  )}
                  <Button
                    variant="destructive"
                    className="justify-start text-left h-auto py-3"
                    disabled={isBusy}
                    onClick={() => {
                      if (deleteFileIssueId != null)
                        deleteIssueMutation.mutate(deleteFileIssueId)
                    }}
                  >
                    <div>
                      <div className="font-medium">{t('issues.deleteIssue')}</div>
                      <div className="text-xs opacity-80 font-normal">{t('issues.deleteIssueDesc')}</div>
                    </div>
                  </Button>
                </div>
              </>
            )
          })()}
          <DialogFooter>
            <Button variant="ghost" onClick={() => setDeleteFileOpen(false)}>
              {t('common.cancel')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <DialogContent className="sm:max-w-md bg-zinc-950 border-zinc-800">
          <DialogHeader>
            <DialogTitle className="text-zinc-100">
              {t('magazineDetail.deleteTitle')}
            </DialogTitle>
          </DialogHeader>
          <p className="text-sm text-zinc-400">
            {t('magazineDetail.deleteConfirm', { title: magazine?.title })}
          </p>
          <div className="flex items-center gap-2 mt-2">
            <input
              type="checkbox"
              id="deleteFiles"
              checked={deleteFiles}
              onChange={(e) => setDeleteFiles(e.target.checked)}
              className="size-4 rounded border-zinc-600 bg-zinc-900 accent-[#7C3AED]"
            />
            <label htmlFor="deleteFiles" className="text-sm text-zinc-300">
              {t('magazineDetail.deleteFiles')}
            </label>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteOpen(false)}>
              {t('common.cancel')}
            </Button>
            <Button
              variant="destructive"
              disabled={deleteMagazineMutation.isPending}
              onClick={() => deleteMagazineMutation.mutate()}
            >
              {t('common.delete')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Issue Viewer */}
      <IssueViewer
        issueId={viewerIssueId}
        open={viewerOpen}
        onOpenChange={setViewerOpen}
      />

      {/* History modals */}
      <HistoryModal
        open={historyMagazineOpen}
        onOpenChange={setHistoryMagazineOpen}
        magazineId={magazine?.id}
        title={`${t('history.title')} — ${magazine?.title ?? ''}`}
      />
      <HistoryModal
        open={historyIssueOpen}
        onOpenChange={setHistoryIssueOpen}
        magazineId={magazine?.id}
        issueId={historyIssueId ?? undefined}
        title={`${t('history.title')} — ${magazine?.title ?? ''} #${issues.find(i => i.id === historyIssueId)?.number ?? historyIssueId ?? ''}`}
      />

      {/* Recherche wanted (pipeline unifié) */}
      <WantedSearchNowModal
        issueId={wantedSearchIssueId}
        magazineId={magazine?.id}
        onClose={() => setWantedSearchIssueId(null)}
      />

      {/* File Manager modal */}
      <FileManagerModal
        open={fileManagerOpen}
        onOpenChange={setFileManagerOpen}
        magazineId={magazineId}
        issues={issues}
        magazineTitle={magazine?.title ?? ''}
      />

      {/* Refresh IA batch modal */}
      <AIRefreshModal
        open={aiRefreshOpen}
        onClose={() => setAiRefreshOpen(false)}
        magazineId={magazineId}
        magazineTitle={magazine?.title ?? ''}
        issues={issues}
        onDone={() => {
          queryClient.invalidateQueries({ queryKey: ['magazine', magazineId] })
          queryClient.invalidateQueries({ queryKey: ['issues', magazineId] })
        }}
      />

      {/* Manual grab confirmation — chooses the target issue BEFORE
          the download starts, so a « 12 août » torrent doesn't end up
          bound to a « 1er août » issue via parser guess. */}
      {grabConfirm && (
        <ManualGrabConfirmDialog
          release={grabConfirm}
          issues={issues}
          isPending={grabbing === grabConfirm.guid}
          onClose={() => setGrabConfirm(null)}
          onConfirm={(overrides) => handleGrab(grabConfirm, true, overrides)}
        />
      )}

    </div>
  )
}


// ---------------------------------------------------------------------------
// Patterns Tab
// ---------------------------------------------------------------------------

function MagazinePatternsTab({ magazine, magazineId }: { magazine: Magazine; magazineId: number }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()

  // Inline edit state for patterns
  const [editingPatternId, setEditingPatternId] = useState<number | null>(null)
  const [editPatternValue, setEditPatternValue] = useState('')

  // Search state
  const [query, setQuery] = useState(magazine.title || '')
  const [results, setResults] = useState<SearchResult[]>([])
  const [searchingPatterns, setSearchingPatterns] = useState(false)
  const [savingPattern, setSavingPattern] = useState<string | null>(null)
  const [searchSource, setSearchSource] = useState('indexers')
  const [sourceFilter, setSourceFilter] = useState('')
  const [dateSort, setDateSort] = useState<'' | 'asc' | 'desc'>('')
  const [page, setPage] = useState(1)

  async function handleSearch() {
    if (!query.trim()) return
    setSearchingPatterns(true)
    setResults([])
    setPage(1)
    setSourceFilter('')
    setDateSort('')
    try {
      let data: SearchResult[]
      switch (searchSource) {
        case 'internetarchive':
          data = await searchInternetArchive(query.trim())
          break
        case 'annasarchive':
          data = await searchAnnasArchive(query.trim())
          break
        default:
          data = await searchIndexers(query.trim())
      }
      setResults(data)
    } catch {
      toast.error(t('issues.searchError'))
    } finally {
      setSearchingPatterns(false)
    }
  }

  async function handleSavePattern(result: SearchResult) {
    setSavingPattern(result.guid)
    try {
      await addMagazinePattern(magazineId, {
        pattern: result.title,
        source: result.indexer || result.source || undefined,
      })
      toast.success(t('magazineDetail.patternAdded'))
      queryClient.invalidateQueries({ queryKey: ['magazine', magazineId] })
    } catch {
      toast.error(t('magazineDetail.patternAddError'))
    } finally {
      setSavingPattern(null)
    }
  }

  function isAlreadyPattern(result: SearchResult) {
    return magazine.patterns?.some((p) => p.pattern === result.title) ?? false
  }

  async function handleDelete(patternId: number) {
    try {
      await deleteMagazinePattern(magazineId, patternId)
      toast.success(t('magazineDetail.patternDeleted'))
      queryClient.invalidateQueries({ queryKey: ['magazine', magazineId] })
    } catch {
      toast.error(t('magazineDetail.patternDeleteError'))
    }
  }

  async function handleConvertToBanRule(pattern: { id: number }) {
    try {
      await convertPatternToExcludeRule(magazineId, pattern.id)
      toast.success(t('magazineDetail.patternConvertedToBan'))
      queryClient.invalidateQueries({ queryKey: ['magazine', magazineId] })
    } catch {
      toast.error(t('magazineDetail.patternConvertToBanError'))
    }
  }

  async function handleSavePatternEdit(patternId: number) {
    if (!editPatternValue.trim()) return
    try {
      await updateMagazinePattern(magazineId, patternId, { pattern: editPatternValue.trim() })
      toast.success(t('magazineDetail.patternUpdated'))
      setEditingPatternId(null)
      queryClient.invalidateQueries({ queryKey: ['magazine', magazineId] })
    } catch {
      toast.error(t('magazineDetail.patternUpdateError'))
    }
  }

  const sources = [...new Set(results.map((r) => r.source || r.indexer).filter(Boolean))]
  const bySource = sourceFilter
    ? results.filter((r) => (r.source || r.indexer) === sourceFilter)
    : results
  const filtered = dateSort ? sortByDate(bySource, dateSort) : bySource
  const totalPages = Math.ceil(filtered.length / RESULTS_PER_PAGE)
  const nextDateSort = dateSort === '' ? 'desc' : dateSort === 'desc' ? 'asc' : ''
  const dateSortLabel = dateSort === 'desc' ? t('issues.sortDateDesc') : dateSort === 'asc' ? t('issues.sortDateAsc') : t('issues.sortDefault')

  return (
    <div className="pt-4 space-y-6">
      {/* Saved patterns table */}
      <div>
        <p className="text-sm text-zinc-400 mb-3">
          {t('magazineDetail.patterns', { count: magazine.patterns?.length ?? 0 })}
        </p>
        {magazine.patterns && magazine.patterns.length > 0 ? (
          <Table>
            <TableHeader>
              <TableRow className="border-zinc-800 hover:bg-transparent">
                <TableHead className="text-zinc-400">Pattern</TableHead>
                <TableHead className="text-zinc-400 w-32">{t('magazineDetail.source')}</TableHead>
                <TableHead className="text-zinc-400 w-32">{t('magazineDetail.uploader')}</TableHead>
                <TableHead className="text-zinc-400 w-36">{t('history.date')}</TableHead>
                <TableHead className="text-zinc-400 w-20" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {magazine.patterns.map((p) => (
                <TableRow key={p.id} className="border-zinc-800">
                  <TableCell className="text-zinc-100 text-sm">
                    {editingPatternId === p.id ? (
                      <div className="flex items-center gap-2">
                        <Input
                          value={editPatternValue}
                          onChange={(e) => setEditPatternValue(e.target.value)}
                          className="bg-zinc-900 border-zinc-700 text-zinc-100 text-sm h-8"
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') handleSavePatternEdit(p.id)
                            if (e.key === 'Escape') setEditingPatternId(null)
                          }}
                          autoFocus
                        />
                        <button type="button" onClick={() => handleSavePatternEdit(p.id)} className="p-1 text-zinc-500 hover:text-green-400">
                          <Check className="size-4" />
                        </button>
                        <button type="button" onClick={() => setEditingPatternId(null)} className="p-1 text-zinc-500 hover:text-zinc-300">
                          <X className="size-4" />
                        </button>
                      </div>
                    ) : (
                      <span className="line-clamp-2">{p.pattern}</span>
                    )}
                  </TableCell>
                  <TableCell className="text-zinc-400 text-sm">{p.source || '-'}</TableCell>
                  <TableCell className="text-zinc-400 text-sm">{p.uploader || '-'}</TableCell>
                  <TableCell className="text-zinc-500 text-sm">
                    {new Date(p.lastSeenAt).toLocaleDateString()}
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-1">
                      <button
                        type="button"
                        onClick={() => { setEditingPatternId(p.id); setEditPatternValue(p.pattern) }}
                        className="p-1 text-zinc-500 hover:text-zinc-300"
                        title={t('common.edit')}
                      >
                        <Pencil className="size-4" />
                      </button>
                      <button
                        type="button"
                        onClick={() => handleConvertToBanRule(p)}
                        className="p-1 text-zinc-500 hover:text-amber-400"
                        title={t('magazineDetail.convertToBanRule')}
                      >
                        <Ban className="size-4" />
                      </button>
                      <button
                        type="button"
                        onClick={() => handleDelete(p.id)}
                        className="p-1 text-zinc-500 hover:text-red-400"
                        title={t('common.delete')}
                      >
                        <X className="size-4" />
                      </button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        ) : (
          <p className="text-sm text-zinc-500 text-center py-4">{t('magazineDetail.noPatterns')}</p>
        )}
      </div>

      {/* Search interface to find & save patterns */}
      <div className="border-t border-zinc-800 pt-4 space-y-4">
        <p className="text-sm font-medium text-zinc-300">{t('magazineDetail.addPattern')}</p>

        {/* Source tabs */}
        <div className="flex flex-wrap gap-2">
          {['indexers', 'internetarchive', 'annasarchive'].map((src) => (
            <button
              key={src}
              type="button"
              onClick={() => { setSearchSource(src); setResults([]); setPage(1); setSourceFilter(''); setDateSort('') }}
              className={`px-3 py-1.5 text-sm rounded-md transition-colors whitespace-nowrap ${
                searchSource === src
                  ? 'bg-[#7C3AED] text-white'
                  : 'bg-zinc-900 text-zinc-400 hover:text-zinc-100'
              }`}
            >
              {src === 'indexers' ? t('magazineDetail.tabIndexers') :
               src === 'internetarchive' ? t('magazineDetail.tabInternetArchive') :
               t('magazineDetail.tabAnnasArchive')}
            </button>
          ))}
        </div>

        {/* Search input */}
        <div className="flex gap-2">
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') handleSearch() }}
            placeholder={t('magazineDetail.searchPlaceholder')}
            className="bg-zinc-900 border-zinc-700 text-zinc-100 flex-1"
          />
          <Button onClick={handleSearch} disabled={searchingPatterns || !query.trim()}>
            {searchingPatterns ? <Loader2 className="size-4 animate-spin" /> : <Search className="size-4" />}
            {t('common.search')}
          </Button>
        </div>

        {/* Source filter badges + date sort */}
        {results.length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5">
            {sources.length > 1 && (
              <Badge
                variant={sourceFilter === '' ? 'default' : 'outline'}
                className="cursor-pointer text-xs"
                onClick={() => { setSourceFilter(''); setPage(1) }}
              >
                {t('issues.all')} ({results.length})
              </Badge>
            )}
            {sources.map((src) => {
              const count = results.filter((r) => (r.source || r.indexer) === src).length
              return (
                <Badge
                  key={src}
                  variant={sourceFilter === src ? 'default' : 'outline'}
                  className="cursor-pointer text-xs"
                  onClick={() => { setSourceFilter(src); setPage(1) }}
                >
                  {src} ({count})
                </Badge>
              )
            })}
            <Button
              variant="ghost"
              size="sm"
              className="ml-auto h-6 px-2 text-xs text-zinc-400"
              onClick={() => { setDateSort(nextDateSort as '' | 'asc' | 'desc'); setPage(1) }}
            >
              <ArrowDownUp className="size-3 mr-1" />
              {dateSortLabel}
            </Button>
          </div>
        )}

        {/* Results */}
        {searchingPatterns ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="size-6 animate-spin text-zinc-400" />
            <span className="ml-2 text-zinc-400">{t('issues.searching')}</span>
          </div>
        ) : filtered.length === 0 && results.length === 0 ? (
          <p className="text-sm text-zinc-500">{t('magazineDetail.patternSearchHint')}</p>
        ) : filtered.length === 0 ? (
          <p className="text-sm text-zinc-500 text-center py-8">{t('common.noResults')}</p>
        ) : (
          <div className="divide-y divide-zinc-800">
            {filtered
              .slice((page - 1) * RESULTS_PER_PAGE, page * RESULTS_PER_PAGE)
              .map((result) => {
                const alreadySaved = isAlreadyPattern(result)
                return (
                  <div
                    key={result.guid}
                    className={`py-3 px-2 hover:bg-zinc-900/50 rounded ${
                      result.isBlocklisted ? 'opacity-40' : ''
                    }`}
                  >
                    <div className="min-w-0">
                      <p className="text-sm text-zinc-100 break-words">{result.title}</p>
                      <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 mt-1 text-xs text-zinc-500">
                        {result.source ? (
                          <span>{result.source}</span>
                        ) : (
                          <span>{result.indexer}</span>
                        )}
                        {result.size > 0 && (
                          <>
                            <span>|</span>
                            <span>{formatBytes(result.size)}</span>
                          </>
                        )}
                        {result.quality && result.quality !== 'unknown' && (
                          <>
                            <span>|</span>
                            <span>{result.quality}</span>
                          </>
                        )}
                        {result.language && result.language !== 'unknown' && (
                          <>
                            <span>|</span>
                            <span>{result.language}</span>
                          </>
                        )}
                        {result.seeders !== null && result.seeders > 0 && (
                          <>
                            <span>|</span>
                            <span>
                              {result.seeders} {result.protocol === 'ia' ? 'downloads' : t('issues.seeders')}
                            </span>
                          </>
                        )}
                        {result.publishDate && (
                          <>
                            <span>|</span>
                            <span>{formatPublishDate(result.publishDate)}</span>
                          </>
                        )}
                        {!result.publishDate && result.age > 0 && (
                          <>
                            <span>|</span>
                            <span>{result.age}d</span>
                          </>
                        )}
                      </div>
                    </div>
                    <div className="flex flex-wrap gap-1.5 mt-2">
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={alreadySaved || savingPattern === result.guid}
                        onClick={() => handleSavePattern(result)}
                        title={t('magazineDetail.saveAsPattern')}
                      >
                        {savingPattern === result.guid ? (
                          <Loader2 className="size-3.5 animate-spin" />
                        ) : alreadySaved ? (
                          <Check className="size-3.5 text-green-400" />
                        ) : (
                          <Plus className="size-3.5" />
                        )}
                        {t('magazineDetail.saveAsPattern')}
                      </Button>
                    </div>
                  </div>
                )
              })}
          </div>
        )}

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-center gap-2 pt-3 border-t border-zinc-800">
            <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
              <ChevronLeft className="size-4" />
            </Button>
            <span className="text-xs text-zinc-400">
              {t('issues.page', { page, totalPages })}
            </span>
            <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>
              <ChevronRight className="size-4" />
            </Button>
          </div>
        )}
      </div>
    </div>
  )
}


// ---------------------------------------------------------------------------
// Rules Tab
// ---------------------------------------------------------------------------

function MagazineRulesTab({ magazine, magazineId }: { magazine: Magazine; magazineId: number }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [addOpen, setAddOpen] = useState(false)
  const [ruleType, setRuleType] = useState<string>('exclude')
  const [rulePattern, setRulePattern] = useState('')

  // Inline edit state
  const [editingRuleId, setEditingRuleId] = useState<number | null>(null)
  const [editRuleType, setEditRuleType] = useState<string>('exclude')
  const [editRulePattern, setEditRulePattern] = useState('')

  async function handleAdd() {
    if (!rulePattern.trim()) return
    try {
      await addMagazineRule(magazineId, {
        ruleType,
        pattern: rulePattern.trim(),
      })
      toast.success(t('magazineDetail.ruleAdded'))
      setAddOpen(false)
      setRulePattern('')
      queryClient.invalidateQueries({ queryKey: ['magazine', magazineId] })
    } catch {
      toast.error(t('magazineDetail.ruleAddError'))
    }
  }

  async function handleSaveRuleEdit(ruleId: number) {
    if (!editRulePattern.trim()) return
    try {
      await updateMagazineRule(magazineId, ruleId, {
        ruleType: editRuleType,
        pattern: editRulePattern.trim(),
      })
      toast.success(t('magazineDetail.ruleUpdated'))
      setEditingRuleId(null)
      queryClient.invalidateQueries({ queryKey: ['magazine', magazineId] })
    } catch {
      toast.error(t('magazineDetail.ruleUpdateError'))
    }
  }

  async function handleDelete(ruleId: number) {
    try {
      await deleteMagazineRule(magazineId, ruleId)
      toast.success(t('magazineDetail.ruleDeleted'))
      queryClient.invalidateQueries({ queryKey: ['magazine', magazineId] })
    } catch {
      toast.error(t('magazineDetail.ruleDeleteError'))
    }
  }

  return (
    <div className="pt-4 space-y-4">
      <div className="flex justify-between items-center">
        <p className="text-sm text-zinc-400">
          {magazine.rules?.length ?? 0} {t('magazineDetail.tabRules').toLowerCase()}
        </p>
        <Button size="sm" onClick={() => setAddOpen(true)}>
          <Plus className="size-3.5" />
          {t('magazineDetail.addRule')}
        </Button>
      </div>

      {magazine.rules && magazine.rules.length > 0 ? (
        <Table>
          <TableHeader>
            <TableRow className="border-zinc-800 hover:bg-transparent">
              <TableHead className="text-zinc-400 w-24">{t('magazineDetail.ruleType')}</TableHead>
              <TableHead className="text-zinc-400">{t('magazineDetail.rulePattern')}</TableHead>
              <TableHead className="text-zinc-400 w-20" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {magazine.rules.map((r) => (
              <TableRow key={r.id} className="border-zinc-800">
                <TableCell>
                  {editingRuleId === r.id ? (
                    <Select value={editRuleType} onValueChange={setEditRuleType}>
                      <SelectTrigger className="bg-zinc-900 border-zinc-700 text-zinc-100 h-8 w-24">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="include">{t('magazineDetail.include')}</SelectItem>
                        <SelectItem value="exclude">{t('magazineDetail.exclude')}</SelectItem>
                      </SelectContent>
                    </Select>
                  ) : (
                    <Badge variant={r.ruleType === 'include' ? 'default' : 'destructive'} className={r.ruleType === 'include' ? 'bg-green-700' : ''}>
                      {t(`magazineDetail.${r.ruleType}`)}
                    </Badge>
                  )}
                </TableCell>
                <TableCell className="text-zinc-100 text-sm font-mono">
                  {editingRuleId === r.id ? (
                    <Input
                      value={editRulePattern}
                      onChange={(e) => setEditRulePattern(e.target.value)}
                      className="bg-zinc-900 border-zinc-700 text-zinc-100 text-sm font-mono h-8"
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') handleSaveRuleEdit(r.id)
                        if (e.key === 'Escape') setEditingRuleId(null)
                      }}
                      autoFocus
                    />
                  ) : (
                    r.pattern
                  )}
                </TableCell>
                <TableCell>
                  <div className="flex items-center gap-1">
                    {editingRuleId === r.id ? (
                      <>
                        <button type="button" onClick={() => handleSaveRuleEdit(r.id)} className="p-1 text-zinc-500 hover:text-green-400">
                          <Check className="size-4" />
                        </button>
                        <button type="button" onClick={() => setEditingRuleId(null)} className="p-1 text-zinc-500 hover:text-zinc-300">
                          <X className="size-4" />
                        </button>
                      </>
                    ) : (
                      <>
                        <button
                          type="button"
                          onClick={() => { setEditingRuleId(r.id); setEditRuleType(r.ruleType); setEditRulePattern(r.pattern) }}
                          className="p-1 text-zinc-500 hover:text-zinc-300"
                          title={t('common.edit')}
                        >
                          <Pencil className="size-4" />
                        </button>
                        <button
                          type="button"
                          onClick={() => handleDelete(r.id)}
                          className="p-1 text-zinc-500 hover:text-red-400"
                          title={t('common.delete')}
                        >
                          <X className="size-4" />
                        </button>
                      </>
                    )}
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      ) : (
        <p className="text-sm text-zinc-500 text-center py-8">{t('magazineDetail.noRules')}</p>
      )}

      {/* Add Rule Dialog */}
      <Dialog open={addOpen} onOpenChange={setAddOpen}>
        <DialogContent className="sm:max-w-md bg-zinc-950 border-zinc-800">
          <DialogHeader>
            <DialogTitle className="text-zinc-100">{t('magazineDetail.addRule')}</DialogTitle>
          </DialogHeader>
          <div className="grid gap-4 py-2">
            <div className="grid gap-1.5">
              <label className="text-sm font-medium text-zinc-300">{t('magazineDetail.ruleType')}</label>
              <Select value={ruleType} onValueChange={setRuleType}>
                <SelectTrigger className="bg-zinc-900 border-zinc-700 text-zinc-100 w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="include">{t('magazineDetail.include')}</SelectItem>
                  <SelectItem value="exclude">{t('magazineDetail.exclude')}</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-1.5">
              <label className="text-sm font-medium text-zinc-300">{t('magazineDetail.rulePattern')}</label>
              <Input
                value={rulePattern}
                onChange={(e) => setRulePattern(e.target.value)}
                placeholder={t('magazineDetail.rulePatternPlaceholder')}
                className="bg-zinc-900 border-zinc-700 text-zinc-100 font-mono"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setAddOpen(false)}>{t('common.cancel')}</Button>
            <Button onClick={handleAdd} disabled={!rulePattern.trim()}>{t('common.add')}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

    </div>
  )
}

// --- Manual Grab confirmation dialog --------------------------------

interface ManualGrabConfirmProps {
  release: SearchResult
  issues: Issue[]
  isPending: boolean
  onClose: () => void
  onConfirm: (overrides?: { targetIssueId?: number; targetDate?: string }) => void
}

function ManualGrabConfirmDialog({
  release,
  issues,
  isPending,
  onClose,
  onConfirm,
}: ManualGrabConfirmProps) {
  const { t } = useTranslation()
  const [mode, setMode] = useState<'auto' | 'existing' | 'date'>('auto')
  const [issueId, setIssueId] = useState<number | ''>('')
  const [date, setDate] = useState('')

  // Sort issues by date DESC then by number, keep only those without
  // a file (grabbing on top of an existing file overwrites — user
  // usually doesn't want that from Manual Grab).
  const sortedIssues = [...issues]
    .filter((i) => !i.file)
    .sort((a, b) => {
      const da = a.year ? a.year * 10000 + (a.month ?? 0) * 100 + (a.day ?? 0) : 0
      const db = b.year ? b.year * 10000 + (b.month ?? 0) * 100 + (b.day ?? 0) : 0
      if (da !== db) return db - da
      return (b.number ?? 0) - (a.number ?? 0)
    })

  function issueLabel(iss: Issue): string {
    const parts: string[] = []
    if (iss.number != null) parts.push(`#${iss.number}`)
    if (iss.year) {
      const ymd = [iss.year, iss.month, iss.day]
        .filter(Boolean)
        .map((n, i) => (i === 0 ? String(n) : String(n).padStart(2, '0')))
        .join('-')
      parts.push(ymd)
    }
    if (iss.title) parts.push(`— ${iss.title}`)
    return parts.join(' ') || `issue #${iss.id}`
  }

  const canConfirm =
    !isPending &&
    (mode === 'auto' ||
      (mode === 'existing' && issueId !== '') ||
      (mode === 'date' && /^\d{4}-\d{2}-\d{2}$/.test(date)))

  function handleConfirm() {
    if (mode === 'existing' && issueId !== '') {
      onConfirm({ targetIssueId: issueId })
    } else if (mode === 'date' && date) {
      onConfirm({ targetDate: date })
    } else {
      onConfirm()
    }
  }

  return (
    <Dialog open onOpenChange={(v) => { if (!v) onClose() }}>
      <DialogContent className="sm:max-w-lg bg-zinc-950 border-zinc-800">
        <DialogHeader>
          <DialogTitle className="text-zinc-100">
            {t('issues.grab')} — associer à
          </DialogTitle>
        </DialogHeader>
        <div className="text-xs text-zinc-500 -mt-1 break-words">
          {release.title}
        </div>

        <div className="space-y-3 mt-4">
          <ModeRow
            checked={mode === 'auto'}
            onSelect={() => setMode('auto')}
            title="Auto (parse le nom + IA)"
            hint="Comportement historique : le parser + l'IA d'import décident du numéro/date après le téléchargement."
          />
          <ModeRow
            checked={mode === 'existing'}
            onSelect={() => setMode('existing')}
            title="Issue existante"
            hint="Force le rattachement à une issue déjà connue (utile si le titre du torrent trompe le parser)."
          >
            <select
              value={issueId}
              onChange={(e) => setIssueId(e.target.value === '' ? '' : Number(e.target.value))}
              onClick={(e) => e.stopPropagation()}
              disabled={mode !== 'existing'}
              className="w-full mt-2 rounded border border-zinc-700 bg-zinc-900 px-2 py-1 text-sm text-zinc-100 disabled:opacity-40"
            >
              <option value="">— choisir —</option>
              {sortedIssues.map((iss) => (
                <option key={iss.id} value={iss.id}>{issueLabel(iss)}</option>
              ))}
            </select>
          </ModeRow>
          <ModeRow
            checked={mode === 'date'}
            onSelect={() => setMode('date')}
            title="Nouvelle par date"
            hint="Crée (ou retrouve) une issue à cette date exacte — bypass total du parser."
          >
            <Input
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              onClick={(e) => e.stopPropagation()}
              disabled={mode !== 'date'}
              className="mt-2 bg-zinc-900 border-zinc-700 text-zinc-100 disabled:opacity-40"
            />
          </ModeRow>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={isPending}>
            {t('common.cancel')}
          </Button>
          <Button onClick={handleConfirm} disabled={!canConfirm}>
            {isPending ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <Download className="size-4" />
            )}
            {t('issues.grab')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function ModeRow({
  checked,
  onSelect,
  title,
  hint,
  children,
}: {
  checked: boolean
  onSelect: () => void
  title: string
  hint: string
  children?: React.ReactNode
}) {
  return (
    <div
      onClick={onSelect}
      className={
        'rounded border px-3 py-2 cursor-pointer transition ' +
        (checked
          ? 'border-purple-500/60 bg-purple-500/5'
          : 'border-zinc-800 bg-zinc-900/40 hover:border-zinc-700')
      }
    >
      <div className="flex items-start gap-2">
        <input
          type="radio"
          checked={checked}
          onChange={onSelect}
          className="mt-1 accent-purple-500"
        />
        <div className="min-w-0 flex-1">
          <div className="text-sm text-zinc-100">{title}</div>
          <div className="text-xs text-zinc-500">{hint}</div>
          {checked && children}
        </div>
      </div>
    </div>
  )
}

// --- Manual Research helpers ----------------------------------------

const TAB_LABELS: Record<string, string> = {
  annasarchive: "Anna's Archive",
  internetarchive: 'Internet Archive',
  indexers: 'Indexers',
}

function TabCountBadge({ n }: { n: number | null }) {
  if (n == null) return null
  return (
    <span
      className={
        'ml-1.5 rounded px-1.5 text-[10px] leading-4 ' +
        (n > 0
          ? 'bg-emerald-500/20 text-emerald-300'
          : 'bg-zinc-800 text-zinc-500')
      }
    >
      {n}
    </span>
  )
}

/** Below-empty-state suggestion : if the active tab has no hits
 *  but another free-text tab does, show a one-click switch. */
function OtherTabsHint({
  activeTab,
  counts,
  onSwitch,
}: {
  activeTab: string
  counts: Record<string, number | null>
  onSwitch: (tab: string) => void
}) {
  const others = (['indexers', 'annasarchive', 'internetarchive'] as const)
    .filter((k) => k !== activeTab)
    .map((k) => ({ key: k as string, n: counts[k] }))
    .filter((x) => (x.n ?? 0) > 0) as Array<{ key: string; n: number }>
  if (others.length === 0) return null
  return (
    <div className="text-xs text-zinc-400">
      Résultats disponibles sur :{' '}
      {others.map((o, i) => (
        <span key={o.key}>
          {i > 0 && ' · '}
          <button
            type="button"
            onClick={() => onSwitch(o.key)}
            className="text-purple-400 hover:text-purple-300 underline"
          >
            {TAB_LABELS[o.key] ?? o.key} ({o.n})
          </button>
        </span>
      ))}
    </div>
  )
}

// ─── Tri des issues dans la table ─────────────────────────────────────

type IssueSortKey = 'date' | 'number' | 'title' | 'status'
type IssueSortDir = 'asc' | 'desc'

// Ordre logique des status pour tri : ce qui demande une action en
// premier (wanted), puis available, puis inconnu/manquant.
const STATUS_ORDER: Record<string, number> = {
  wanted: 0,
  available: 1,
  missing: 2,
  upcoming: 3,
}

function issueDateKey(i: Issue): number {
  // Composite month*100+day pour tri intra-année. On ignore l'année
  // parce que le grouping externe est déjà par année.
  const m = i.month ?? 0
  const d = i.day ?? 0
  return m * 100 + d
}

function sortIssues(
  arr: Issue[],
  key: IssueSortKey,
  dir: IssueSortDir,
): Issue[] {
  const mul = dir === 'asc' ? 1 : -1
  const out = [...arr]
  out.sort((a, b) => {
    // Handle key
    let cmp = 0
    if (key === 'date') {
      const av = issueDateKey(a)
      const bv = issueDateKey(b)
      // Issues sans date à la fin, quel que soit le sens du tri.
      if (av === 0 && bv !== 0) return 1
      if (av !== 0 && bv === 0) return -1
      cmp = av - bv
    } else if (key === 'number') {
      const av = a.number ?? Number.NEGATIVE_INFINITY
      const bv = b.number ?? Number.NEGATIVE_INFINITY
      cmp = av - bv
    } else if (key === 'title') {
      const av = (a.title ?? '').trim()
      const bv = (b.title ?? '').trim()
      if (!av && bv) return 1
      if (av && !bv) return -1
      cmp = av.localeCompare(bv)
    } else if (key === 'status') {
      const av = STATUS_ORDER[a.status ?? ''] ?? 99
      const bv = STATUS_ORDER[b.status ?? ''] ?? 99
      cmp = av - bv
    }
    if (cmp !== 0) return cmp * mul
    // Tie-breaker stable : par numéro puis id (garantit ordre reproductible)
    const na = a.number ?? 0
    const nb = b.number ?? 0
    if (na !== nb) return (na - nb) * mul
    return a.id - b.id
  })
  return out
}

function SortableHead({
  label,
  sortKey,
  currentKey,
  currentDir,
  onSort,
}: {
  label: string
  sortKey: IssueSortKey
  currentKey: IssueSortKey
  currentDir: IssueSortDir
  onSort: (k: IssueSortKey) => void
}) {
  const active = currentKey === sortKey
  const Icon = active ? (currentDir === 'asc' ? ArrowUp : ArrowDown) : ArrowDownUp
  return (
    <th className="h-12 px-2 text-left align-middle text-zinc-400 [&:has([role=checkbox])]:pr-0 [&>[role=checkbox]]:translate-y-[2px]">
      <button
        type="button"
        onClick={() => onSort(sortKey)}
        className={`inline-flex items-center gap-1 hover:text-zinc-200 transition-colors ${
          active ? 'text-purple-300' : ''
        }`}
      >
        {label}
        <Icon className={`size-3 ${active ? 'opacity-100' : 'opacity-40'}`} />
      </button>
    </th>
  )
}
