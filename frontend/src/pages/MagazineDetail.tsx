import { useState, useMemo, useCallback, useEffect } from 'react'
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
} from 'lucide-react'
import { toast } from 'sonner'

import {
  getMagazine,
  getMagazineCoverUrl,
  updateMagazine,
  deleteMagazine,
  refreshMetadata,
  type Magazine,
} from '@/api/magazines'
import {
  getIssues,
  updateIssueMonitored,
  batchMonitor,
  deleteIssueFile,
  type Issue,
} from '@/api/issues'
import {
  searchIssue,
  searchMagazine,
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

type StatusFilter = 'all' | 'available' | 'wanted' | 'missing'

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(1024))
  return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${units[i]}`
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

  // Delete modal state
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [deleteFiles, setDeleteFiles] = useState(false)

  // Refreshing state
  const [refreshing, setRefreshing] = useState(false)

  // Manual Research modal state
  const [manualSearchOpen, setManualSearchOpen] = useState(false)
  const [manualSearchQuery, setManualSearchQuery] = useState('')
  const [manualSearchTab, setManualSearchTab] = useState('annasarchive')
  const [manualSearchResults, setManualSearchResults] = useState<SearchResult[]>([])
  const [manualSearching, setManualSearching] = useState(false)

  const { data: magazine, isLoading: magazineLoading } = useQuery({
    queryKey: ['magazine', magazineId],
    queryFn: () => getMagazine(magazineId),
    enabled: !isNaN(magazineId),
  })

  const { data: issues = [], isLoading: issuesLoading } = useQuery({
    queryKey: ['issues', magazineId, statusFilter === 'all' ? undefined : statusFilter],
    queryFn: () => getIssues(magazineId, statusFilter === 'all' ? undefined : statusFilter),
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
    // Also match by magazine ID for items without issue ID
    // (from Manual Research where issue_id is unknown)
    for (const item of queue) {
      if (!item.issueId && item.magazineId === magazineId) {
        // Show as a magazine-level queue item (not tied to specific issue)
        map.set(-item.id, item) // negative key = not issue-matched
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
    mutationFn: (issueId: number) => deleteIssueFile(issueId),
    onSuccess: () => {
      invalidateIssues()
      toast.success(t('issues.fileDeleted'))
    },
    onError: () => toast.error(t('issues.deleteFileError')),
  })

  const updateMagazineMutation = useMutation({
    mutationFn: (data: Partial<Magazine>) => updateMagazine(magazineId, data),
    onSuccess: () => {
      invalidateMagazine()
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

  // Group issues by year
  const groupedIssues = useMemo(() => {
    const groups: Record<string, Issue[]> = {}
    for (const issue of issues) {
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
  }, [issues, t])

  // Status counts
  const statusCounts = useMemo(() => {
    const counts = { all: issues.length, available: 0, wanted: 0, missing: 0 }
    for (const issue of issues) {
      if (issue.status === 'available') counts.available++
      else if (issue.status === 'wanted') counts.wanted++
      else if (issue.status === 'missing') counts.missing++
    }
    return counts
  }, [issues])

  const completionPercent = issues.length > 0
    ? Math.round((statusCounts.available / issues.length) * 100)
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
    setEditOpen(true)
  }

  function handleSaveEdit() {
    const folder = rootFolders.find((f) => f.path === editRootFolderPath)
    updateMagazineMutation.mutate({
      title: editTitle,
      monitored: editMonitored,
      qualityProfileId: Number(editQualityProfileId),
      rootFolderId: folder?.id,
    })
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
    try {
      let results: SearchResult[] = []
      if (activeTab === 'annasarchive') {
        results = await searchAnnasArchive(manualSearchQuery, magazineId)
      } else if (activeTab === 'internetarchive') {
        results = await searchInternetArchive(manualSearchQuery, magazineId)
      } else if (activeTab === 'indexers') {
        results = await searchMagazine(magazineId)
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
        await downloadFromAA(result.guid, targetIssueId || undefined, magazineId)
      } else if (result.protocol === 'ia') {
        // Internet Archive direct download
        await downloadFromIA(
          result.guid,
          `${result.guid}.pdf`,
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
      <div className="p-8 max-w-6xl">
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
    <div className="p-8 max-w-6xl">
      {/* Cover + Metadata Header */}
      {magazine && (
        <div className="flex gap-6 mb-8">
          {/* Cover */}
          <div className="w-32 shrink-0">
            <div className="aspect-[3/4] rounded-lg bg-zinc-900 overflow-hidden">
              {magazine.coverPath ? (
                <img
                  src={getMagazineCoverUrl(magazine.id)}
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
                <h1 className="text-2xl font-bold text-zinc-100">{magazine.title}</h1>
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

              {/* Action buttons */}
              <div className="flex items-center gap-2 shrink-0">
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

            {/* Statistics overview */}
            <div className="flex items-center gap-4 mt-4">
              <Badge variant={magazine.monitored ? 'default' : 'outline'} className={magazine.monitored ? 'bg-[#E85D04]' : ''}>
                {magazine.monitored ? t('library.monitored') : t('library.unmonitored')}
              </Badge>
              <div className="flex items-center gap-3 text-sm">
                <span className="text-zinc-400">
                  {t('magazineDetail.totalIssues')}: <span className="text-zinc-100">{issues.length}</span>
                </span>
                <span className="text-zinc-400">
                  {t('status.available')}: <span className="text-green-400">{statusCounts.available}</span>
                </span>
                <span className="text-zinc-400">
                  {t('status.missing')}: <span className="text-red-400">{statusCounts.missing}</span>
                </span>
                <span className="text-zinc-400">
                  {t('magazineDetail.completion')}: <span className="text-[#E85D04]">{completionPercent}%</span>
                </span>
              </div>
            </div>

            {/* Progress bar */}
            <div className="mt-3 h-1.5 rounded-full bg-zinc-800 overflow-hidden max-w-md">
              <div
                className="h-full rounded-full bg-[#E85D04] transition-all"
                style={{ width: `${completionPercent}%` }}
              />
            </div>
          </div>
        </div>
      )}

      {/* Status Filters */}
      <div className="flex items-center gap-2 mb-6">
        {(['all', 'available', 'wanted', 'missing'] as StatusFilter[]).map((filter) => (
          <Button
            key={filter}
            variant={statusFilter === filter ? 'default' : 'outline'}
            size="sm"
            onClick={() => setStatusFilter(filter)}
            className={statusFilter === filter ? 'bg-[#E85D04] hover:bg-[#E85D04]/90' : ''}
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

      {/* Active downloads for this magazine (not matched to a specific issue) */}
      {queue.filter((q) => q.magazineId === magazineId && !q.issueId).length > 0 && (
        <div className="mb-4 space-y-2">
          {queue
            .filter((q) => q.magazineId === magazineId && !q.issueId)
            .map((item) => {
              const progress = item.size > 0
                ? Math.round(((item.size - item.sizeLeft) / item.size) * 100)
                : 0
              return (
                <div
                  key={item.id}
                  className="flex items-center gap-3 rounded-md border border-[#E85D04]/30 bg-[#E85D04]/5 px-4 py-2"
                >
                  <Loader2 className="size-4 animate-spin text-[#E85D04] shrink-0" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-zinc-200 truncate">{item.title}</p>
                    <div className="flex items-center gap-2 mt-1">
                      <div className="flex-1 h-1 rounded-full bg-zinc-800 overflow-hidden max-w-[200px]">
                        <div
                          className="h-full rounded-full bg-[#E85D04] transition-all"
                          style={{ width: `${progress}%` }}
                        />
                      </div>
                      <span className="text-xs text-zinc-500">{progress}%</span>
                      <span className="text-xs text-zinc-500">{item.downloadClient}</span>
                      <Badge variant="outline" className="text-xs border-[#E85D04]/50 text-[#E85D04]">
                        {item.status}
                      </Badge>
                    </div>
                  </div>
                </div>
              )
            })}
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
                        className="size-4 rounded border-zinc-600 bg-zinc-900 accent-[#E85D04]"
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
                  {yearIssues.map((issue) => (
                    <IssueRow
                      key={issue.id}
                      issue={issue}
                      selected={selectedIds.has(issue.id)}
                      queueItem={queueByIssueId.get(issue.id)}
                      onSelect={handleSelect}
                      onToggleMonitor={(issueId, monitored) =>
                        monitorMutation.mutate({ issueId, monitored })
                      }
                      onDeleteFile={(issueId) => deleteFileMutation.mutate(issueId)}
                      onSearch={handleSearch}
                    />
                  ))}
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

          <div className="flex-1 overflow-y-auto">
            {searching ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="size-6 animate-spin text-zinc-400" />
                <span className="ml-2 text-zinc-400">{t('issues.searching')}</span>
              </div>
            ) : searchResults.length === 0 ? (
              <p className="text-zinc-500 text-center py-8">
                {t('common.noResults')}
              </p>
            ) : (
              <div className="divide-y divide-zinc-800">
                {searchResults.map((result) => (
                  <div
                    key={result.guid}
                    className={`flex items-center justify-between py-3 px-2 hover:bg-zinc-900/50 rounded ${
                      result.isBlocklisted ? 'opacity-40' : ''
                    }`}
                  >
                    <div className="flex-1 min-w-0 mr-4">
                      <p className="text-sm text-zinc-100 truncate">{result.title}</p>
                      <div className="flex items-center gap-2 mt-1 text-xs text-zinc-500">
                        <span>{result.indexer}</span>
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
                        {result.age > 0 && (
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
            <div className="flex-1 overflow-y-auto mt-3">
              {manualSearching ? (
                <div className="flex items-center justify-center py-12">
                  <Loader2 className="size-6 animate-spin text-zinc-400" />
                  <span className="ml-2 text-zinc-400">{t('issues.searching')}</span>
                </div>
              ) : manualSearchResults.length === 0 ? (
                <p className="text-zinc-500 text-center py-8">
                  {t('magazineDetail.manualSearchHint')}
                </p>
              ) : (
                <div className="divide-y divide-zinc-800">
                  {manualSearchResults.map((result) => (
                    <div
                      key={result.guid}
                      className={`flex items-center justify-between py-3 px-2 hover:bg-zinc-900/50 rounded ${
                        result.isBlocklisted ? 'opacity-40' : ''
                      }`}
                    >
                      <div className="flex-1 min-w-0 mr-4">
                        <p className="text-sm text-zinc-100 truncate">{result.title}</p>
                        <div className="flex items-center gap-2 mt-1 text-xs text-zinc-500">
                          <span>{result.indexer}</span>
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
          </div>

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
              className="size-4 rounded border-zinc-600 bg-zinc-900 accent-[#E85D04]"
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
