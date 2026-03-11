import { useState, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Pencil, Trash2, FlaskConical, Loader2 } from 'lucide-react'
import { toast } from 'sonner'

import {
  getIndexers,
  createIndexer,
  updateIndexer,
  deleteIndexer,
  testIndexer,
  testIndexerById,
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
    apiKey: '',
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
    setDialogOpen(true)
  }

  function openEdit(indexer: IndexerConfig) {
    setEditingId(indexer.id)
    setForm(indexerToForm(indexer))
    setDetectedIndexers([])
    setDialogOpen(true)
  }

  function openDelete(indexer: IndexerConfig) {
    setDeletingIndexer(indexer)
    setDeleteDialogOpen(true)
  }

  function handleSave() {
    const payload: Record<string, unknown> = {
      name: form.name,
      url: form.url,
      categories: form.categories,
      enabled: form.enabled,
      indexerOverrides: form.overrides,
    }
    // Only send apiKey if user entered one (otherwise keep existing)
    if (form.apiKey.trim()) {
      payload.apiKey = form.apiKey
    }
    if (editingId !== null) {
      updateMutation.mutate({ id: editingId, data: payload as Partial<IndexerConfig> & { apiKey?: string } })
    } else {
      payload.apiKey = form.apiKey
      createMutation.mutate(payload as Partial<IndexerConfig> & { apiKey: string })
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

  async function handleTest() {
    setTesting(true)
    try {
      let result
      if (editingId !== null && !form.apiKey.trim()) {
        // Use stored API key via test-by-id
        result = await testIndexerById(editingId)
      } else if (form.url && form.apiKey) {
        result = await testIndexer({ url: form.url, apiKey: form.apiKey })
      } else {
        toast.error(t('indexers.testMissingFields'))
        setTesting(false)
        return
      }

      if (result.isValid) {
        toast.success(t('indexers.testSuccess'))
        if (result.indexers && result.indexers.length > 0) {
          setDetectedIndexers(result.indexers)
          // If no categories set yet, pre-select book-related ones
          if (!form.categories.trim()) {
            const allCats = new Set<number>()
            result.indexers.forEach((idx) => idx.categories.forEach((c) => allCats.add(c)))
            const bookCats = [...allCats].filter((c) => c >= 7000 && c < 8000).sort((a, b) => a - b)
            setForm((f) => ({ ...f, categories: bookCats.join(',') }))
          }
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
                  <Input
                    value={form.apiKey}
                    onChange={(e) => setForm({ ...form, apiKey: e.target.value })}
                    type="password"
                    placeholder={editingId !== null ? t('indexers.apiKeyKeep') : t('indexers.apiKeyPlaceholder')}
                    className="bg-zinc-900 border-zinc-700 text-zinc-100"
                  />
                  {editingId !== null && (
                    <p className="text-xs text-zinc-500">{t('indexers.apiKeyKeepHint')}</p>
                  )}
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
                    <div className="max-h-64 overflow-y-auto space-y-1">
                      {detectedIndexers.map((idx) => {
                        const enabled = isIndexerEnabled(idx.id)
                        const bookCats = idx.categories.filter((c) => c >= 7000 && c < 8000)
                        return (
                          <div
                            key={idx.id}
                            className={`flex items-center justify-between rounded px-3 py-2 border ${
                              enabled
                                ? 'border-zinc-800 bg-zinc-900/50'
                                : 'border-zinc-800/50 bg-zinc-900/20 opacity-60'
                            }`}
                          >
                            <div className="flex-1 min-w-0">
                              <p className="text-sm font-medium text-zinc-200 truncate">{idx.name}</p>
                              <div className="flex flex-wrap gap-1 mt-1">
                                {bookCats.length > 0 ? (
                                  bookCats.map((cat) => (
                                    <Badge key={cat} variant="outline" className="text-xs">
                                      {cat}
                                    </Badge>
                                  ))
                                ) : (
                                  <span className="text-xs text-zinc-500">{t('indexers.noBookCategories')}</span>
                                )}
                              </div>
                            </div>
                            <Switch
                              checked={enabled}
                              onCheckedChange={() => toggleOverrideEnabled(idx.id)}
                            />
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
                (editingId === null && !form.apiKey.trim()) ||
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
