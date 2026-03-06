import { useState, useMemo, useCallback, useEffect, useRef } from 'react'
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
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Upload,
} from 'lucide-react'
import { toast } from 'sonner'

import {
  getMagazine,
  getMagazineCoverUrl,
  updateMagazine,
  uploadMagazineCover,
  deleteMagazine,
  refreshMetadata,
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
  type SearchResult,
} from '@/api/search'
import { getProfiles } from '@/api/quality'
import { getRootFolders } from '@/api/system'
import { IssueRow } from '@/components/IssueRow'
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
  const [editQualityProfileId, setEditQualityProfileId] = useState('')
  const [editRootFolderPath, setEditRootFolderPath] = useState('')
  const [editFrequency, setEditFrequency] = useState('monthly')
  const [editMonitoringStartDate, setEditMonitoringStartDate] = useState('')
  const [editExcludedDays, setEditExcludedDays] = useState<number[]>([])
  const [editUseLatestCover, setEditUseLatestCover] = useState(false)
  const [editCoverIssueId, setEditCoverIssueId] = useState<number | null>(null)
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
  const [editIssueYear, setEditIssueYear] = useState('')
  const [editIssueMonth, setEditIssueMonth] = useState('')
  const [editIssueDay, setEditIssueDay] = useState('')
  const [editIssueSpecial, setEditIssueSpecial] = useState(false)
  const [editIssueQuality, setEditIssueQuality] = useState('')
  const [editIssueFormat, setEditIssueFormat] = useState('')
  const [editIssueReleaseGroup, setEditIssueReleaseGroup] = useState('')
  const [editIssueLanguage, setEditIssueLanguage] = useState('')

  // Collapse upcoming issues per year group
  const [expandedUpcoming, setExpandedUpcoming] = useState<Set<string>>(new Set())

  // Refreshing state
  const [refreshing, setRefreshing] = useState(false)
  const [refreshingIssueId, setRefreshingIssueId] = useState<number | null>(null)
  const [importingIssueId, setImportingIssueId] = useState<number | null>(null)

  // Manual Research modal state
  const [manualSearchOpen, setManualSearchOpen] = useState(false)
  const [manualSearchQuery, setManualSearchQuery] = useState('')
  const [manualSearchTab, setManualSearchTab] = useState('annasarchive')
  const [manualSearchResults, setManualSearchResults] = useState<SearchResult[]>([])
  const [manualSearching, setManualSearching] = useState(false)
  const [manualSearchPage, setManualSearchPage] = useState(1)
  const [manualSearchSourceFilter, setManualSearchSourceFilter] = useState('')
  const [manualSearchDateSort, setManualSearchDateSort] = useState<'' | 'asc' | 'desc'>('')
  const [searchPage, setSearchPage] = useState(1)
  const [searchSourceFilter, setSearchSourceFilter] = useState('')
  const [searchDateSort, setSearchDateSort] = useState<'' | 'asc' | 'desc'>('')

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
    onError: () => toast.error(t('issues.issueUpdateError')),
  })

  const handleEditIssue = (issue: Issue) => {
    setEditingIssue(issue)
    setEditIssueNumber(issue.number != null ? String(issue.number) : '')
    setEditIssueVolume(issue.volume != null ? String(issue.volume) : '')
    setEditIssueTitle(issue.title ?? '')
    setEditIssueYear(issue.year != null ? String(issue.year) : '')
    setEditIssueMonth(issue.month != null ? String(issue.month) : '')
    setEditIssueDay(issue.day != null ? String(issue.day) : '')
    setEditIssueSpecial(issue.isSpecial)
    setEditIssueQuality(issue.file?.quality ?? '')
    setEditIssueFormat(issue.file?.format ?? '')
    setEditIssueReleaseGroup(issue.file?.releaseGroup ?? '')
    setEditIssueLanguage(issue.file?.language ?? '')
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
    if (yr !== editingIssue.year) data.year = yr
    if (mo !== editingIssue.month) data.month = mo
    if (dy !== editingIssue.day) data.day = dy
    if (editIssueSpecial !== editingIssue.isSpecial) data.isSpecial = editIssueSpecial

    if (editingIssue.file) {
      if (editIssueQuality !== editingIssue.file.quality) data.quality = editIssueQuality || null
      if (editIssueFormat !== editingIssue.file.format) data.format = editIssueFormat || null
      if ((editIssueReleaseGroup || null) !== editingIssue.file.releaseGroup) data.releaseGroup = editIssueReleaseGroup || null
      if ((editIssueLanguage || null) !== editingIssue.file.language) data.language = editIssueLanguage || null
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
    setEditUseLatestCover(magazine.useLatestIssueCover)
    setEditCoverIssueId(null)
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
      useLatestIssueCover: editUseLatestCover,
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

  // Refresh
  async function handleRefresh() {
    setRefreshing(true)
    try {
      await refreshMetadata(magazineId)
      invalidateMagazine()
      invalidateIssues()
      toast.success(t('magazineDetail.refreshed'))
    } catch {
      toast.error(t('magazineDetail.refreshError'))
    } finally {
      setRefreshing(false)
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
    if (!manualSearchQuery.trim()) return
    setManualSearching(true)
    setManualSearchResults([])
    setManualSearchPage(1)
    setManualSearchSourceFilter('')
    setManualSearchDateSort('')
    try {
      let results: SearchResult[] = []
      if (activeTab === 'annasarchive') {
        results = await searchAnnasArchive(manualSearchQuery, magazineId)
      } else if (activeTab === 'internetarchive') {
        results = await searchInternetArchive(manualSearchQuery, magazineId)
      } else if (activeTab === 'indexers') {
        results = await searchIndexers(manualSearchQuery, magazineId)
      }
      setManualSearchResults(results)
    } catch {
      toast.error(t('issues.searchError'))
    } finally {
      setManualSearching(false)
    }
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

  async function handleGrab(result: SearchResult, fromManualSearch = false) {
    if (!fromManualSearch && !searchingIssueId && !magazine) return
    const targetIssueId = searchingIssueId ?? 0
    setGrabbing(result.guid)
    try {
      if (result.protocol === 'aa') {
        // Anna's Archive direct download - guid = md5 hash
        await downloadFromAA(result.guid, result.title, targetIssueId || undefined, magazineId)
      } else if (result.protocol === 'ia') {
        // Internet Archive direct download
        await downloadFromIA(
          result.guid,
          `${result.guid}.pdf`,
          result.title,
          targetIssueId || undefined,
          magazineId,
        )
      } else {
        await grabRelease(
          targetIssueId,
          result.downloadUrl,
          result.title,
          result.protocol,
          result.guid,
          magazineId,
        )
      }
      toast.success(t('issues.grabbed'))
      if (fromManualSearch) {
        setManualSearchOpen(false)
      } else {
        setSearchDialogOpen(false)
      }
      invalidateIssues()
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
                  <Badge variant={magazine.monitored ? 'default' : 'secondary'} className={magazine.monitored ? 'bg-green-600 hover:bg-green-600' : ''}>
                    {magazine.monitored ? t('library.monitored') : t('library.unmonitored')}
                  </Badge>
                </div>
                <div className="flex items-center gap-2 mt-1 text-sm text-zinc-400">
                  {magazine.publisher && (
                    <span>{magazine.publisher}</span>
                  )}
                  {magazine.frequency && (
                    <>
                      <span className="text-zinc-700">|</span>
                      <span className="capitalize">{magazine.frequency}</span>
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
                >
                  <RefreshCw className={`size-3.5 ${refreshing ? 'animate-spin' : ''}`} />
                  {t('magazineDetail.refresh')}
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
                onClick={handleOpenManualSearch}
              >
                <Search className="size-3.5" />
                {t('magazineDetail.manualResearch')}
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
                    <TableHead className="text-zinc-400">{t('issues.number')}</TableHead>
                    <TableHead className="text-zinc-400">{t('issues.date')}</TableHead>
                    <TableHead className="text-zinc-400">{t('issues.issueTitle')}</TableHead>
                    <TableHead className="text-zinc-400">{t('issues.status')}</TableHead>
                    <TableHead className="text-zinc-400">{t('issues.fileInfo')}</TableHead>
                    <TableHead className="text-zinc-400">{t('issues.actions')}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {(() => {
                    const regular = yearIssues.filter((i) => !i.isForecast || i.status === 'wanted')
                    const upcoming = yearIssues.filter((i) => i.isForecast && i.status !== 'wanted')
                    const isExpanded = expandedUpcoming.has(year)

                    const renderRow = (issue: typeof yearIssues[number]) => (
                      <IssueRow
                        key={issue.id}
                        issue={issue}
                        selected={selectedIds.has(issue.id)}
                        queueItem={queueByIssueId.get(issue.id)}
                        deduced={deductions.get(issue.id)}
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
                        onRefresh={handleRefreshIssue}
                        onImport={handleImportIssue}
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
                              <TableCell colSpan={7} className="py-2">
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
            }}
            className="flex-1 overflow-hidden flex flex-col"
          >
            <TabsList className="w-full">
              <TabsTrigger value="annasarchive">
                {t('magazineDetail.tabAnnasArchive')}
              </TabsTrigger>
              <TabsTrigger value="internetarchive">
                {t('magazineDetail.tabInternetArchive')}
              </TabsTrigger>
              <TabsTrigger value="indexers">
                {t('magazineDetail.tabIndexers')}
              </TabsTrigger>
            </TabsList>

            {/* Search bar (shared across tabs) */}
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

            {/* Results area (same for all tabs) */}
            {(() => {
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
                      <p className="text-zinc-500 text-center py-8">
                        {t('magazineDetail.manualSearchHint')}
                      </p>
                    ) : filtered.length === 0 ? (
                      <p className="text-zinc-500 text-center py-8">
                        {t('common.noResults')}
                      </p>
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
                              </div>
                            </div>
                            <Button
                              variant="outline"
                              size="sm"
                              disabled={result.isBlocklisted || grabbing === result.guid}
                              onClick={() => handleGrab(result, true)}
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
          </Tabs>
        </DialogContent>
      </Dialog>

      {/* Edit Modal */}
      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent className="sm:max-w-lg bg-zinc-950 border-zinc-800">
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
                  {['daily', 'weekly', 'biweekly'].includes(editFrequency) && (
                    <div className="grid gap-1.5 mt-2">
                      <label className="text-sm font-medium text-zinc-300">
                        {t('addMagazine.excludedDays')}
                      </label>
                      <div className="flex gap-1">
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
                            onClick={() =>
                              setEditExcludedDays((prev) =>
                                prev.includes(day) ? prev.filter((d) => d !== day) : [...prev, day]
                              )
                            }
                            className={`px-2 py-1 text-xs rounded border ${
                              editExcludedDays.includes(day)
                                ? 'bg-red-900/50 border-red-700 text-red-300'
                                : 'bg-zinc-900 border-zinc-700 text-zinc-400'
                            }`}
                          >
                            {t(key)}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                <div className="grid gap-1.5">
                  <label className="text-sm font-medium text-zinc-300">
                    {t('addMagazine.rootFolder')}
                  </label>
                  <Select value={editRootFolderPath} onValueChange={setEditRootFolderPath}>
                    <SelectTrigger className="bg-zinc-900 border-zinc-700 text-zinc-100 w-full">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {rootFolders.map((folder) => (
                        <SelectItem key={folder.id} value={folder.path}>
                          {folder.path}
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

      {/* Edit Issue Dialog */}
      <Dialog open={editIssueOpen} onOpenChange={(open) => {
        setEditIssueOpen(open)
        if (!open) setEditingIssue(null)
      }}>
        <DialogContent className="sm:max-w-lg bg-zinc-950 border-zinc-800">
          <DialogHeader>
            <DialogTitle className="text-zinc-100">
              {t('issues.editIssueTitle')}
            </DialogTitle>
          </DialogHeader>
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
                {editingIssue.file.originalFilename && (
                  <div>
                    <label className="text-xs text-zinc-400">{t('issues.sourceFilename')}</label>
                    <p className="text-sm text-zinc-300 bg-zinc-900 border border-zinc-700 rounded-md px-3 py-2 break-all">
                      {editingIssue.file.originalFilename}
                    </p>
                  </div>
                )}
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
    </div>
  )
}
