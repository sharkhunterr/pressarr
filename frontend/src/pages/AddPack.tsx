import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import { Loader2, Search, Check, ArrowDownUp, ChevronLeft, ChevronRight } from 'lucide-react'
import { toast } from 'sonner'

import { createPack, addPackPattern } from '@/api/packs'
import {
  searchIndexers,
  searchInternetArchive,
  searchAnnasArchive,
  type SearchResult,
} from '@/api/search'
import { getProfiles } from '@/api/quality'
import { getRootFolders } from '@/api/system'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

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

interface SelectedPattern {
  title: string
  source: string
}

export default function AddPack() {
  const { t } = useTranslation()
  const navigate = useNavigate()

  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [recurrence, setRecurrence] = useState('monthly')
  const [rootFolderId, setRootFolderId] = useState('')
  const [qualityProfileId, setQualityProfileId] = useState('')
  const [adding, setAdding] = useState(false)

  // Search & patterns
  const [searchSource, setSearchSource] = useState('indexers')
  const [searchQuery, setSearchQuery] = useState('')
  const [results, setResults] = useState<SearchResult[]>([])
  const [searching, setSearching] = useState(false)
  const [selectedPatterns, setSelectedPatterns] = useState<SelectedPattern[]>([])
  const [sourceFilter, setSourceFilter] = useState('')
  const [dateSort, setDateSort] = useState<'' | 'asc' | 'desc'>('')
  const [page, setPage] = useState(1)

  const { data: profiles = [] } = useQuery({
    queryKey: ['qualityProfiles'],
    queryFn: getProfiles,
  })

  const { data: rootFolders = [] } = useQuery({
    queryKey: ['rootFolders'],
    queryFn: getRootFolders,
  })

  useEffect(() => {
    if (profiles.length > 0 && !qualityProfileId) {
      const def = profiles.find((p) => p.isDefault) || profiles[0]
      setQualityProfileId(String(def.id))
    }
  }, [profiles, qualityProfileId])

  useEffect(() => {
    if (rootFolders.length > 0 && !rootFolderId) {
      const def = rootFolders.find((f) => f.isDefault) || rootFolders[0]
      setRootFolderId(String(def.id))
    }
  }, [rootFolders, rootFolderId])

  async function handleSearch() {
    if (!searchQuery.trim()) return
    setSearching(true)
    setResults([])
    setPage(1)
    setSourceFilter('')
    setDateSort('')
    try {
      let data: SearchResult[]
      switch (searchSource) {
        case 'internetarchive':
          data = await searchInternetArchive(searchQuery.trim())
          break
        case 'annasarchive':
          data = await searchAnnasArchive(searchQuery.trim())
          break
        default:
          data = await searchIndexers(searchQuery.trim())
      }
      setResults(data)
    } catch {
      toast.error(t('issues.searchError'))
    } finally {
      setSearching(false)
    }
  }

  function togglePattern(result: SearchResult) {
    setSelectedPatterns((prev) => {
      const exists = prev.some((p) => p.title === result.title)
      if (exists) {
        return prev.filter((p) => p.title !== result.title)
      }
      return [...prev, { title: result.title, source: result.indexer }]
    })
  }

  function isSelected(result: SearchResult) {
    return selectedPatterns.some((p) => p.title === result.title)
  }

  async function handleAdd() {
    if (!name.trim() || !searchQuery.trim()) return
    setAdding(true)
    try {
      const pack = await createPack({
        name: name.trim(),
        description: description.trim() || undefined,
        searchQuery: searchQuery.trim(),
        recurrence,
        qualityProfileId: Number(qualityProfileId),
        rootFolderId: Number(rootFolderId),
      })

      // Save selected patterns
      for (const sp of selectedPatterns) {
        try {
          await addPackPattern(pack.id, {
            pattern: sp.title,
            source: sp.source || undefined,
          })
        } catch {
          // Pattern save errors are non-critical
        }
      }

      toast.success(t('packs.created'))
      navigate(`/pack/${pack.id}`)
    } catch {
      toast.error(t('packs.createError'))
    } finally {
      setAdding(false)
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
    <div className="p-4 lg:p-8 max-w-3xl overflow-hidden">
      <h1 className="text-2xl font-bold text-zinc-100 mb-6">{t('packs.addPack')}</h1>

      <div className="grid gap-4">
        {/* Name */}
        <div className="grid gap-1.5">
          <label className="text-sm font-medium text-zinc-300">{t('packs.name')}</label>
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder={t('packs.namePlaceholder')}
            className="bg-zinc-900 border-zinc-700 text-zinc-100"
          />
        </div>

        {/* Description */}
        <div className="grid gap-1.5">
          <label className="text-sm font-medium text-zinc-300">{t('packs.description')}</label>
          <Input
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder={t('packs.descriptionPlaceholder')}
            className="bg-zinc-900 border-zinc-700 text-zinc-100"
          />
        </div>

        {/* Recurrence */}
        <div className="grid gap-1.5">
          <label className="text-sm font-medium text-zinc-300">{t('packs.recurrence')}</label>
          <Select value={recurrence} onValueChange={setRecurrence}>
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

        {/* Root Folder */}
        <div className="grid gap-1.5">
          <label className="text-sm font-medium text-zinc-300">{t('packs.rootFolder')}</label>
          <Select value={rootFolderId} onValueChange={setRootFolderId}>
            <SelectTrigger className="bg-zinc-900 border-zinc-700 text-zinc-100 w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {rootFolders.map((folder) => (
                <SelectItem key={folder.id} value={String(folder.id)}>
                  {folder.path}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Quality Profile */}
        <div className="grid gap-1.5">
          <label className="text-sm font-medium text-zinc-300">{t('packs.qualityProfile')}</label>
          <Select value={qualityProfileId} onValueChange={setQualityProfileId}>
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

        {/* Search & Select Patterns — same layout as Manual Research */}
        <div className="space-y-4 mt-2">
          <div>
            <p className="text-sm font-medium text-zinc-100">{t('packs.searchAndSelect')}</p>
            <p className="text-xs text-zinc-500 mt-0.5">{t('packs.searchAndSelectDesc')}</p>
          </div>

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
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') handleSearch() }}
              placeholder={t('magazineDetail.searchPlaceholder')}
              className="bg-zinc-900 border-zinc-700 text-zinc-100 flex-1"
            />
            <Button onClick={handleSearch} disabled={searching || !searchQuery.trim()}>
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

          {/* Selected patterns count */}
          {selectedPatterns.length > 0 && (
            <p className="text-xs text-[#7C3AED] font-medium">
              {t('packs.selectedPatterns', { count: selectedPatterns.length })}
            </p>
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
                  const selected = isSelected(result)
                  return (
                    <div
                      key={result.guid}
                      className={`py-3 px-2 rounded cursor-pointer transition-colors ${
                        selected ? 'bg-[#7C3AED]/10' : 'hover:bg-zinc-900/50'
                      } ${result.isBlocklisted ? 'opacity-40' : ''}`}
                      onClick={() => togglePattern(result)}
                    >
                      <div className="flex items-center gap-3 flex-1 min-w-0">
                        <div className={`size-5 rounded border flex items-center justify-center shrink-0 transition-colors ${
                          selected ? 'bg-[#7C3AED] border-[#7C3AED]' : 'border-zinc-600'
                        }`}>
                          {selected && <Check className="size-3.5 text-white" />}
                        </div>
                        <div className="flex-1 min-w-0">
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

        {/* Submit */}
        <div className="flex justify-end gap-2 mt-2">
          <Button variant="outline" onClick={() => navigate('/packs')}>
            {t('common.cancel')}
          </Button>
          <Button
            onClick={handleAdd}
            disabled={!name.trim() || !searchQuery.trim() || adding}
          >
            {adding && <Loader2 className="size-4 animate-spin" />}
            {selectedPatterns.length > 0 ? t('packs.createWithPatterns') : t('common.add')}
          </Button>
        </div>
      </div>
    </div>
  )
}
