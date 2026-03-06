import { useState, useEffect, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import { ChevronLeft, ChevronRight, Loader2, ZoomIn, ZoomOut, X } from 'lucide-react'

import { getIssuePageCount, getIssuePageUrl } from '@/api/issues'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
} from '@/components/ui/dialog'

interface IssueViewerProps {
  issueId: number | null
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function IssueViewer({ issueId, open, onOpenChange }: IssueViewerProps) {
  const { t } = useTranslation()
  const [page, setPage] = useState(0)
  const [zoom, setZoom] = useState(1)

  const { data: pageInfo, isLoading, error } = useQuery({
    queryKey: ['issue-pages', issueId],
    queryFn: () => getIssuePageCount(issueId!),
    enabled: open && issueId !== null,
  })

  // Reset page when opening a new issue
  useEffect(() => {
    if (open) {
      setPage(0)
      setZoom(1)
    }
  }, [open, issueId])

  // Keyboard navigation
  useEffect(() => {
    if (!open) return
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
        e.preventDefault()
        setPage((p) => Math.max(0, p - 1))
      } else if (e.key === 'ArrowRight' || e.key === 'ArrowDown' || e.key === ' ') {
        e.preventDefault()
        setPage((p) => Math.min((pageInfo?.pageCount ?? 1) - 1, p + 1))
      } else if (e.key === 'Escape') {
        onOpenChange(false)
      } else if (e.key === '+' || e.key === '=') {
        setZoom((z) => Math.min(3, z + 0.25))
      } else if (e.key === '-') {
        setZoom((z) => Math.max(0.25, z - 0.25))
      } else if (e.key === '0') {
        setZoom(1)
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [open, pageInfo, onOpenChange])

  const goTo = useCallback((p: number) => {
    if (pageInfo) setPage(Math.max(0, Math.min(pageInfo.pageCount - 1, p)))
  }, [pageInfo])

  const totalPages = pageInfo?.pageCount ?? 0

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-[95vw] max-h-[95vh] w-auto h-[95vh] p-0 bg-zinc-950 border-zinc-800 flex flex-col overflow-hidden">
        {/* Toolbar */}
        <div className="flex items-center justify-between px-4 py-2 border-b border-zinc-800 shrink-0">
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="icon-sm"
              onClick={() => goTo(page - 1)}
              disabled={page === 0}
            >
              <ChevronLeft className="size-4" />
            </Button>
            <span className="text-sm text-zinc-300 min-w-[80px] text-center">
              {totalPages > 0 ? `${page + 1} / ${totalPages}` : '-'}
            </span>
            <Button
              variant="ghost"
              size="icon-sm"
              onClick={() => goTo(page + 1)}
              disabled={page >= totalPages - 1}
            >
              <ChevronRight className="size-4" />
            </Button>
          </div>

          <div className="flex items-center gap-1">
            <Button variant="ghost" size="icon-sm" onClick={() => setZoom((z) => Math.max(0.25, z - 0.25))}>
              <ZoomOut className="size-4" />
            </Button>
            <span className="text-xs text-zinc-400 min-w-[40px] text-center">{Math.round(zoom * 100)}%</span>
            <Button variant="ghost" size="icon-sm" onClick={() => setZoom((z) => Math.min(3, z + 0.25))}>
              <ZoomIn className="size-4" />
            </Button>
            <Button variant="ghost" size="icon-sm" onClick={() => setZoom(1)} title="Reset zoom">
              <span className="text-xs">1:1</span>
            </Button>
            <Button variant="ghost" size="icon-sm" onClick={() => onOpenChange(false)}>
              <X className="size-4" />
            </Button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-auto flex items-start justify-center bg-zinc-900/50">
          {isLoading && (
            <div className="flex items-center justify-center h-full">
              <Loader2 className="size-8 animate-spin text-[#7C3AED]" />
            </div>
          )}
          {error && (
            <div className="flex items-center justify-center h-full">
              <p className="text-red-400 text-sm">{t('viewer.error')}</p>
            </div>
          )}
          {pageInfo && issueId !== null && (
            <img
              key={`${issueId}-${page}`}
              src={getIssuePageUrl(issueId, page)}
              alt={`Page ${page + 1}`}
              className="max-w-none"
              style={{ transform: `scale(${zoom})`, transformOrigin: 'top center' }}
              draggable={false}
            />
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
