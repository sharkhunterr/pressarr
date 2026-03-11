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
  type IndexerConfig,
  type ProwlarrIndexerInfo,
} from '@/api/downloads'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Switch } from '@/components/ui/switch'
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
}

function emptyForm(): IndexerFormState {
  return { name: '', url: '', apiKey: '', categories: '', enabled: true }
}

function indexerToForm(i: IndexerConfig): IndexerFormState {
  return {
    name: i.name,
    url: i.url,
    apiKey: i.apiKey ?? '',
    categories: i.categories,
    enabled: i.enabled,
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
  const [selectedCategories, setSelectedCategories] = useState<Set<number>>(new Set())

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
    setSelectedCategories(new Set())
    setDialogOpen(true)
  }

  function openEdit(indexer: IndexerConfig) {
    setEditingId(indexer.id)
    setForm(indexerToForm(indexer))
    setDetectedIndexers([])
    const existing = new Set(
      indexer.categories
        .split(',')
        .map((c) => parseInt(c.trim(), 10))
        .filter((n) => !isNaN(n)),
    )
    setSelectedCategories(existing)
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
    }
    if (editingId !== null) {
      updateMutation.mutate({ id: editingId, data: payload })
    } else {
      createMutation.mutate(payload)
    }
  }

  function toggleCategory(catId: number) {
    setSelectedCategories((prev) => {
      const next = new Set(prev)
      if (next.has(catId)) {
        next.delete(catId)
      } else {
        next.add(catId)
      }
      const sorted = [...next].sort((a, b) => a - b)
      setForm((f) => ({ ...f, categories: sorted.join(',') }))
      return next
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
          // Collect all unique categories from all indexers
          const allCats = new Set<number>()
          result.indexers.forEach((idx) => idx.categories.forEach((c) => allCats.add(c)))
          // If user has no categories set yet, pre-select book-related ones (7xxx)
          if (!form.categories.trim()) {
            const bookCats = [...allCats].filter((c) => c >= 7000 && c < 8000).sort((a, b) => a - b)
            setSelectedCategories(new Set(bookCats))
            setForm((f) => ({ ...f, categories: bookCats.join(',') }))
          } else {
            // Keep existing selection
            const existing = new Set(
              form.categories.split(',').map((c) => parseInt(c.trim(), 10)).filter((n) => !isNaN(n)),
            )
            setSelectedCategories(existing)
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
                placeholder="https://api.nzbindex.com"
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
                placeholder={t('indexers.apiKeyPlaceholder')}
                className="bg-zinc-900 border-zinc-700 text-zinc-100"
              />
            </div>

            <div className="grid gap-1.5">
              <label className="text-sm font-medium text-zinc-300">
                {t('indexers.categories')}
              </label>
              <Input
                value={form.categories}
                onChange={(e) => {
                  setForm({ ...form, categories: e.target.value })
                  const parsed = new Set(
                    e.target.value.split(',').map((c) => parseInt(c.trim(), 10)).filter((n) => !isNaN(n)),
                  )
                  setSelectedCategories(parsed)
                }}
                placeholder={t('indexers.categoriesPlaceholder')}
                className="bg-zinc-900 border-zinc-700 text-zinc-100"
              />
            </div>

            {/* Detected indexers with categories after test */}
            {detectedIndexers.length > 0 && (
              <div className="grid gap-2">
                <label className="text-sm font-medium text-zinc-300">
                  {t('indexers.detectedIndexers')}
                </label>
                <div className="max-h-48 overflow-y-auto space-y-2 rounded border border-zinc-800 p-2 bg-zinc-900/50">
                  {detectedIndexers.map((idx) => (
                    <div key={idx.id} className="space-y-1">
                      <p className="text-xs font-medium text-zinc-300">{idx.name}</p>
                      <div className="flex flex-wrap gap-1">
                        {idx.categories
                          .filter((c) => c >= 7000 && c < 8000)
                          .map((cat) => (
                            <Badge
                              key={cat}
                              variant={selectedCategories.has(cat) ? 'default' : 'outline'}
                              className="cursor-pointer text-xs"
                              onClick={() => toggleCategory(cat)}
                            >
                              {cat}
                            </Badge>
                          ))}
                        {idx.categories.filter((c) => c >= 7000 && c < 8000).length === 0 && (
                          <span className="text-xs text-zinc-500">{t('indexers.noBookCategories')}</span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
                <p className="text-xs text-zinc-500">{t('indexers.categoriesHint')}</p>
              </div>
            )}

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
