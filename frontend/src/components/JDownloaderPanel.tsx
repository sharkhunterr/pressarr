import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, FileText, Folder, Loader2, RefreshCw, Trash2, X } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

import {
  clearAllCrawljobs,
  deleteCompletedFolder,
  deleteCrawljob,
  getJDownloaderState,
} from '@/api/system'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'

// JDownloader 2 queue inspection — pressarr-side view of the
// shared folderwatch + output paths. No noVNC required:
// operator sees what's queued, what's downloaded, and can
// remove anything from this UI.

function formatBytes(b: number): string {
  if (b < 1024) return `${b} B`
  const units = ['B', 'KB', 'MB', 'GB']
  let i = 0
  let v = b
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024
    i += 1
  }
  return `${v.toFixed(1)} ${units[i]}`
}

function formatAge(ms: number): string {
  if (!ms) return '—'
  const diff = (Date.now() - ms) / 1000
  if (diff < 60) return `${Math.round(diff)}s`
  if (diff < 3600) return `${Math.round(diff / 60)}m`
  if (diff < 86400) return `${Math.round(diff / 3600)}h`
  return `${Math.round(diff / 86400)}d`
}

function hostFromUrl(url: string | null): string {
  if (!url) return '—'
  try {
    return new URL(url).hostname.replace(/^www\d?\./, '')
  } catch {
    return url.slice(0, 30)
  }
}

