import { useState, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ArrowUp, ArrowDown, Plus, Trash2, Pencil } from 'lucide-react'

import {
  getProfiles,
  createProfile,
  updateProfile,
  deleteProfile,
  type QualityProfile,
  type QualityProfileItem,
} from '@/api/quality'
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

const QUALITIES = ['unknown', 'scan', 'pdf_lq', 'pdf_hq', 'retail', 'truepdf']

const QUALITY_LABELS: Record<string, string> = {
  unknown: 'Unknown',
  scan: 'Scan',
  pdf_lq: 'PDF (Low Quality)',
  pdf_hq: 'PDF (High Quality)',
  retail: 'Retail',
  truepdf: 'TruePDF',
}

function buildDefaultItems(): QualityProfileItem[] {
  return QUALITIES.map((q, i) => ({
    quality: q,
    allowed: true,
    sortOrder: i,
  }))
}

interface ProfileFormState {
  name: string
  cutoff: string
  isDefault: boolean
  items: QualityProfileItem[]
}

function emptyForm(): ProfileFormState {
  return {
    name: '',
    cutoff: 'pdf_hq',
    isDefault: false,
    items: buildDefaultItems(),
  }
}

function profileToForm(p: QualityProfile): ProfileFormState {
  return {
    name: p.name,
    cutoff: p.cutoff,
    isDefault: p.isDefault,
    items: [...p.items].sort((a, b) => a.sortOrder - b.sortOrder),
  }
}

