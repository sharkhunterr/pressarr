import { useState, useMemo, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { useQueryClient } from '@tanstack/react-query'
import { Loader2, Undo2, Save, Wand2, FileText } from 'lucide-react'
import { toast } from 'sonner'

import { type Issue, updateIssue, reassignIssueFile } from '@/api/issues'
import { previewRename, type RenamePreview } from '@/api/magazines'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
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

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(1024))
  return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${units[i]}`
}

function issueLabel(issue: Issue): string {
  const parts: string[] = []
  if (issue.number != null) parts.push(`#${issue.number}`)
  if (issue.year) {
    let d = `${issue.year}`
    if (issue.month) d += `-${String(issue.month).padStart(2, '0')}`
    if (issue.day) d += `-${String(issue.day).padStart(2, '0')}`
    parts.push(d)
  }
  if (issue.title) parts.push(issue.title)
  if (parts.length === 0) return `ID ${issue.id}`
  return parts.join(' — ')
}

interface PendingChange {
  targetIssueId?: number
  newFilename?: string
}

interface FileManagerModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  magazineId: number
  issues: Issue[]
  magazineTitle: string
}

export function FileManagerModal({
  open,
  onOpenChange,
  magazineId,
  issues,
  magazineTitle,
}: FileManagerModalProps) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()

  const [pendingChanges, setPendingChanges] = useState<Map<number, PendingChange>>(new Map())
  const [saving, setSaving] = useState<Set<number>>(new Set())
  const [savingAll, setSavingAll] = useState(false)
  const [renamePreviewCache, setRenamePreviewCache] = useState<RenamePreview[] | null>(null)

  // Issues with files, sorted by date desc
  const issuesWithFiles = useMemo(
    () => issues.filter((i) => i.file != null).sort((a, b) => {
      const da = a.publicationDate ?? ''
      const db2 = b.publicationDate ?? ''
      return db2.localeCompare(da)
    }),
    [issues],
  )

  // All issues for the select dropdown (sorted by date desc)
  const allIssues = useMemo(
    () => [...issues].sort((a, b) => {
      const da = a.publicationDate ?? ''
      const db2 = b.publicationDate ?? ''
      return db2.localeCompare(da)
    }),
    [issues],
  )

  const pendingCount = pendingChanges.size

  const invalidateIssues = useCallback(
    () => queryClient.invalidateQueries({ queryKey: ['issues', magazineId] }),
    [queryClient, magazineId],
  )

  function setPending(fileId: number, change: PendingChange) {
    setPendingChanges((prev) => {
      const next = new Map(prev)
      next.set(fileId, change)
      return next
    })
  }

  function clearPending(fileId: number) {
    setPendingChanges((prev) => {
      const next = new Map(prev)
      next.delete(fileId)
      return next
    })
  }

  async function handleAutoRename(issue: Issue) {
    if (!issue.file) return
    let previews = renamePreviewCache
    if (!previews) {
      try {
        previews = await previewRename(magazineId)
        setRenamePreviewCache(previews)
      } catch {
        toast.error(t('magazineDetail.renameError'))
        return
      }
    }
    const match = previews.find((p) => p.old_path === issue.file!.path)
    if (match) {
      const newFilename = match.new_path.split('/').pop() || ''
      const currentFilename = issue.file.path.split('/').pop() || ''
      if (newFilename !== currentFilename) {
        const existing = pendingChanges.get(issue.file.id) || {}
        setPending(issue.file.id, { ...existing, newFilename })
      } else {
        toast.success(t('magazineDetail.renameNoChanges'))
      }
    }
  }

  async function saveFileChange(issue: Issue) {
    if (!issue.file) return
    const change = pendingChanges.get(issue.file.id)
    if (!change) return

    setSaving((prev) => new Set(prev).add(issue.file!.id))

    try {
      // Reassign first if needed
      if (change.targetIssueId && change.targetIssueId !== issue.id) {
        await reassignIssueFile(issue.id, change.targetIssueId)
      }

      // Rename if needed
      if (change.newFilename) {
        const targetId = change.targetIssueId || issue.id
        await updateIssue(targetId, { originalFilename: change.newFilename })
      }

      clearPending(issue.file.id)
      toast.success(t('magazineDetail.fileManagerSaved'))
      invalidateIssues()
    } catch (err) {
      const msg = err instanceof Error ? err.message : ''
      if (msg.includes('409') || msg.includes('already')) {
        toast.error(t('magazineDetail.fileManagerReassignError'))
      } else {
        toast.error(t('magazineDetail.fileManagerRenameError'))
      }
    } finally {
      setSaving((prev) => {
        const next = new Set(prev)
        next.delete(issue.file!.id)
        return next
      })
    }
  }

  async function handleSaveAll() {
    setSavingAll(true)
    for (const issue of issuesWithFiles) {
      if (issue.file && pendingChanges.has(issue.file.id)) {
        await saveFileChange(issue)
      }
    }
    setSavingAll(false)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-4xl bg-zinc-950 border-zinc-800 max-h-[85vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle className="text-zinc-100">
            {t('magazineDetail.fileManagerTitle')}
            <span className="text-zinc-500 font-normal text-sm ml-2">
              — {magazineTitle} ({issuesWithFiles.length} files)
            </span>
          </DialogTitle>
        </DialogHeader>

        <div className="overflow-y-auto flex-1 space-y-2 pr-1">
          {issuesWithFiles.length === 0 ? (
            <p className="text-zinc-500 text-sm text-center py-8">
              {t('magazineDetail.fileManagerNoFiles')}
            </p>
          ) : (
            issuesWithFiles.map((issue) => {
              const file = issue.file!
              const change = pendingChanges.get(file.id)
              const hasChanges = !!change
              const isSaving = saving.has(file.id)
              const currentFilename = file.path.split('/').pop() || ''
              const displayFilename = change?.newFilename || currentFilename
              const selectedIssueId = change?.targetIssueId || issue.id

              return (
                <div
                  key={file.id}
                  className={`rounded border p-3 space-y-2 transition-colors ${
                    hasChanges
                      ? 'border-l-2 border-l-emerald-500 border-zinc-700/50 bg-zinc-900/30'
                      : 'border-zinc-800'
                  }`}
                >
                  {/* Line 1: Filename + badges */}
                  <div className="flex items-center gap-2 min-w-0">
                    <FileText className="size-3.5 text-zinc-500 shrink-0" />
                    <span className="font-mono text-xs text-zinc-200 truncate flex-1">
                      {hasChanges && change?.newFilename ? (
                        <>
                          <span className="line-through text-zinc-500">{currentFilename}</span>
                          {' → '}
                          <span className="text-emerald-400">{change.newFilename}</span>
                        </>
                      ) : (
                        currentFilename
                      )}
                    </span>
                    <div className="flex items-center gap-1.5 shrink-0">
                      <span className="text-[10px] uppercase text-zinc-500 bg-zinc-800 px-1.5 py-0.5 rounded">
                        {file.format}
                      </span>
                      {file.quality && file.quality !== 'unknown' && (
                        <span className="text-[10px] uppercase text-zinc-500 bg-zinc-800 px-1.5 py-0.5 rounded">
                          {file.quality}
                        </span>
                      )}
                      <span className="text-[10px] text-zinc-600">
                        {formatBytes(file.size)}
                      </span>
                    </div>
                  </div>

                  {/* Line 2: Current issue + reassign select */}
                  <div className="flex flex-col sm:flex-row gap-2">
                    <div className="flex-1">
                      <label className="text-[10px] uppercase text-zinc-500 mb-1 block">
                        {t('magazineDetail.fileManagerAssignedTo')}
                      </label>
                      <Select
                        value={String(selectedIssueId)}
                        onValueChange={(val) => {
                          const targetId = Number(val)
                          if (targetId === issue.id) {
                            // Reverted to original
                            const existing = pendingChanges.get(file.id)
                            if (existing) {
                              const { targetIssueId: _, ...rest } = existing
                              if (Object.keys(rest).length === 0 || (!rest.newFilename)) {
                                clearPending(file.id)
                              } else {
                                setPending(file.id, rest)
                              }
                            }
                          } else {
                            const existing = pendingChanges.get(file.id) || {}
                            setPending(file.id, { ...existing, targetIssueId: targetId })
                          }
                        }}
                      >
                        <SelectTrigger className="bg-zinc-900 border-zinc-700 text-zinc-100 h-8 text-xs">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {allIssues.map((iss) => (
                            <SelectItem
                              key={iss.id}
                              value={String(iss.id)}
                              disabled={iss.file != null && iss.id !== issue.id}
                            >
                              <span className="flex items-center gap-1.5">
                                {issueLabel(iss)}
                                {iss.file != null && iss.id !== issue.id && (
                                  <span className="text-[10px] text-zinc-500">
                                    ({t('magazineDetail.fileManagerIssueHasFile')})
                                  </span>
                                )}
                              </span>
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>

                    <div className="flex-1">
                      <label className="text-[10px] uppercase text-zinc-500 mb-1 block">
                        {t('magazineDetail.fileManagerFilename')}
                      </label>
                      <div className="flex gap-1">
                        <Input
                          value={displayFilename}
                          onChange={(e) => {
                            const val = e.target.value
                            if (val === currentFilename) {
                              const existing = pendingChanges.get(file.id)
                              if (existing) {
                                const { newFilename: _, ...rest } = existing
                                if (!rest.targetIssueId) {
                                  clearPending(file.id)
                                } else {
                                  setPending(file.id, rest)
                                }
                              }
                            } else {
                              const existing = pendingChanges.get(file.id) || {}
                              setPending(file.id, { ...existing, newFilename: val })
                            }
                          }}
                          className="bg-zinc-900 border-zinc-700 text-zinc-100 h-8 text-xs font-mono flex-1"
                        />
                        <Button
                          variant="outline"
                          size="sm"
                          className="h-8 px-2"
                          onClick={() => handleAutoRename(issue)}
                          title={t('magazineDetail.fileManagerAutoRename')}
                        >
                          <Wand2 className="size-3" />
                        </Button>
                      </div>
                    </div>
                  </div>

                  {/* Line 3: Actions */}
                  {hasChanges && (
                    <div className="flex justify-end gap-1.5">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 text-xs"
                        onClick={() => clearPending(file.id)}
                        disabled={isSaving}
                      >
                        <Undo2 className="size-3 mr-1" />
                        {t('magazineDetail.fileManagerUndo')}
                      </Button>
                      <Button
                        size="sm"
                        className="h-7 text-xs"
                        onClick={() => saveFileChange(issue)}
                        disabled={isSaving}
                      >
                        {isSaving ? (
                          <Loader2 className="size-3 animate-spin mr-1" />
                        ) : (
                          <Save className="size-3 mr-1" />
                        )}
                        {t('magazineDetail.fileManagerSave')}
                      </Button>
                    </div>
                  )}
                </div>
              )
            })
          )}
        </div>

        <DialogFooter>
          <div className="flex items-center gap-2 mr-auto">
            {pendingCount > 0 && (
              <span className="text-xs text-emerald-400">
                {t('magazineDetail.fileManagerUnsavedChanges', { count: pendingCount })}
              </span>
            )}
          </div>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            {t('common.cancel')}
          </Button>
          <Button
            onClick={handleSaveAll}
            disabled={pendingCount === 0 || savingAll}
          >
            {savingAll ? (
              <Loader2 className="size-3.5 animate-spin mr-1" />
            ) : (
              <Save className="size-3.5 mr-1" />
            )}
            {t('magazineDetail.fileManagerSaveAll')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
