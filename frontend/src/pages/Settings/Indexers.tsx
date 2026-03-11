import { useState, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Pencil, Trash2, FlaskConical, Loader2, Eye, EyeOff } from 'lucide-react'
import { toast } from 'sonner'

import {
  getIndexers,
  createIndexer,
  updateIndexer,
  deleteIndexer,
  testIndexer,
  type IndexerConfig,
  type IndexerOverrideEntry,
  type ProwlarrIndexerInfo,
} from '@/api/downloads'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Switch } from '@/components/ui/switch'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'

interface IndexerFormState {
  name: string
  url: string
  apiKey: string
  categories: string
  enabled: boolean
  overrides: Record<string, IndexerOverrideEntry>
}

function emptyForm(): IndexerFormState {
  return { name: '', url: '', apiKey: '', categories: '', enabled: true, overrides: {} }
}

function indexerToForm(i: IndexerConfig): IndexerFormState {
  return {
    name: i.name,
    url: i.url,
    apiKey: i.apiKey ?? '',
    categories: i.categories,
    enabled: i.enabled,
    overrides: i.indexerOverrides ?? {},
  }
}

export default function Indexers() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()

  const [dialogOpen, setDialogOpen] = useState(false)
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [deletingIndexer, setDeletingIndexer] = useState<IndexerConfig | null>(null)
  const [form, setForm] = useState<IndexerFormState>(emptyForm())
  const [testing, setTesting] = useState(false)
  const [showApiKey, setShowApiKey] = useState(false)
  const [detectedIndexers, setDetectedIndexers] = useState<ProwlarrIndexerInfo[]>([])

  const { data: indexers = [], isLoading } = useQuery({
    queryKey: ['indexers'],
    queryFn: getIndexers,
  })

  const invalidate = useCallback(
    () => queryClient.invalidateQueries({ queryKey: ['indexers'] }),
    [queryClient],
  )

  const createMutation = useMutation({
    mutationFn: (data: Partial<IndexerConfig> & { apiKey: string }) => createIndexer(data),
    onSuccess: () => {
      invalidate()
      setDialogOpen(false)
      toast.success(t('indexers.created'))
    },
    onError: () => toast.error(t('indexers.createError')),
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<IndexerConfig> & { apiKey?: string } }) =>
      updateIndexer(id, data),
    onSuccess: () => {
      invalidate()
      setDialogOpen(false)
      toast.success(t('indexers.updated'))
    },
    onError: () => toast.error(t('indexers.updateError')),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteIndexer(id),
    onSuccess: () => {
      invalidate()
      setDeleteDialogOpen(false)
      setDeletingIndexer(null)
      toast.success(t('indexers.deleted'))
    },
    onError: () => toast.error(t('indexers.deleteError')),
  })

  function openCreate() {
    setEditingId(null)
    setForm(emptyForm())
    setDetectedIndexers([])
    setShowApiKey(false)
    setDialogOpen(true)
  }

  function openEdit(indexer: IndexerConfig) {
    setEditingId(indexer.id)
    setForm(indexerToForm(indexer))
    setDetectedIndexers([])
    setShowApiKey(false)
    setDialogOpen(true)
  }

  function openDelete(indexer: IndexerConfig) {
    setDeletingIndexer(indexer)
    setDeleteDialogOpen(true)
  }

  function handleSave() {
    const payload = {
      name: form.name,
      url: form.url,
      apiKey: form.apiKey,
      categories: form.categories,
      enabled: form.enabled,
      indexerOverrides: form.overrides,
    }
    if (editingId !== null) {
      updateMutation.mutate({ id: editingId, data: payload })
    } else {
      createMutation.mutate(payload)
    }
  }

  function toggleOverrideEnabled(prowlarrId: number) {
    setForm((f) => {
      const key = String(prowlarrId)
      const current = f.overrides[key] ?? { enabled: true }
      return {
        ...f,
        overrides: {
          ...f.overrides,
          [key]: { ...current, enabled: !current.enabled },
        },
      }
    })
  }

  function isIndexerEnabled(prowlarrId: number): boolean {
    const entry = form.overrides[String(prowlarrId)]
    return entry?.enabled ?? true
  }

  function getSelectedCategories(prowlarrId: number, availableCats: number[]): Set<number> {
    const entry = form.overrides[String(prowlarrId)]
    if (entry?.categories) {
      return new Set(entry.categories.split(',').map(Number).filter(Boolean))
    }
    // Default: global categories that this indexer supports
    const globalCats = new Set(form.categories.split(',').map(Number).filter(Boolean))
    return new Set(availableCats.filter((c) => globalCats.has(c)))
  }

  function toggleOverrideCategory(prowlarrId: number, category: number) {
    setForm((f) => {
      const key = String(prowlarrId)
      const current = f.overrides[key] ?? { enabled: true }

      const idx = detectedIndexers.find((i) => i.id === prowlarrId)
      const availableCats = idx ? idx.categories.filter((c) => c >= 7000 && c < 8000) : []

      // Get current selected categories
      let selectedCats: Set<number>
      if (current.categories) {
        selectedCats = new Set(current.categories.split(',').map(Number).filter(Boolean))
      } else {
        // Initialize from global categories
        const globalCats = new Set(f.categories.split(',').map(Number).filter(Boolean))
        selectedCats = new Set(availableCats.filter((c) => globalCats.has(c)))
      }

      // Toggle
      if (selectedCats.has(category)) {
        selectedCats.delete(category)
      } else {
        selectedCats.add(category)
      }

      const newCatsStr =
        selectedCats.size > 0
          ? [...selectedCats].sort((a, b) => a - b).join(',')
          : null

      return {
        ...f,
        overrides: {
          ...f.overrides,
          [key]: { ...current, categories: newCatsStr },
        },
      }
    })
  }

  async function handleTest() {
    if (!form.url || !form.apiKey) {
      toast.error(t('indexers.testMissingFields'))
      return
    }
    setTesting(true)
    try {
      const result = await testIndexer({ url: form.url, apiKey: form.apiKey })

      if (result.isValid) {
        toast.success(t('indexers.testSuccess'))
        if (result.indexers && result.indexers.length > 0) {
          setDetectedIndexers(result.indexers)
          setForm((f) => {
            // Ensure all detected indexers have override entries
            const newOverrides = { ...f.overrides }
            for (const idx of result.indexers!) {
              if (!newOverrides[String(idx.id)]) {
                newOverrides[String(idx.id)] = { enabled: true }
              }
            }
            // If no categories set yet, pre-select book-related ones
            let categories = f.categories
            if (!categories.trim()) {
              const allCats = new Set<number>()
              result.indexers!.forEach((idx) => idx.categories.forEach((c) => allCats.add(c)))
              const bookCats = [...allCats].filter((c) => c >= 7000 && c < 8000).sort((a, b) => a - b)
              categories = bookCats.join(',')
            }
            return { ...f, categories, overrides: newOverrides }
          })
        }
      } else {
        toast.error(result.message || t('indexers.testFailed'))
        setDetectedIndexers([])
      }
    } catch {
      toast.error(t('indexers.testFailed'))
      setDetectedIndexers([])
    } finally {
      setTesting(false)
    }
  }

  if (isLoading) {
    return (
      <div className="p-4 lg:p-8 text-zinc-400">
        {t('common.loading')}
      </div>
    )
  }

  return (
    <div className="p-4 lg:p-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-zinc-100">
          {t('indexers.title')}
        </h1>
        <Button onClick={openCreate}>
          <Plus className="size-4" />
          {t('common.add')}
        </Button>
      </div>

      <div className="grid gap-4">
        {indexers.map((indexer) => (
          <Card key={indexer.id} className="bg-zinc-950 border-zinc-800">
            <CardHeader className="flex-row items-center justify-between">
              <div className="flex items-center gap-3">
                <CardTitle className="text-zinc-100">{indexer.name}</CardTitle>
                <Badge variant={indexer.enabled ? 'default' : 'outline'}>
                  {indexer.enabled ? t('indexers.enabled') : t('indexers.disabled')}
                </Badge>
              </div>
              <div className="flex gap-2">
                <Button variant="ghost" size="icon-sm" onClick={() => openEdit(indexer)}>
                  <Pencil className="size-4" />
                </Button>
                <Button variant="ghost" size="icon-sm" onClick={() => openDelete(indexer)}>
                  <Trash2 className="size-4 text-destructive" />
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              <div className="text-sm text-zinc-400 space-y-1">
                <p>{t('indexers.url')}: <span className="text-zinc-200">{indexer.url}</span></p>
                {indexer.categories && (
                  <p>{t('indexers.categories')}: <span className="text-zinc-200">{indexer.categories}</span></p>
                )}
              </div>
            </CardContent>
          </Card>
        ))}

        {indexers.length === 0 && (
          <p className="text-zinc-500 text-center py-8">
            {t('indexers.noIndexers')}
          </p>
        )}
      </div>

      {/* Create / Edit Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="sm:max-w-lg bg-zinc-950 border-zinc-800">
          <DialogHeader>
            <DialogTitle className="text-zinc-100">
              {editingId !== null ? t('indexers.editTitle') : t('indexers.createTitle')}
            </DialogTitle>
          </DialogHeader>

          <Tabs defaultValue="general">
            <TabsList className="w-full">
              <TabsTrigger value="general">{t('indexers.tabGeneral')}</TabsTrigger>
              <TabsTrigger value="indexers">{t('indexers.tabIndexers')}</TabsTrigger>
            </TabsList>

            <TabsContent value="general">
              <div className="grid gap-4 py-2">
                <div className="grid gap-1.5">
                  <label className="text-sm font-medium text-zinc-300">
                    {t('indexers.name')}
                  </label>
                  <Input
                    value={form.name}
                    onChange={(e) => setForm({ ...form, name: e.target.value })}
                    placeholder={t('indexers.namePlaceholder')}
                    className="bg-zinc-900 border-zinc-700 text-zinc-100"
                  />
                </div>

                <div className="grid gap-1.5">
                  <label className="text-sm font-medium text-zinc-300">
                    {t('indexers.url')}
                  </label>
                  <Input
                    value={form.url}
                    onChange={(e) => setForm({ ...form, url: e.target.value })}
                    placeholder="http://prowlarr:9696"
                    className="bg-zinc-900 border-zinc-700 text-zinc-100"
                  />
                </div>

                <div className="grid gap-1.5">
                  <label className="text-sm font-medium text-zinc-300">
                    {t('indexers.apiKey')}
                  </label>
                  <div className="relative">
                    <Input
                      value={form.apiKey}
                      onChange={(e) => setForm({ ...form, apiKey: e.target.value })}
                      type={showApiKey ? 'text' : 'password'}
                      placeholder={t('indexers.apiKeyPlaceholder')}
                      className="bg-zinc-900 border-zinc-700 text-zinc-100 pr-10"
                    />
                    <button
                      type="button"
                      onClick={() => setShowApiKey(!showApiKey)}
                      className="absolute right-2 top-1/2 -translate-y-1/2 text-zinc-400 hover:text-zinc-200"
                    >
                      {showApiKey ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                    </button>
                  </div>
                </div>

                <div className="grid gap-1.5">
                  <label className="text-sm font-medium text-zinc-300">
                    {t('indexers.categories')}
                  </label>
                  <Input
                    value={form.categories}
                    onChange={(e) => setForm({ ...form, categories: e.target.value })}
                    placeholder={t('indexers.categoriesPlaceholder')}
                    className="bg-zinc-900 border-zinc-700 text-zinc-100"
                  />
                </div>

                <div className="flex items-center justify-between">
                  <label className="text-sm font-medium text-zinc-300">
                    {t('indexers.enabled')}
                  </label>
                  <Switch
                    checked={form.enabled}
                    onCheckedChange={(checked) => setForm({ ...form, enabled: checked === true })}
                  />
                </div>
              </div>
            </TabsContent>

            <TabsContent value="indexers">
              <div className="py-2 space-y-3">
                {detectedIndexers.length === 0 ? (
                  <div className="text-center py-6 space-y-3">
                    <p className="text-sm text-zinc-400">{t('indexers.testToDetect')}</p>
                    <Button
                      variant="outline"
                      onClick={handleTest}
                      disabled={testing}
                    >
                      {testing ? (
                        <Loader2 className="size-4 animate-spin" />
                      ) : (
                        <FlaskConical className="size-4" />
                      )}
                      {t('common.test')}
                    </Button>
                  </div>
                ) : (
                  <>
                    <p className="text-xs text-zinc-500">{t('indexers.indexersHint')}</p>
                    <div className="max-h-72 overflow-y-auto space-y-1">
                      {detectedIndexers.map((idx) => {
                        const enabled = isIndexerEnabled(idx.id)
                        const bookCats = idx.categories.filter((c) => c >= 7000 && c < 8000)
                        const selectedCats = getSelectedCategories(idx.id, bookCats)
                        const hasOverride = !!form.overrides[String(idx.id)]?.categories
                        return (
                          <div
                            key={idx.id}
                            className={`rounded px-3 py-2 border ${
                              enabled
                                ? 'border-zinc-800 bg-zinc-900/50'
                                : 'border-zinc-800/50 bg-zinc-900/20 opacity-60'
                            }`}
                          >
                            <div className="flex items-center justify-between">
                              <p className="text-sm font-medium text-zinc-200 truncate">{idx.name}</p>
                              <Switch
                                checked={enabled}
                                onCheckedChange={() => toggleOverrideEnabled(idx.id)}
                              />
                            </div>
                            <div className="flex flex-wrap gap-1 mt-1.5">
                              {bookCats.length > 0 ? (
                                bookCats.map((cat) => {
                                  const selected = selectedCats.has(cat)
                                  return (
                                    <Badge
                                      key={cat}
                                      variant={selected ? 'default' : 'outline'}
                                      className={`text-xs cursor-pointer select-none transition-opacity ${
                                        !selected ? 'opacity-40' : ''
                                      } ${!enabled ? 'pointer-events-none' : ''}`}
                                      onClick={() => enabled && toggleOverrideCategory(idx.id, cat)}
                                    >
                                      {cat}
                                    </Badge>
                                  )
                                })
                              ) : (
                                <span className="text-xs text-zinc-500">{t('indexers.noBookCategories')}</span>
                              )}
                              {hasOverride && (
                                <span className="text-[10px] text-zinc-600 ml-1 self-center">
                                  {t('indexers.customCategories')}
                                </span>
                              )}
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  </>
                )}
              </div>
            </TabsContent>
          </Tabs>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={handleTest}
              disabled={testing}
            >
              {testing ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <FlaskConical className="size-4" />
              )}
              {t('common.test')}
            </Button>
            <div className="flex-1" />
            <Button variant="outline" onClick={() => setDialogOpen(false)}>
              {t('common.cancel')}
            </Button>
            <Button
              onClick={handleSave}
              disabled={
                !form.name.trim() ||
                !form.url.trim() ||
                !form.apiKey.trim() ||
                createMutation.isPending ||
                updateMutation.isPending
              }
            >
              {t('common.save')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent className="sm:max-w-md bg-zinc-950 border-zinc-800">
          <DialogHeader>
            <DialogTitle className="text-zinc-100">
              {t('indexers.deleteTitle')}
            </DialogTitle>
          </DialogHeader>
          <p className="text-sm text-zinc-400">
            {t('indexers.deleteConfirm', { name: deletingIndexer?.name })}
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteDialogOpen(false)}>
              {t('common.cancel')}
            </Button>
            <Button
              variant="destructive"
              disabled={deleteMutation.isPending}
              onClick={() => deletingIndexer && deleteMutation.mutate(deletingIndexer.id)}
            >
              {t('common.delete')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
