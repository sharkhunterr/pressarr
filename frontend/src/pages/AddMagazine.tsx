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
import { IssueGroupsEditor, type IssueGroup } from '@/components/IssueGroupsEditor'
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

import { shortenPath } from '@/lib/utils'

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
  const [releaseWeekday, setReleaseWeekday] = useState<number | null>(null)
  const [weekendDays] = useState<number[]>([])
  const [issueGroups, setIssueGroups] = useState<IssueGroup[]>([])
  const [sortByRecentDate, setSortByRecentDate] = useState(true)
  const [minTitleMatchOverride, setMinTitleMatchOverride] = useState<string>('')
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
    setIssueGroups([])
    setManualOpen(true)
  }

  function openManualAdd() {
    setSelectedResult(null)
    setManualTitle('')
    setExcludedDays([])
    setIssueGroups([])
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
        releaseWeekday: releaseWeekday,
        weekendDays: weekendDays.length > 0 ? weekendDays : undefined,
        issueGroups:
          issueGroups.length > 0
            ? issueGroups.map((g) => ({ ...g, label: g.label ?? null }))
            : undefined,
        sortByRecentDate,
        minTitleMatchOverride: minTitleMatchOverride.trim()
          ? Number(minTitleMatchOverride)
          : undefined,
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
    <div className="p-4 lg:p-8">
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
                  {result.sources.map((s) => {
                    const label = s.provider === 'internet_archive'
                      ? t('addMagazine.sourceInternetArchive')
                      : t('addMagazine.sourceGoogleBooks')
                    return (
                      <Badge key={s.provider} variant="outline" className="text-xs shrink-0">
                        {s.count > 1 ? `${label} (${s.count})` : label}
                      </Badge>
                    )
                  })}
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
              {/* Sélecteur weekday — uniquement pour DAILY. Un weekly
                  publie 1 jour fixe (releaseWeekday plus bas), pas
                  besoin d'exclure les autres. Monthly+ n'utilise pas
                  la notion de jour de la semaine. */}
              {manualFrequency === 'daily' && (
                <div className="grid gap-4 mt-2">
                  {/* Jours sans publication — chips rouge simple */}
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
                        const isEx = excludedDays.includes(d)
                        return (
                          <button
                            key={d}
                            type="button"
                            onClick={() => {
                              const next = isEx
                                ? excludedDays.filter((x) => x !== d)
                                : [...excludedDays, d]
                              setExcludedDays(next)
                              // Retire des groupes si on exclut
                              if (!isEx) {
                                setIssueGroups(
                                  issueGroups
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
                      Jours rouges = pas d'édition (ex. dimanche pour la
                      plupart des quotidiens FR).
                    </p>
                  </div>

                  {/* Groupes d'issues combinées — multi + typés */}
                  <div className="grid gap-1.5">
                    <label className="text-sm font-medium text-zinc-300">
                      Groupes d'issues combinées
                    </label>
                    <p className="text-xs text-zinc-500">
                      Regroupe plusieurs jours consécutifs en <strong>1
                      seule issue</strong> émise sur le dernier jour du
                      groupe. Chaque groupe a un type
                      (Régulier / Weekend / Spécial) qui pilote le badge
                      affiché sur la row. Ex Le Monde : groupe
                      (dim + lun) type Régulier pour l'édition combinée
                      du lundi, groupe (sam) type Weekend pour l'édition
                      WEEK-END du samedi.
                    </p>
                    <IssueGroupsEditor
                      groups={issueGroups}
                      excluded={excludedDays}
                      onChange={setIssueGroups}
                    />
                  </div>
                </div>
              )}
              {['weekly', 'biweekly'].includes(manualFrequency) && (
                <div className="grid gap-1.5 mt-2">
                  <label className="text-sm font-medium text-zinc-300">
                    Jour de publication
                  </label>
                  <div className="flex flex-wrap gap-1">
                    <button
                      type="button"
                      onClick={() => setReleaseWeekday(null)}
                      className={`px-2 py-1 text-xs rounded border ${
                        releaseWeekday == null
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
                        onClick={() => setReleaseWeekday(day)}
                        className={`px-2 py-1 text-xs rounded border ${
                          releaseWeekday === day
                            ? 'bg-purple-900/50 border-purple-600 text-purple-200'
                            : 'bg-zinc-900 border-zinc-700 text-zinc-400'
                        }`}
                      >
                        {t(key)}
                      </button>
                    ))}
                  </div>
                  <p className="text-xs text-zinc-500">
                    Auto = déduit du dernier numéro connu. Sinon les prévisions s'alignent sur ce jour.
                  </p>
                </div>
              )}
            </div>

            {/* ── Section recherche automatique (IA) ─────────────── */}
            <div className="border-t border-zinc-800 pt-4 space-y-4">
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
                  checked={sortByRecentDate}
                  onCheckedChange={(v) => setSortByRecentDate(v === true)}
                />
              </div>

              <div className="grid gap-1.5">
                <div className="flex items-baseline justify-between">
                  <label className="text-sm font-medium text-zinc-300">
                    Exigence de correspondance du titre
                  </label>
                  <span className="text-xs font-mono text-zinc-400 tabular-nums">
                    {minTitleMatchOverride === ''
                      ? 'Auto (80 %)'
                      : `${minTitleMatchOverride} %`}
                  </span>
                </div>
                <input
                  type="range"
                  min={0}
                  max={100}
                  step={5}
                  value={minTitleMatchOverride === '' ? 80 : Number(minTitleMatchOverride)}
                  onChange={(e) => setMinTitleMatchOverride(e.target.value)}
                  className="w-full accent-purple-500 h-2 rounded-lg bg-zinc-800 cursor-pointer"
                />
                <div className="flex justify-between text-[10px] text-zinc-600 tabular-nums">
                  <span>Souple (0)</span>
                  <span>Strict (100)</span>
                </div>
                <div className="flex items-center justify-between">
                  <p className="text-xs text-zinc-500 flex-1 pr-2">
                    Similarité minimale entre le titre du release et
                    celui du magazine pour autoriser l'auto-grab. Monte
                    (90+) pour un mag ambigu ("Le Monde" ≠ "Le Monde
                    Diplomatique"). Baisse (70) pour un mag au nom court.
                  </p>
                  {minTitleMatchOverride !== '' && (
                    <button
                      type="button"
                      onClick={() => setMinTitleMatchOverride('')}
                      className="text-xs text-purple-400 hover:text-purple-300 shrink-0"
                    >
                      Reset auto
                    </button>
                  )}
                </div>
              </div>
            </div>

            {/* Root Folder */}
            <div className="grid gap-1.5">
              <label className="text-sm font-medium text-zinc-300">
                {t('addMagazine.rootFolder')}
              </label>
              <Select value={rootFolderId} onValueChange={setRootFolderId}>
                <SelectTrigger className="bg-zinc-900 border-zinc-700 text-zinc-100 w-full truncate">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {rootFolders.map((folder) => (
                    <SelectItem key={folder.id} value={String(folder.id)}>
                      {shortenPath(folder.path)}
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
