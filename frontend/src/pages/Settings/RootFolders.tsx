import { useState, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Trash2, FolderOpen } from 'lucide-react'
import { toast } from 'sonner'

import {
  getRootFolders,
  createRootFolder,
  deleteRootFolder,
  type RootFolder,
} from '@/api/system'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { PathPicker } from '@/components/PathPicker'

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(1024))
  return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${units[i]}`
}

function spacePercent(free: number, total: number): number {
  if (total === 0) return 0
  return Math.round(((total - free) / total) * 100)
}

export default function RootFolders() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()

  const [addDialogOpen, setAddDialogOpen] = useState(false)
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const [deletingFolder, setDeletingFolder] = useState<RootFolder | null>(null)
  const [newPath, setNewPath] = useState('')

  const { data: folders = [], isLoading } = useQuery({
    queryKey: ['rootFolders'],
    queryFn: getRootFolders,
  })

  const invalidate = useCallback(
    () => queryClient.invalidateQueries({ queryKey: ['rootFolders'] }),
    [queryClient],
  )

  const createMutation = useMutation({
    mutationFn: (data: { path: string }) => createRootFolder(data),
    onSuccess: () => {
      invalidate()
      setAddDialogOpen(false)
      setNewPath('')
      toast.success(t('rootFolders.created'))
    },
    onError: () => toast.error(t('rootFolders.createError')),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteRootFolder(id),
    onSuccess: () => {
      invalidate()
      setDeleteDialogOpen(false)
      setDeletingFolder(null)
      setDeleteError(null)
      toast.success(t('rootFolders.deleted'))
    },
    onError: (err: unknown) => {
      const message = err instanceof Error ? err.message : ''
      if (message.includes('409') || message.includes('in use')) {
        setDeleteError(t('rootFolders.deleteInUse'))
      } else {
        toast.error(t('rootFolders.deleteError'))
      }
    },
  })

  function openAdd() {
    setNewPath('')
    setAddDialogOpen(true)
  }

  function openDelete(folder: RootFolder) {
    setDeletingFolder(folder)
    setDeleteError(null)
    setDeleteDialogOpen(true)
  }

  function handleAdd() {
    if (newPath.trim()) {
      createMutation.mutate({ path: newPath.trim() })
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
          {t('rootFolders.title')}
        </h1>
        <Button onClick={openAdd}>
          <Plus className="size-4" />
          {t('common.add')}
        </Button>
      </div>

      <div className="grid gap-4">
        {folders.map((folder) => {
          const usedPercent = spacePercent(folder.freeSpace, folder.totalSpace)
          const barColor = usedPercent > 90 ? 'bg-red-500' : usedPercent > 70 ? 'bg-yellow-500' : 'bg-[#7C3AED]'

          return (
            <Card key={folder.id} className="bg-zinc-950 border-zinc-800">
              <CardHeader className="flex-row items-center justify-between">
                <div className="flex items-center gap-3">
                  <FolderOpen className="size-5 text-[#7C3AED]" />
                  <CardTitle className="text-zinc-100 font-mono text-sm">
                    {folder.path}
                  </CardTitle>
                  {folder.isDefault && (
                    <Badge variant="secondary">{t('rootFolders.default')}</Badge>
                  )}
                </div>
                <Button variant="ghost" size="icon-sm" onClick={() => openDelete(folder)}>
                  <Trash2 className="size-4 text-destructive" />
                </Button>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  <div className="flex justify-between text-sm text-zinc-400">
                    <span>
                      {t('rootFolders.used')}: {formatBytes(folder.totalSpace - folder.freeSpace)}
                    </span>
                    <span>
                      {t('rootFolders.free')}: {formatBytes(folder.freeSpace)} / {formatBytes(folder.totalSpace)}
                    </span>
                  </div>
                  <div className="w-full h-2 bg-zinc-800 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all ${barColor}`}
                      style={{ width: `${usedPercent}%` }}
                    />
                  </div>
                </div>
              </CardContent>
            </Card>
          )
        })}

        {folders.length === 0 && (
          <p className="text-zinc-500 text-center py-8">
            {t('rootFolders.noFolders')}
          </p>
        )}
      </div>

      {/* Add Dialog */}
      <Dialog open={addDialogOpen} onOpenChange={setAddDialogOpen}>
        <DialogContent className="sm:max-w-lg bg-zinc-950 border-zinc-800">
          <DialogHeader>
            <DialogTitle className="text-zinc-100">
              {t('rootFolders.addTitle')}
            </DialogTitle>
          </DialogHeader>

          <div className="grid gap-4 py-2">
            <div className="grid gap-1.5">
              <label className="text-sm font-medium text-zinc-300">
                {t('rootFolders.path')}
              </label>
              {/* PathPicker : navigation dossiers + saisie manuelle en
                  fallback. Chaque dossier affiche son nombre d'items +
                  badges mount/RO pour choisir en connaissance de cause. */}
              <PathPicker
                value={newPath}
                onChange={setNewPath}
                disabled={createMutation.isPending}
                placeholder={t('rootFolders.pathPlaceholder')}
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setAddDialogOpen(false)}>
              {t('common.cancel')}
            </Button>
            <Button
              onClick={handleAdd}
              disabled={!newPath.trim() || createMutation.isPending}
            >
              {t('common.add')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent className="sm:max-w-md bg-zinc-950 border-zinc-800">
          <DialogHeader>
            <DialogTitle className="text-zinc-100">
              {t('rootFolders.deleteTitle')}
            </DialogTitle>
          </DialogHeader>
          <p className="text-sm text-zinc-400">
            {t('rootFolders.deleteConfirm', { path: deletingFolder?.path })}
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
              onClick={() => deletingFolder && deleteMutation.mutate(deletingFolder.id)}
            >
              {t('common.delete')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
