import { useState, useEffect, useMemo, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { useQueryClient } from '@tanstack/react-query'
import { Loader2, Undo2, Save, Wand2, FileText, AlertTriangle, Unlink } from 'lucide-react'
import { toast } from 'sonner'

import {
  type Issue,
  type IssueFile,
  updateIssue,
  reassignIssueFile,
  getUnassignedFiles,
  assignFileToIssue,
} from '@/api/issues'
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

const UNASSIGNED = '__none__'

interface PendingChange {
  targetIssueId?: number | null // null = unassign
  newFilename?: string
}

// A row in the file manager: either an issue-linked file or an unassigned file
interface FileRow {
  file: IssueFile
  issue: Issue | null // null for unassigned files
  originalIssueId: number | null
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
  const [unassignedFiles, setUnassignedFiles] = useState<IssueFile[]>([])

  // Fetch unassigned files and rename preview when modal opens
  useEffect(() => {
    if (open) {
      getUnassignedFiles(magazineId).then(setUnassignedFiles).catch(() => {})
      previewRename(magazineId).then(setRenamePreviewCache).catch(() => {})
      setPendingChanges(new Map())
    }
  }, [open, magazineId])

  // Build expected filename map from rename preview
  const expectedFilenames = useMemo(() => {
    const map = new Map<string, string>() // old_path → expected filename
    if (renamePreviewCache) {
      for (const p of renamePreviewCache) {
        map.set(p.old_path, p.new_path.split('/').pop() || '')
      }
    }
    return map
  }, [renamePreviewCache])

  // Build file rows: issues with files + unassigned files
  const fileRows = useMemo(() => {
    const rows: FileRow[] = []
    // Issues with files, sorted by date desc
    const sorted = issues
      .filter((i) => i.file != null)
      .sort((a, b) => (b.publicationDate ?? '').localeCompare(a.publicationDate ?? ''))
    for (const issue of sorted) {
      rows.push({ file: issue.file!, issue, originalIssueId: issue.id })
    }
    // Unassigned files
    for (const file of unassignedFiles) {
      rows.push({ file, issue: null, originalIssueId: null })
    }
    return rows
  }, [issues, unassignedFiles])

  // All issues for the select dropdown (sorted by date desc)
  const allIssues = useMemo(
    () => [...issues].sort((a, b) =>
      (b.publicationDate ?? '').localeCompare(a.publicationDate ?? ''),
    ),
    [issues],
  )

  const pendingCount = pendingChanges.size

  const invalidateAll = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ['issues', magazineId] })
    getUnassignedFiles(magazineId).then(setUnassignedFiles).catch(() => {})
  }, [queryClient, magazineId])

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

  async function handleAutoRename(row: FileRow) {
    const file = row.file
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
    const match = previews.find((p) => p.old_path === file.path)
    if (match) {
      const newFilename = match.new_path.split('/').pop() || ''
      const currentFilename = file.path.split('/').pop() || ''
      if (newFilename !== currentFilename) {
        const existing = pendingChanges.get(file.id) || {}
        setPending(file.id, { ...existing, newFilename })
      } else {
        toast.success(t('magazineDetail.renameNoChanges'))
      }
    }
  }

  async function saveFileChange(row: FileRow) {
    const file = row.file
    const change = pendingChanges.get(file.id)
    if (!change) return

    setSaving((prev) => new Set(prev).add(file.id))

    try {
      if (row.issue) {
        // Currently assigned to an issue
        if (change.targetIssueId === null) {
          // Unassign
          await reassignIssueFile(row.issue.id, null)
        } else if (change.targetIssueId && change.targetIssueId !== row.issue.id) {
          // Reassign to different issue
          await reassignIssueFile(row.issue.id, change.targetIssueId)
        }

        // Rename if needed
        if (change.newFilename) {
          const targetId = change.targetIssueId === null
            ? undefined
            : (change.targetIssueId || row.issue.id)
          if (targetId) {
            await updateIssue(targetId, { originalFilename: change.newFilename })
          }
        }
      } else {
        // Currently unassigned
        if (change.targetIssueId && change.targetIssueId !== null) {
          // Assign to an issue
          await assignFileToIssue(file.id, change.targetIssueId)

          // Rename if needed
          if (change.newFilename) {
            await updateIssue(change.targetIssueId, { originalFilename: change.newFilename })
          }
        }
      }

      clearPending(file.id)
      toast.success(t('magazineDetail.fileManagerSaved'))
      invalidateAll()
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
        next.delete(file.id)
        return next
      })
    }
  }

  async function handleSaveAll() {
    setSavingAll(true)
    for (const row of fileRows) {
      if (pendingChanges.has(row.file.id)) {
        await saveFileChange(row)
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
              — {magazineTitle} ({fileRows.length} files)
            </span>
          </DialogTitle>
        </DialogHeader>

        <div className="overflow-y-auto flex-1 space-y-2 pr-1">
          {fileRows.length === 0 ? (
            <p className="text-zinc-500 text-sm text-center py-8">
              {t('magazineDetail.fileManagerNoFiles')}
            </p>
          ) : (
            fileRows.map((row) => {
              const file = row.file
              const change = pendingChanges.get(file.id)
              const hasChanges = !!change
              const isSaving = saving.has(file.id)
              const currentFilename = file.path.split('/').pop() || ''
              const displayFilename = change?.newFilename || currentFilename

              // Determine selected issue in dropdown
              const selectedValue = change?.targetIssueId === null
                ? UNASSIGNED
                : change?.targetIssueId
                  ? String(change.targetIssueId)
                  : row.issue
                    ? String(row.issue.id)
                    : UNASSIGNED

              // Check mismatch with expected filename
              const expectedName = expectedFilenames.get(file.path)
              const hasMismatch = expectedName != null && expectedName !== currentFilename

              return (
                <div
                  key={file.id}
                  className={`rounded border p-3 space-y-2 transition-colors ${
                    hasChanges
                      ? 'border-l-2 border-l-emerald-500 border-zinc-700/50 bg-zinc-900/30'
                      : row.issue === null
                        ? 'border-l-2 border-l-amber-500 border-zinc-700/50 bg-zinc-900/20'
                        : 'border-zinc-800'
                  }`}
                >
                  {/* Line 1: Filename + badges */}
                  <div className="flex items-center gap-2 min-w-0">
                    {row.issue === null ? (
                      <Unlink className="size-3.5 text-amber-500 shrink-0" />
                    ) : (
                      <FileText className="size-3.5 text-zinc-500 shrink-0" />
                    )}
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
                      {hasMismatch && !hasChanges && (
                        <span
                          className="text-[10px] uppercase text-amber-400 bg-amber-900/30 px-1.5 py-0.5 rounded flex items-center gap-1"
                          title={t('magazineDetail.fileManagerMismatch')}
                        >
                          <AlertTriangle className="size-2.5" />
                          {t('magazineDetail.fileManagerMismatch')}
                        </span>
                      )}
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

                  {/* Line 2: Assigned issue + filename */}
                  <div className="flex flex-col sm:flex-row gap-2">
                    <div className="flex-1">
                      <label className="text-[10px] uppercase text-zinc-500 mb-1 block">
                        {t('magazineDetail.fileManagerAssignedTo')}
                      </label>
                      <Select
                        value={selectedValue}
                        onValueChange={(val) => {
                          if (val === UNASSIGNED) {
                            if (row.originalIssueId === null) {
                              // Was already unassigned — revert
                              const existing = pendingChanges.get(file.id)
                              if (existing) {
                                const { targetIssueId: _, ...rest } = existing
                                if (!rest.newFilename) clearPending(file.id)
                                else setPending(file.id, rest)
                              }
                            } else {
                              // Unassign from current issue
                              const existing = pendingChanges.get(file.id) || {}
                              setPending(file.id, { ...existing, targetIssueId: null })
                            }
                          } else {
                            const targetId = Number(val)
                            if (targetId === row.originalIssueId) {
                              // Reverted to original
                              const existing = pendingChanges.get(file.id)
                              if (existing) {
                                const { targetIssueId: _, ...rest } = existing
                                if (!rest.newFilename) clearPending(file.id)
                                else setPending(file.id, rest)
                              }
                            } else {
                              const existing = pendingChanges.get(file.id) || {}
                              setPending(file.id, { ...existing, targetIssueId: targetId })
                            }
                          }
                        }}
                      >
                        <SelectTrigger className="bg-zinc-900 border-zinc-700 text-zinc-100 h-8 text-xs">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value={UNASSIGNED}>
                            <span className="text-amber-400">
                              {t('magazineDetail.fileManagerNone')}
                            </span>
                          </SelectItem>
                          {allIssues.map((iss) => (
                            <SelectItem
                              key={iss.id}
                              value={String(iss.id)}
                              disabled={iss.file != null && iss.id !== row.originalIssueId}
                            >
                              <span className="flex items-center gap-1.5">
                                {issueLabel(iss)}
                                {iss.file != null && iss.id !== row.originalIssueId && (
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
                                if (rest.targetIssueId === undefined) clearPending(file.id)
                                else setPending(file.id, rest)
                              }
                            } else {
                              const existing = pendingChanges.get(file.id) || {}
                              setPending(file.id, { ...existing, newFilename: val })
                            }
                          }}
                          className="bg-zinc-900 border-zinc-700 text-zinc-100 h-8 text-xs font-mono flex-1"
                        />
                        {row.issue && (
                          <Button
                            variant="outline"
                            size="sm"
                            className="h-8 px-2"
                            onClick={() => handleAutoRename(row)}
                            title={t('magazineDetail.fileManagerAutoRename')}
                          >
                            <Wand2 className="size-3" />
                          </Button>
                        )}
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
                        onClick={() => saveFileChange(row)}
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
