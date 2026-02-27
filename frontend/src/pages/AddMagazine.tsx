import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import { Search, Loader2, Plus, Library } from 'lucide-react'
import { toast } from 'sonner'

import {
  searchMetadata,
  createMagazine,
  type MetadataSearchResult,
} from '@/api/magazines'
import { getProfiles } from '@/api/quality'
import { getRootFolders } from '@/api/system'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Switch } from '@/components/ui/switch'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'

export default function AddMagazine() {
  const { t } = useTranslation()
  const navigate = useNavigate()

  const [query, setQuery] = useState('')
  const [results, setResults] = useState<MetadataSearchResult[]>([])
  const [searching, setSearching] = useState(false)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Manual add dialog
  const [manualOpen, setManualOpen] = useState(false)
  const [manualTitle, setManualTitle] = useState('')
  const [manualFrequency, setManualFrequency] = useState('monthly')
  const [excludedDays, setExcludedDays] = useState<number[]>([])
  const [rootFolderId, setRootFolderId] = useState<string>('')
  const [qualityProfileId, setQualityProfileId] = useState<string>('')
  const [monitoringStartDate, setMonitoringStartDate] = useState('')
  const [searchForMissing, setSearchForMissing] = useState(true)
  const [adding, setAdding] = useState(false)

  // Selected metadata result for add dialog
  const [selectedResult, setSelectedResult] = useState<MetadataSearchResult | null>(null)

  const { data: profiles = [] } = useQuery({
    queryKey: ['qualityProfiles'],
    queryFn: getProfiles,
  })

  const { data: rootFolders = [] } = useQuery({
    queryKey: ['rootFolders'],
    queryFn: getRootFolders,
  })

  // Set defaults when loaded
  useEffect(() => {
    if (profiles.length > 0 && !qualityProfileId) {
      const defaultProfile = profiles.find((p) => p.isDefault) || profiles[0]
      setQualityProfileId(String(defaultProfile.id))
    }
  }, [profiles, qualityProfileId])

  useEffect(() => {
    if (rootFolders.length > 0 && !rootFolderId) {
      const defaultFolder = rootFolders.find((f) => f.isDefault) || rootFolders[0]
      setRootFolderId(String(defaultFolder.id))
    }
  }, [rootFolders, rootFolderId])

  // Debounced search
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    if (query.trim().length < 2) {
      setResults([])
      return
    }
    debounceRef.current = setTimeout(async () => {
      setSearching(true)
      try {
        const data = await searchMetadata(query.trim())
        setResults(data)
      } catch {
        toast.error(t('addMagazine.searchError'))
      } finally {
        setSearching(false)
      }
    }, 500)
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [query, t])

  function openAddFromResult(result: MetadataSearchResult) {
    setSelectedResult(result)
    setManualTitle(result.title)
    if (result.frequency) setManualFrequency(result.frequency)
    setExcludedDays([])
    setManualOpen(true)
  }

  function openManualAdd() {
    setSelectedResult(null)
    setManualTitle('')
    setExcludedDays([])
    setManualOpen(true)
  }

  async function handleAdd() {
    if (!manualTitle.trim()) return
    setAdding(true)
    try {
      const magazine = await createMagazine({
        title: manualTitle.trim(),
        frequency: manualFrequency,
        excludedDays: excludedDays.length > 0 ? excludedDays : undefined,
        rootFolderId: rootFolderId ? Number(rootFolderId) : undefined,
        qualityProfileId: qualityProfileId ? Number(qualityProfileId) : undefined,
        monitoringStartDate: monitoringStartDate || undefined,
        metadataProvider: selectedResult?.provider ?? undefined,
        metadataProviderId: selectedResult?.providerId ?? undefined,
        searchForMissingIssues: searchForMissing,
      })
      toast.success(t('addMagazine.added'))
      setManualOpen(false)
      navigate(`/magazine/${magazine.id}`)
    } catch {
      toast.error(t('addMagazine.addError'))
    } finally {
      setAdding(false)
    }
  }

  return (
    <div className="p-8 max-w-4xl">
      <h1 className="text-2xl font-bold text-zinc-100 mb-6">{t('addMagazine.title')}</h1>

      {/* Search */}
      <div className="relative mb-6">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-zinc-500" />
        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={t('addMagazine.searchPlaceholder')}
          className="pl-10 bg-zinc-900 border-zinc-700 text-zinc-100"
        />
        {searching && (
          <Loader2 className="absolute right-3 top-1/2 -translate-y-1/2 size-4 animate-spin text-zinc-400" />
        )}
      </div>

      {/* Results */}
      {results.length > 0 && (
        <div className="space-y-2 mb-6">
          {results.map((result) => (
            <div
              key={`${result.provider}-${result.providerId}`}
              className="flex items-center gap-4 rounded-md border border-zinc-800 bg-zinc-950 px-4 py-3"
            >
              {/* Cover thumbnail */}
              <div className="size-16 shrink-0 rounded bg-zinc-800 overflow-hidden">
                {result.coverUrl ? (
                  <img
                    src={result.coverUrl}
                    alt=""
                    className="h-full w-full object-cover"
                  />
                ) : (
                  <div className="flex items-center justify-center h-full text-zinc-600 text-xs">
                    N/A
                  </div>
                )}
              </div>

              {/* Info */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <p className="text-sm font-medium text-zinc-100 truncate">
                    {result.title}
                  </p>
                  <Badge variant="outline" className="text-xs shrink-0">
                    {result.provider === 'internet_archive' ? 'Internet Archive' : 'Google Books'}
                  </Badge>
                  {result.alreadyInLibrary && (
                    <Badge variant="secondary" className="text-xs">
                      <Library className="size-3" />
                      {t('addMagazine.inLibrary')}
                    </Badge>
                  )}
                </div>
                {result.publisher && (
                  <p className="text-xs text-zinc-500">{result.publisher}</p>
                )}
                {result.description && (
                  <p className="text-xs text-zinc-400 mt-1 line-clamp-2">
                    {result.description}
                  </p>
                )}
              </div>

              {/* Add button */}
              <Button
                variant="outline"
                size="sm"
                disabled={result.alreadyInLibrary}
                onClick={() => openAddFromResult(result)}
              >
                <Plus className="size-3.5" />
                {t('common.add')}
              </Button>
            </div>
          ))}
        </div>
      )}

      {/* No results */}
      {query.trim().length >= 2 && !searching && results.length === 0 && (
        <p className="text-zinc-500 text-center py-4">{t('common.noResults')}</p>
      )}

      {/* Manual add button */}
      <div className="flex justify-center">
        <Button variant="outline" onClick={openManualAdd}>
          <Plus className="size-4" />
          {t('addMagazine.manualAdd')}
        </Button>
      </div>

      {/* Add Dialog */}
      <Dialog open={manualOpen} onOpenChange={setManualOpen}>
        <DialogContent className="sm:max-w-lg bg-zinc-950 border-zinc-800">
          <DialogHeader>
            <DialogTitle className="text-zinc-100">
              {selectedResult
                ? t('addMagazine.addTitle', { title: selectedResult.title })
                : t('addMagazine.manualAddTitle')}
            </DialogTitle>
          </DialogHeader>

          <div className="grid gap-4 py-2">
            {/* Title */}
            <div className="grid gap-1.5">
              <label className="text-sm font-medium text-zinc-300">
                {t('addMagazine.magazineTitle')}
              </label>
              <Input
                value={manualTitle}
                onChange={(e) => setManualTitle(e.target.value)}
                placeholder={t('addMagazine.titlePlaceholder')}
                className="bg-zinc-900 border-zinc-700 text-zinc-100"
              />
            </div>

            {/* Frequency */}
            <div className="grid gap-1.5">
              <label className="text-sm font-medium text-zinc-300">
                {t('addMagazine.frequency')}
              </label>
              <Select value={manualFrequency} onValueChange={setManualFrequency}>
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
              {['daily', 'weekly', 'biweekly'].includes(manualFrequency) && (
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
                          setExcludedDays((prev) =>
                            prev.includes(day) ? prev.filter((d) => d !== day) : [...prev, day]
                          )
                        }
                        className={`px-2 py-1 text-xs rounded border ${
                          excludedDays.includes(day)
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

            {/* Root Folder */}
            <div className="grid gap-1.5">
              <label className="text-sm font-medium text-zinc-300">
                {t('addMagazine.rootFolder')}
              </label>
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
              <label className="text-sm font-medium text-zinc-300">
                {t('addMagazine.qualityProfile')}
              </label>
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

            {/* Monitoring Start Date */}
            <div className="grid gap-1.5">
              <label className="text-sm font-medium text-zinc-300">
                {t('addMagazine.monitoringStartDate')}
              </label>
              <Input
                type="date"
                value={monitoringStartDate}
                onChange={(e) => setMonitoringStartDate(e.target.value)}
                className="bg-zinc-900 border-zinc-700 text-zinc-100"
              />
            </div>

            {/* Search for missing */}
            <div className="flex items-center justify-between">
              <label className="text-sm font-medium text-zinc-300">
                {t('addMagazine.searchForMissing')}
              </label>
              <Switch
                checked={searchForMissing}
                onCheckedChange={(checked) => setSearchForMissing(checked === true)}
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setManualOpen(false)}>
              {t('common.cancel')}
            </Button>
            <Button
              onClick={handleAdd}
              disabled={!manualTitle.trim() || adding}
            >
              {adding && <Loader2 className="size-4 animate-spin" />}
              {t('common.add')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