export default function QualityProfiles() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()

  const [dialogOpen, setDialogOpen] = useState(false)
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [deletingProfile, setDeletingProfile] = useState<QualityProfile | null>(null)
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const [form, setForm] = useState<ProfileFormState>(emptyForm())

  const { data: profiles = [], isLoading } = useQuery({
    queryKey: ['qualityProfiles'],
    queryFn: getProfiles,
  })

  const invalidate = useCallback(
    () => queryClient.invalidateQueries({ queryKey: ['qualityProfiles'] }),
    [queryClient],
  )

  const createMutation = useMutation({
    mutationFn: (data: Partial<QualityProfile>) => createProfile(data),
    onSuccess: () => {
      invalidate()
      setDialogOpen(false)
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<QualityProfile> }) =>
      updateProfile(id, data),
    onSuccess: () => {
      invalidate()
      setDialogOpen(false)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteProfile(id),
    onSuccess: () => {
      invalidate()
      setDeleteDialogOpen(false)
      setDeletingProfile(null)
      setDeleteError(null)
    },
    onError: (err: unknown) => {
      const message =
        err instanceof Error ? err.message : 'Cannot delete profile'
      if (message.includes('409') || message.includes('in use')) {
        setDeleteError(
          t('qualityProfiles.deleteInUse', 'This profile is in use by one or more magazines and cannot be deleted.'),
        )
      } else {
        setDeleteError(message)
      }
    },
  })

  // ---------------------------------------------------------------------------
  // Form helpers
  // ---------------------------------------------------------------------------

  function openCreate() {
    setEditingId(null)
    setForm(emptyForm())
    setDialogOpen(true)
  }

  function openEdit(profile: QualityProfile) {
    setEditingId(profile.id)
    setForm(profileToForm(profile))
    setDialogOpen(true)
  }

  function openDelete(profile: QualityProfile) {
    setDeletingProfile(profile)
    setDeleteError(null)
    setDeleteDialogOpen(true)
  }

  function handleSave() {
    const payload: Partial<QualityProfile> = {
      name: form.name,
      cutoff: form.cutoff,
      isDefault: form.isDefault,
      items: form.items.map((item, i) => ({
        ...item,
        sortOrder: i,
      })),
    }
    if (editingId !== null) {
      updateMutation.mutate({ id: editingId, data: payload })
    } else {
      createMutation.mutate(payload)
    }
  }

  function moveItem(index: number, direction: -1 | 1) {
    const target = index + direction
    if (target < 0 || target >= form.items.length) return
    const newItems = [...form.items]
    const temp = newItems[index]
    newItems[index] = newItems[target]
    newItems[target] = temp
    setForm({ ...form, items: newItems })
  }

  function toggleAllowed(index: number) {
    const newItems = [...form.items]
    newItems[index] = { ...newItems[index], allowed: !newItems[index].allowed }
    setForm({ ...form, items: newItems })
  }

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

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
          {t('qualityProfiles.title', 'Quality Profiles')}
        </h1>
        <Button onClick={openCreate}>
          <Plus className="size-4" />
          {t('common.add')}
        </Button>
      </div>

      <div className="grid gap-4">
        {profiles.map((profile) => (
          <Card key={profile.id} className="bg-zinc-950 border-zinc-800">
            <CardHeader className="flex-row items-center justify-between">
              <div className="flex items-center gap-3">
                <CardTitle className="text-zinc-100">{profile.name}</CardTitle>
                {profile.isDefault && (
                  <Badge variant="secondary">
                    {t('qualityProfiles.default', 'Default')}
                  </Badge>
                )}
              </div>
              <div className="flex gap-2">
                <Button variant="ghost" size="icon-sm" onClick={() => openEdit(profile)}>
                  <Pencil className="size-4" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon-sm"
                  onClick={() => openDelete(profile)}
                >
                  <Trash2 className="size-4 text-destructive" />
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-2 mb-3">
                {[...profile.items]
                  .sort((a, b) => a.sortOrder - b.sortOrder)
                  .map((item) => (
                    <Badge
                      key={item.quality}
                      variant={item.allowed ? 'default' : 'outline'}
                      className={!item.allowed ? 'opacity-40' : ''}
                    >
                      {QUALITY_LABELS[item.quality] ?? item.quality}
                    </Badge>
                  ))}
              </div>
              <p className="text-sm text-zinc-400">
                {t('qualityProfiles.cutoff', 'Cutoff')}:{' '}
                <span className="text-zinc-200">
                  {QUALITY_LABELS[profile.cutoff] ?? profile.cutoff}
                </span>
              </p>
            </CardContent>
          </Card>
        ))}

        {profiles.length === 0 && (
          <p className="text-zinc-500 text-center py-8">
            {t('qualityProfiles.noProfiles', 'No quality profiles yet.')}
          </p>
        )}
      </div>

      {/* Create / Edit Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="sm:max-w-lg bg-zinc-950 border-zinc-800">
          <DialogHeader>
            <DialogTitle className="text-zinc-100">
              {editingId !== null
                ? t('qualityProfiles.editTitle', 'Edit Quality Profile')
                : t('qualityProfiles.createTitle', 'Create Quality Profile')}
            </DialogTitle>
          </DialogHeader>

          <div className="grid gap-4 py-2">
            {/* Name */}
            <div className="grid gap-1.5">
              <label className="text-sm font-medium text-zinc-300">
                {t('qualityProfiles.name', 'Name')}
              </label>
              <Input
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder={t('qualityProfiles.namePlaceholder', 'e.g. HD Quality')}
                className="bg-zinc-900 border-zinc-700 text-zinc-100"
              />
            </div>

            {/* Cutoff */}
            <div className="grid gap-1.5">
              <label className="text-sm font-medium text-zinc-300">
                {t('qualityProfiles.cutoff', 'Cutoff')}
              </label>
              <Select value={form.cutoff} onValueChange={(v) => setForm({ ...form, cutoff: v })}>
                <SelectTrigger className="bg-zinc-900 border-zinc-700 text-zinc-100 w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {QUALITIES.map((q) => (
                    <SelectItem key={q} value={q}>
                      {QUALITY_LABELS[q]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Default toggle */}
            <div className="flex items-center justify-between">
              <label className="text-sm font-medium text-zinc-300">
                {t('qualityProfiles.default', 'Default')}
              </label>
              <Switch
                checked={form.isDefault}
                onCheckedChange={(checked) =>
                  setForm({ ...form, isDefault: checked === true })
                }
              />
            </div>

            {/* Items list */}
            <div className="grid gap-1.5">
              <label className="text-sm font-medium text-zinc-300">
                {t('qualityProfiles.qualities', 'Qualities')}
              </label>
              <div className="rounded-md border border-zinc-800 divide-y divide-zinc-800">
                {form.items.map((item, idx) => (
                  <div
                    key={item.quality}
                    className="flex items-center gap-3 px-3 py-2"
                  >
                    <div className="flex flex-col gap-0.5">
                      <Button
                        variant="ghost"
                        size="icon-xs"
                        disabled={idx === 0}
                        onClick={() => moveItem(idx, -1)}
                      >
                        <ArrowUp className="size-3" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon-xs"
                        disabled={idx === form.items.length - 1}
                        onClick={() => moveItem(idx, 1)}
                      >
                        <ArrowDown className="size-3" />
                      </Button>
                    </div>
                    <span
                      className={`flex-1 text-sm ${item.allowed ? 'text-zinc-100' : 'text-zinc-500'}`}
                    >
                      {QUALITY_LABELS[item.quality] ?? item.quality}
                    </span>
                    <Switch
                      checked={item.allowed}
                      onCheckedChange={() => toggleAllowed(idx)}
                    />
                  </div>
                ))}
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>
              {t('common.cancel')}
            </Button>
            <Button
              onClick={handleSave}
              disabled={
                !form.name.trim() ||
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
              {t('qualityProfiles.deleteTitle', 'Delete Quality Profile')}
            </DialogTitle>
          </DialogHeader>
          <p className="text-sm text-zinc-400">
            {t(
              'qualityProfiles.deleteConfirm',
              'Are you sure you want to delete the profile "{{name}}"?',
              { name: deletingProfile?.name },
            )}
          </p>
          {deleteError && (
            <p className="text-sm text-destructive">{deleteError}</p>
          )}
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setDeleteDialogOpen(false)
                setDeleteError(null)
              }}
            >
              {t('common.cancel')}
            </Button>
            <Button
              variant="destructive"
              disabled={deleteMutation.isPending}
              onClick={() => deletingProfile && deleteMutation.mutate(deletingProfile.id)}
            >
              {t('common.delete')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
