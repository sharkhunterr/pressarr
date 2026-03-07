import { useState, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Eye,
  EyeOff,
  Pencil,
  Trash2,
  Search,
  Loader2,
  Plus,
  X,
  Check,
  ArrowDownUp,
  ChevronLeft,
  ChevronRight,
  Download,
} from 'lucide-react'
import { toast } from 'sonner'

import {
  getPack,
  updatePack,
  deletePack,
  addPackPattern,
  deletePackPattern,
  addPackRule,
  deletePackRule,
  grabPackRelease,
  type Pack,
} from '@/api/packs'
import {
  searchIndexers,
  searchInternetArchive,
  searchAnnasArchive,
  type SearchResult,
} from '@/api/search'
import { HistoryModal } from '@/components/HistoryModal'
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

const RESULTS_PER_PAGE = 50

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

export default function PackDetail() {
  const { id } = useParams<{ id: string }>()
  const packId = Number(id)
  const { t } = useTranslation()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  // Edit modal
  const [editOpen, setEditOpen] = useState(false)
  const [editName, setEditName] = useState('')
  const [editDescription, setEditDescription] = useState('')
  const [editSearchQuery, setEditSearchQuery] = useState('')
  const [editRecurrence, setEditRecurrence] = useState('monthly')

  // Delete modal
  const [deleteOpen, setDeleteOpen] = useState(false)

  // History modal
  const [historyOpen, setHistoryOpen] = useState(false)

  const { data: pack, isLoading } = useQuery({
    queryKey: ['pack', packId],
    queryFn: () => getPack(packId),
  })

  const toggleMonitored = useCallback(async () => {
    if (!pack) return
    try {
      await updatePack(packId, { monitored: !pack.monitored })
      queryClient.invalidateQueries({ queryKey: ['pack', packId] })
    } catch { /* ignore */ }
  }, [pack, packId, queryClient])

  function openEdit() {
    if (!pack) return
    setEditName(pack.name)
    setEditDescription(pack.description || '')
    setEditSearchQuery(pack.searchQuery)
    setEditRecurrence(pack.recurrence)
    setEditOpen(true)
  }

  async function handleEdit() {
    try {
      await updatePack(packId, {
        name: editName.trim(),
        description: editDescription.trim() || undefined,
        searchQuery: editSearchQuery.trim(),
        recurrence: editRecurrence,
      })
      toast.success(t('packs.updated'))
      setEditOpen(false)
      queryClient.invalidateQueries({ queryKey: ['pack', packId] })
    } catch {
      toast.error(t('packs.updateError'))
    }
  }

  async function handleDelete() {
    try {
      await deletePack(packId)
      toast.success(t('packs.deleted'))
      navigate('/packs')
    } catch {
      toast.error(t('packs.deleteError'))
    }
  }

  async function handleToggleAuto(field: 'autoSearch' | 'autoGrab' | 'autoImport', value: boolean) {
    try {
      await updatePack(packId, { [field]: value })
      queryClient.invalidateQueries({ queryKey: ['pack', packId] })
    } catch {
      toast.error(t('packs.updateError'))
    }
  }

  if (isLoading || !pack) {
    return (
      <div className="p-4 lg:p-8">
        <Skeleton className="h-8 w-64 bg-zinc-800 mb-4" />
        <Skeleton className="h-64 bg-zinc-800 rounded-lg" />
      </div>
    )
  }

  return (
    <div className="p-4 lg:p-8">
      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-zinc-100">{pack.name}</h1>
          {pack.description && (
            <p className="text-sm text-zinc-400 mt-1">{pack.description}</p>
          )}
          <div className="flex items-center gap-2 mt-2">
            <Badge
              variant={pack.monitored ? 'default' : 'outline'}
              className={pack.monitored ? 'bg-[#7C3AED]' : ''}
            >
              {pack.monitored ? t('packs.monitored') : t('packs.unmonitored')}
            </Badge>
            {pack.recurrence !== 'none' && (
              <Badge variant="secondary" className="capitalize">
                {t(`packs.${pack.recurrence}`)}
              </Badge>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Button variant="outline" size="icon" onClick={toggleMonitored} title={pack.monitored ? t('packs.unmonitored') : t('packs.monitored')}>
            {pack.monitored ? <Eye className="size-4" /> : <EyeOff className="size-4" />}
          </Button>
          <Button variant="outline" size="icon" onClick={openEdit}>
            <Pencil className="size-4" />
          </Button>
          <Button variant="outline" size="icon" onClick={() => setDeleteOpen(true)}>
            <Trash2 className="size-4 text-red-400" />
          </Button>
        </div>
      </div>

      {/* Tabs */}
      <Tabs defaultValue="overview">
        <TabsList className="bg-zinc-900 border-zinc-800">
          <TabsTrigger value="overview">{t('packs.tabOverview')}</TabsTrigger>
          <TabsTrigger value="search">{t('packs.tabSearch')}</TabsTrigger>
          <TabsTrigger value="patterns">{t('packs.tabPatterns')}</TabsTrigger>
          <TabsTrigger value="rules">{t('packs.tabRules')}</TabsTrigger>
          <TabsTrigger value="history">{t('packs.tabHistory')}</TabsTrigger>
        </TabsList>

        <TabsContent value="overview">
          <OverviewTab pack={pack} onToggleAuto={handleToggleAuto} />
        </TabsContent>

        <TabsContent value="search">
          <SearchTab pack={pack} packId={packId} />
        </TabsContent>

        <TabsContent value="patterns">
          <PatternsTab pack={pack} packId={packId} />
        </TabsContent>

        <TabsContent value="rules">
          <RulesTab pack={pack} packId={packId} />
        </TabsContent>

        <TabsContent value="history">
          <div className="pt-4">
            <Button variant="outline" onClick={() => setHistoryOpen(true)}>
              {t('packs.tabHistory')}
            </Button>
          </div>
        </TabsContent>
      </Tabs>

      {/* Edit Dialog */}
      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent className="sm:max-w-lg bg-zinc-950 border-zinc-800">
          <DialogHeader>
            <DialogTitle className="text-zinc-100">{t('common.edit')}</DialogTitle>
          </DialogHeader>
          <div className="grid gap-4 py-2">
            <div className="grid gap-1.5">
              <label className="text-sm font-medium text-zinc-300">{t('packs.name')}</label>
              <Input value={editName} onChange={(e) => setEditName(e.target.value)} className="bg-zinc-900 border-zinc-700 text-zinc-100" />
            </div>
            <div className="grid gap-1.5">
              <label className="text-sm font-medium text-zinc-300">{t('packs.description')}</label>
              <Input value={editDescription} onChange={(e) => setEditDescription(e.target.value)} className="bg-zinc-900 border-zinc-700 text-zinc-100" />
            </div>
            <div className="grid gap-1.5">
              <label className="text-sm font-medium text-zinc-300">{t('packs.searchQuery')}</label>
              <Input value={editSearchQuery} onChange={(e) => setEditSearchQuery(e.target.value)} className="bg-zinc-900 border-zinc-700 text-zinc-100" />
            </div>
            <div className="grid gap-1.5">
              <label className="text-sm font-medium text-zinc-300">{t('packs.recurrence')}</label>
              <Select value={editRecurrence} onValueChange={setEditRecurrence}>
                <SelectTrigger className="bg-zinc-900 border-zinc-700 text-zinc-100 w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">{t('packs.none')}</SelectItem>
                  <SelectItem value="daily">{t('packs.daily')}</SelectItem>
                  <SelectItem value="weekly">{t('packs.weekly')}</SelectItem>
                  <SelectItem value="monthly">{t('packs.monthly')}</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditOpen(false)}>{t('common.cancel')}</Button>
            <Button onClick={handleEdit}>{t('common.save')}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Dialog */}
      <Dialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <DialogContent className="sm:max-w-md bg-zinc-950 border-zinc-800">
          <DialogHeader>
            <DialogTitle className="text-zinc-100">{t('packs.deleteTitle')}</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-zinc-400">
            {t('packs.deleteConfirm', { name: pack.name })}
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteOpen(false)}>{t('common.cancel')}</Button>
            <Button variant="destructive" onClick={handleDelete}>{t('common.delete')}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* History Modal */}
      {historyOpen && (
        <HistoryModal
          open={historyOpen}
          onOpenChange={setHistoryOpen}
          packId={packId}
        />
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Overview Tab
// ---------------------------------------------------------------------------

function OverviewTab({ pack, onToggleAuto }: { pack: Pack; onToggleAuto: (field: 'autoSearch' | 'autoGrab' | 'autoImport', value: boolean) => void }) {
  const { t } = useTranslation()

  return (
    <div className="pt-4 space-y-6">
      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-4">
          <p className="text-xs text-zinc-500">{t('packs.tabPatterns')}</p>
          <p className="text-2xl font-bold text-zinc-100">{pack.statistics?.patternCount ?? 0}</p>
        </div>
        <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-4">
          <p className="text-xs text-zinc-500">{t('packs.tabRules')}</p>
          <p className="text-2xl font-bold text-zinc-100">{pack.statistics?.ruleCount ?? 0}</p>
        </div>
        <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-4">
          <p className="text-xs text-zinc-500">{t('packs.grabs', { count: 0 }).replace('0 ', '')}</p>
          <p className="text-2xl font-bold text-zinc-100">{pack.statistics?.totalGrabs ?? 0}</p>
        </div>
        <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-4">
          <p className="text-xs text-zinc-500">{t('packs.searchQuery')}</p>
          <p className="text-sm font-medium text-zinc-300 truncate">{pack.searchQuery}</p>
        </div>
      </div>

      {/* Auto toggles */}
      <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-4 space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-zinc-100">{t('packs.autoSearch')}</p>
          </div>
          <Switch checked={pack.autoSearch} onCheckedChange={(v) => onToggleAuto('autoSearch', v === true)} />
        </div>
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-zinc-100">{t('packs.autoGrab')}</p>
          </div>
          <Switch checked={pack.autoGrab} onCheckedChange={(v) => onToggleAuto('autoGrab', v === true)} />
        </div>
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-zinc-100">{t('packs.autoImport')}</p>
            <p className="text-xs text-zinc-500">{t('packs.autoImportDesc')}</p>
          </div>
          <Switch checked={pack.autoImport} onCheckedChange={(v) => onToggleAuto('autoImport', v === true)} />
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Search Tab
// ---------------------------------------------------------------------------

function SearchTab({ pack, packId }: { pack: Pack; packId: number }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [query, setQuery] = useState(pack.searchQuery || '')
  const [results, setResults] = useState<SearchResult[]>([])
  const [searching, setSearching] = useState(false)
  const [grabbing, setGrabbing] = useState<string | null>(null)
  const [savingPattern, setSavingPattern] = useState<string | null>(null)
  const [searchSource, setSearchSource] = useState('indexers')
  const [sourceFilter, setSourceFilter] = useState('')
  const [dateSort, setDateSort] = useState<'' | 'asc' | 'desc'>('')
  const [page, setPage] = useState(1)

  async function handleSearch() {
    if (!query.trim()) return
    setSearching(true)
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
      setSearching(false)
    }
  }

  async function handleGrab(result: SearchResult) {
    setGrabbing(result.guid)
    try {
      await grabPackRelease(
        packId,
        result.downloadUrl,
        result.title,
        result.protocol,
        result.guid,
        result.indexer,
      )
      toast.success(t('packs.grabbed'))
      queryClient.invalidateQueries({ queryKey: ['pack', packId] })
    } catch {
      toast.error(t('packs.grabError'))
    } finally {
      setGrabbing(null)
    }
  }

  async function handleSavePattern(result: SearchResult) {
    setSavingPattern(result.guid)
    try {
      await addPackPattern(packId, {
        pattern: result.title,
        source: result.indexer || undefined,
      })
      toast.success(t('packs.patternSaved'))
      queryClient.invalidateQueries({ queryKey: ['pack', packId] })
    } catch {
      toast.error(t('packs.patternAddError'))
    } finally {
      setSavingPattern(null)
    }
  }

  function isAlreadyPattern(result: SearchResult) {
    return pack.patterns?.some((p) => p.pattern === result.title) ?? false
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
    <div className="pt-4 space-y-4">
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
        <Button onClick={handleSearch} disabled={searching || !query.trim()}>
          {searching ? <Loader2 className="size-4 animate-spin" /> : <Search className="size-4" />}
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
      {searching ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="size-6 animate-spin text-zinc-400" />
          <span className="ml-2 text-zinc-400">{t('issues.searching')}</span>
        </div>
      ) : filtered.length === 0 && results.length === 0 ? (
        <p className="text-sm text-zinc-500">{t('packs.searchHint')}</p>
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
                      title={t('packs.saveAsPattern')}
                    >
                      {savingPattern === result.guid ? (
                        <Loader2 className="size-3.5 animate-spin" />
                      ) : alreadySaved ? (
                        <Check className="size-3.5 text-green-400" />
                      ) : (
                        <Plus className="size-3.5" />
                      )}
                      {t('packs.saveAsPattern')}
                    </Button>
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
  )
}

// ---------------------------------------------------------------------------
// Patterns Tab
// ---------------------------------------------------------------------------

function PatternsTab({ pack, packId }: { pack: Pack; packId: number }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [addOpen, setAddOpen] = useState(false)
  const [pattern, setPattern] = useState('')
  const [source, setSource] = useState('')
  const [uploader, setUploader] = useState('')

  async function handleAdd() {
    if (!pattern.trim()) return
    try {
      await addPackPattern(packId, {
        pattern: pattern.trim(),
        source: source.trim() || undefined,
        uploader: uploader.trim() || undefined,
      })
      toast.success(t('packs.patternAdded'))
      setAddOpen(false)
      setPattern('')
      setSource('')
      setUploader('')
      queryClient.invalidateQueries({ queryKey: ['pack', packId] })
    } catch {
      toast.error(t('packs.patternAddError'))
    }
  }

  async function handleDelete(patternId: number) {
    try {
      await deletePackPattern(packId, patternId)
      toast.success(t('packs.patternDeleted'))
      queryClient.invalidateQueries({ queryKey: ['pack', packId] })
    } catch {
      toast.error(t('packs.patternDeleteError'))
    }
  }

  return (
    <div className="pt-4 space-y-4">
      <div className="flex justify-between items-center">
        <p className="text-sm text-zinc-400">
          {t('packs.patterns', { count: pack.patterns?.length ?? 0 })}
        </p>
        <Button size="sm" onClick={() => setAddOpen(true)}>
          <Plus className="size-3.5" />
          {t('packs.addPattern')}
        </Button>
      </div>

      {pack.patterns && pack.patterns.length > 0 ? (
        <Table>
          <TableHeader>
            <TableRow className="border-zinc-800 hover:bg-transparent">
              <TableHead className="text-zinc-400">Pattern</TableHead>
              <TableHead className="text-zinc-400 w-32">{t('packs.source')}</TableHead>
              <TableHead className="text-zinc-400 w-32">{t('packs.uploader')}</TableHead>
              <TableHead className="text-zinc-400 w-36">{t('history.date')}</TableHead>
              <TableHead className="text-zinc-400 w-12" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {pack.patterns.map((p) => (
              <TableRow key={p.id} className="border-zinc-800">
                <TableCell className="text-zinc-100 text-sm">
                  <span className="line-clamp-2">{p.pattern}</span>
                </TableCell>
                <TableCell className="text-zinc-400 text-sm">{p.source || '-'}</TableCell>
                <TableCell className="text-zinc-400 text-sm">{p.uploader || '-'}</TableCell>
                <TableCell className="text-zinc-500 text-sm">
                  {new Date(p.lastSeenAt).toLocaleDateString()}
                </TableCell>
                <TableCell>
                  <button
                    type="button"
                    onClick={() => handleDelete(p.id)}
                    className="p-1 text-zinc-500 hover:text-red-400"
                  >
                    <X className="size-4" />
                  </button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      ) : (
        <p className="text-sm text-zinc-500 text-center py-8">{t('common.noResults')}</p>
      )}

      {/* Add Pattern Dialog */}
      <Dialog open={addOpen} onOpenChange={setAddOpen}>
        <DialogContent className="sm:max-w-lg bg-zinc-950 border-zinc-800">
          <DialogHeader>
            <DialogTitle className="text-zinc-100">{t('packs.addPattern')}</DialogTitle>
          </DialogHeader>
          <div className="grid gap-4 py-2">
            <div className="grid gap-1.5">
              <label className="text-sm font-medium text-zinc-300">Pattern</label>
              <Input
                value={pattern}
                onChange={(e) => setPattern(e.target.value)}
                placeholder={t('packs.patternPlaceholder')}
                className="bg-zinc-900 border-zinc-700 text-zinc-100"
              />
            </div>
            <div className="grid gap-1.5">
              <label className="text-sm font-medium text-zinc-300">{t('packs.source')}</label>
              <Input
                value={source}
                onChange={(e) => setSource(e.target.value)}
                placeholder={t('packs.sourcePlaceholder')}
                className="bg-zinc-900 border-zinc-700 text-zinc-100"
              />
            </div>
            <div className="grid gap-1.5">
              <label className="text-sm font-medium text-zinc-300">{t('packs.uploader')}</label>
              <Input
                value={uploader}
                onChange={(e) => setUploader(e.target.value)}
                placeholder={t('packs.uploaderPlaceholder')}
                className="bg-zinc-900 border-zinc-700 text-zinc-100"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setAddOpen(false)}>{t('common.cancel')}</Button>
            <Button onClick={handleAdd} disabled={!pattern.trim()}>{t('common.add')}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Rules Tab
// ---------------------------------------------------------------------------

function RulesTab({ pack, packId }: { pack: Pack; packId: number }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [addOpen, setAddOpen] = useState(false)
  const [ruleType, setRuleType] = useState<string>('exclude')
  const [rulePattern, setRulePattern] = useState('')

  async function handleAdd() {
    if (!rulePattern.trim()) return
    try {
      await addPackRule(packId, {
        ruleType,
        pattern: rulePattern.trim(),
      })
      toast.success(t('packs.ruleAdded'))
      setAddOpen(false)
      setRulePattern('')
      queryClient.invalidateQueries({ queryKey: ['pack', packId] })
    } catch {
      toast.error(t('packs.ruleAddError'))
    }
  }

  async function handleDelete(ruleId: number) {
    try {
      await deletePackRule(packId, ruleId)
      toast.success(t('packs.ruleDeleted'))
      queryClient.invalidateQueries({ queryKey: ['pack', packId] })
    } catch {
      toast.error(t('packs.ruleDeleteError'))
    }
  }

  return (
    <div className="pt-4 space-y-4">
      <div className="flex justify-between items-center">
        <p className="text-sm text-zinc-400">
          {pack.rules?.length ?? 0} {t('packs.tabRules').toLowerCase()}
        </p>
        <Button size="sm" onClick={() => setAddOpen(true)}>
          <Plus className="size-3.5" />
          {t('packs.addRule')}
        </Button>
      </div>

      {pack.rules && pack.rules.length > 0 ? (
        <Table>
          <TableHeader>
            <TableRow className="border-zinc-800 hover:bg-transparent">
              <TableHead className="text-zinc-400 w-24">{t('packs.ruleType')}</TableHead>
              <TableHead className="text-zinc-400">{t('packs.rulePattern')}</TableHead>
              <TableHead className="text-zinc-400 w-12" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {pack.rules.map((r) => (
              <TableRow key={r.id} className="border-zinc-800">
                <TableCell>
                  <Badge variant={r.ruleType === 'include' ? 'default' : 'destructive'} className={r.ruleType === 'include' ? 'bg-green-700' : ''}>
                    {t(`packs.${r.ruleType}`)}
                  </Badge>
                </TableCell>
                <TableCell className="text-zinc-100 text-sm font-mono">{r.pattern}</TableCell>
                <TableCell>
                  <button
                    type="button"
                    onClick={() => handleDelete(r.id)}
                    className="p-1 text-zinc-500 hover:text-red-400"
                  >
                    <X className="size-4" />
                  </button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      ) : (
        <p className="text-sm text-zinc-500 text-center py-8">{t('common.noResults')}</p>
      )}

      {/* Add Rule Dialog */}
      <Dialog open={addOpen} onOpenChange={setAddOpen}>
        <DialogContent className="sm:max-w-md bg-zinc-950 border-zinc-800">
          <DialogHeader>
            <DialogTitle className="text-zinc-100">{t('packs.addRule')}</DialogTitle>
          </DialogHeader>
          <div className="grid gap-4 py-2">
            <div className="grid gap-1.5">
              <label className="text-sm font-medium text-zinc-300">{t('packs.ruleType')}</label>
              <Select value={ruleType} onValueChange={setRuleType}>
                <SelectTrigger className="bg-zinc-900 border-zinc-700 text-zinc-100 w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="include">{t('packs.include')}</SelectItem>
                  <SelectItem value="exclude">{t('packs.exclude')}</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-1.5">
              <label className="text-sm font-medium text-zinc-300">{t('packs.rulePattern')}</label>
              <Input
                value={rulePattern}
                onChange={(e) => setRulePattern(e.target.value)}
                placeholder={t('packs.rulePatternPlaceholder')}
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