export default function JDownloaderPanel() {
  const queryClient = useQueryClient()
  const [busyName, setBusyName] = useState<string | null>(null)

  const { data, isLoading, refetch, isRefetching } = useQuery({
    queryKey: ['jdownloader-state'],
    queryFn: getJDownloaderState,
    refetchInterval: 5000, // poll every 5s — operator sees JD2 progress live
  })

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ['jdownloader-state'] })

  const removeMutation = useMutation({
    mutationFn: (filename: string) => deleteCrawljob(filename),
    onSuccess: (_, filename) => {
      toast.success(`Removed ${filename}`)
      invalidate()
    },
    onError: (e) => toast.error((e as Error).message),
    onSettled: () => setBusyName(null),
  })

  const clearAllMutation = useMutation({
    mutationFn: () => clearAllCrawljobs(),
    onSuccess: (d) => {
      toast.success(`Cleared ${d.deleted} queued crawljob(s)`)
      invalidate()
    },
    onError: (e) => toast.error((e as Error).message),
  })

  const removeFolderMutation = useMutation({
    mutationFn: (folderName: string) => deleteCompletedFolder(folderName),
    onSuccess: (_, name) => {
      toast.success(`Removed folder ${name}`)
      invalidate()
    },
    onError: (e) => toast.error((e as Error).message),
    onSettled: () => setBusyName(null),
  })

  if (isLoading || !data) {
    return (
      <div className="p-8 text-center text-zinc-400">
        <Loader2 className="mx-auto size-6 animate-spin" />
      </div>
    )
  }

  if (!data.enabled) {
    return (
      <div className="rounded-lg border border-dashed border-zinc-700 bg-zinc-900/40 p-6 text-center text-sm text-zinc-400">
        JDownloader 2 dispatcher is disabled. Enable it in{' '}
        <a
          href="/settings/indexers"
          className="text-indigo-400 hover:text-indigo-300"
        >
          Settings → Indexers
        </a>
        .
      </div>
    )
  }

  const pending = data.pendingJobs
  const completed = data.completedFolders

  return (
    <div className="space-y-6">
      {/* Header + refresh */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-xs text-zinc-400">
            folderwatch <code className="text-zinc-300">{data.folderwatchPath}</code>
            {' · '}
            output <code className="text-zinc-300">{data.outputPath}</code>
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => refetch()}
          disabled={isRefetching}
        >
          {isRefetching ? (
            <Loader2 className="size-3 animate-spin" />
          ) : (
            <RefreshCw className="size-3" />
          )}
          Refresh
        </Button>
      </div>

      {/* PENDING crawljobs */}
      <div className="rounded-lg border border-zinc-800 bg-zinc-900/40">
        <div className="flex items-center justify-between p-3 border-b border-zinc-800">
          <div className="flex items-center gap-2 text-sm font-semibold text-zinc-100">
            <FileText className="size-4" />
            Queued crawljobs
            <Badge variant="outline">{pending.length}</Badge>
          </div>
          {pending.length > 0 && (
            <Button
              variant="destructive"
              size="sm"
              onClick={() => clearAllMutation.mutate()}
              disabled={clearAllMutation.isPending}
            >
              {clearAllMutation.isPending ? (
                <Loader2 className="size-3 animate-spin" />
              ) : (
                <Trash2 className="size-3" />
              )}
              Clear all
            </Button>
          )}
        </div>
        {pending.length === 0 ? (
          <div className="p-6 text-center text-sm text-zinc-400">
            No crawljobs waiting. JD2 has ingested everything pressarr
            dispatched.
          </div>
        ) : (
          <ul className="divide-y divide-zinc-800">
            {pending.map((j) => (
              <li key={j.filename} className="p-3">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-medium text-zinc-100 truncate">
                      {j.packageName || j.filename}
                    </div>
                    <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-zinc-400">
                      <Badge variant="outline" className="text-[10px]">
                        {hostFromUrl(j.primaryUrl)}
                      </Badge>
                      {j.textUrlCount > 1 && (
                        <Badge variant="secondary" className="text-[10px]">
                          {j.textUrlCount} URLs (legacy)
                        </Badge>
                      )}
                      <span>queued {formatAge(j.writtenAtMs)} ago</span>
                      {j.releaseId && (
                        <span className="font-mono text-zinc-500">
                          release #{j.releaseId}
                        </span>
                      )}
                    </div>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      setBusyName(j.filename)
                      removeMutation.mutate(j.filename)
                    }}
                    disabled={busyName === j.filename}
                  >
                    {busyName === j.filename ? (
                      <Loader2 className="size-3 animate-spin" />
                    ) : (
                      <X className="size-3" />
                    )}
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* COMPLETED folders (downloaded by JD2, awaiting pressarr import
          OR already imported and leftover). */}
      <div className="rounded-lg border border-zinc-800 bg-zinc-900/40">
        <div className="flex items-center justify-between p-3 border-b border-zinc-800">
          <div className="flex items-center gap-2 text-sm font-semibold text-zinc-100">
            <Folder className="size-4" />
            Completed (JD2 output)
            <Badge variant="outline">{completed.length}</Badge>
          </div>
        </div>
        {completed.length === 0 ? (
          <div className="p-6 text-center text-sm text-zinc-400">
            JD2 hasn't produced any downloads yet.
          </div>
        ) : (
          <ul className="divide-y divide-zinc-800">
            {completed.map((f) => (
              <li key={f.folderName} className="p-3">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 text-sm font-medium text-zinc-100">
                      {f.folderName}
                      <CheckCircle2 className="size-3 text-emerald-400" />
                    </div>
                    <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-zinc-400">
                      <span>
                        {f.fileCount} file{f.fileCount > 1 ? 's' : ''}
                      </span>
                      <span>·</span>
                      <span>{formatBytes(f.totalSizeBytes)}</span>
                    </div>
                    {f.files.length > 0 && (
                      <ul className="mt-2 space-y-0.5">
                        {f.files.map((file) => (
                          <li
                            key={file.name}
                            className="text-xs text-zinc-500 flex items-center gap-2"
                          >
                            <span className="truncate">{file.name}</span>
                            {file.isPart && (
                              <Badge variant="secondary" className="text-[9px]">
                                in progress
                              </Badge>
                            )}
                            <span className="text-zinc-600 ml-auto">
                              {formatBytes(file.sizeBytes)}
                            </span>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      setBusyName(f.folderName)
                      removeFolderMutation.mutate(f.folderName)
                    }}
                    disabled={busyName === f.folderName}
                  >
                    {busyName === f.folderName ? (
                      <Loader2 className="size-3 animate-spin" />
                    ) : (
                      <Trash2 className="size-3" />
                    )}
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
