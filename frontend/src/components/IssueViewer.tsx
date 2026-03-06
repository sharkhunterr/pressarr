import { useState, useEffect, useCallback, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import { ChevronLeft, ChevronRight, Loader2, ZoomIn, ZoomOut, X, AlertTriangle } from 'lucide-react'

import { getIssuePageCount } from '@/api/issues'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
} from '@/components/ui/dialog'

async function fetchPageBlob(issueId: number, page: number): Promise<string> {
  const apiKey = localStorage.getItem('pressarr_api_key')
  const headers: Record<string, string> = {}
  if (apiKey) headers['X-Api-Key'] = apiKey

  const resp = await fetch(`/api/v1/issue/${issueId}/page/${page}`, { headers })
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
  const blob = await resp.blob()
  return URL.createObjectURL(blob)
}

interface IssueViewerProps {
  issueId: number | null
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function IssueViewer({ issueId, open, onOpenChange }: IssueViewerProps) {
  const { t } = useTranslation()
  const [page, setPage] = useState(0)
  const [zoom, setZoom] = useState(1)
  const [imgSrc, setImgSrc] = useState<string | null>(null)
  const [imgLoading, setImgLoading] = useState(false)
  const [imgError, setImgError] = useState<string | null>(null)
  const touchStartX = useRef<number | null>(null)

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

  // Fetch page image as blob (sends API key header)
  useEffect(() => {
    if (!open || issueId === null || !pageInfo) return
    let cancelled = false
    setImgLoading(true)
    setImgError(null)
    fetchPageBlob(issueId, page).then((url) => {
      if (!cancelled) {
        setImgSrc((prev) => { if (prev) URL.revokeObjectURL(prev); return url })
        setImgLoading(false)
      } else {
        URL.revokeObjectURL(url)
      }
    }).catch((err) => {
      if (!cancelled) {
        setImgSrc(null)
        setImgError(err.message || 'Failed to load')
        setImgLoading(false)
      }
    })
    return () => { cancelled = true }
  }, [open, issueId, page, pageInfo])

  // Cleanup blob URLs on close
  useEffect(() => {
    if (!open) {
      setImgSrc((prev) => { if (prev) URL.revokeObjectURL(prev); return null })
      setImgError(null)
    }
  }, [open])

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

  // Touch swipe for mobile navigation
  const handleTouchStart = useCallback((e: React.TouchEvent) => {
    if (zoom !== 1) return
    touchStartX.current = e.touches[0].clientX
  }, [zoom])

  const handleTouchEnd = useCallback((e: React.TouchEvent) => {
    if (touchStartX.current === null || zoom !== 1) return
    const diff = e.changedTouches[0].clientX - touchStartX.current
    touchStartX.current = null
    if (Math.abs(diff) < 50) return
    if (diff < 0) {
      // Swipe left → next page
      setPage((p) => Math.min((pageInfo?.pageCount ?? 1) - 1, p + 1))
    } else {
      // Swipe right → previous page
      setPage((p) => Math.max(0, p - 1))
    }
  }, [zoom, pageInfo])

  const totalPages = pageInfo?.pageCount ?? 0

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent showCloseButton={false} className="fixed inset-2 sm:inset-4 !translate-x-0 !translate-y-0 !top-auto !left-auto !max-w-none w-auto h-auto p-0 bg-zinc-950 border-zinc-800 flex flex-col overflow-hidden">
        {/* Toolbar */}
        <div className="flex items-center justify-between px-2 sm:px-4 py-1.5 sm:py-2 border-b border-zinc-800 shrink-0 gap-1">
          <div className="flex items-center gap-1 sm:gap-2">
            <Button
              variant="ghost"
              size="icon-sm"
              onClick={() => goTo(page - 1)}
              disabled={page === 0}
            >
              <ChevronLeft className="size-4" />
            </Button>
            <span className="text-xs sm:text-sm text-zinc-300 min-w-[50px] sm:min-w-[80px] text-center tabular-nums">
              {totalPages > 0 ? `${page + 1}/${totalPages}` : '-'}
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

          <div className="flex items-center gap-0.5 sm:gap-1">
            <Button variant="ghost" size="icon-sm" onClick={() => setZoom((z) => Math.max(0.25, z - 0.25))} className="hidden sm:inline-flex">
              <ZoomOut className="size-4" />
            </Button>
            <span className="text-[10px] sm:text-xs text-zinc-400 min-w-[28px] sm:min-w-[40px] text-center hidden sm:inline">{Math.round(zoom * 100)}%</span>
            <Button variant="ghost" size="icon-sm" onClick={() => setZoom((z) => Math.min(3, z + 0.25))} className="hidden sm:inline-flex">
              <ZoomIn className="size-4" />
            </Button>
            <Button variant="ghost" size="icon-sm" onClick={() => setZoom(1)} title="Reset zoom" className="hidden sm:inline-flex">
              <span className="text-xs">1:1</span>
            </Button>
            <Button variant="ghost" size="icon-sm" onClick={() => onOpenChange(false)}>
              <X className="size-4" />
            </Button>
          </div>
        </div>

        {/* Content */}
        <div
          className="flex-1 overflow-auto flex items-start justify-center bg-zinc-900/50"
          onTouchStart={handleTouchStart}
          onTouchEnd={handleTouchEnd}
        >
          {(isLoading || imgLoading) && (
            <div className="flex items-center justify-center h-full">
              <Loader2 className="size-8 animate-spin text-[#7C3AED]" />
            </div>
          )}
          {error && !imgLoading && (
            <div className="flex flex-col items-center justify-center h-full gap-2 px-4">
              <AlertTriangle className="size-6 text-red-400" />
              <p className="text-red-400 text-sm text-center">{t('viewer.error')}</p>
            </div>
          )}
          {imgError && !imgLoading && !error && (
            <div className="flex flex-col items-center justify-center h-full gap-2 px-4">
              <AlertTriangle className="size-6 text-red-400" />
              <p className="text-red-400 text-sm text-center">{t('viewer.pageError')}</p>
              <Button variant="outline" size="sm" onClick={() => { setImgError(null); setImgLoading(true); fetchPageBlob(issueId!, page).then((url) => { setImgSrc((prev) => { if (prev) URL.revokeObjectURL(prev); return url }); setImgLoading(false) }).catch(() => { setImgError('retry failed'); setImgLoading(false) }) }}>
                {t('viewer.retry')}
              </Button>
            </div>
          )}
          {imgSrc && !imgLoading && (
            <img
              key={`${issueId}-${page}`}
              src={imgSrc}
              alt={`Page ${page + 1}`}
              className={zoom === 1 ? 'max-w-full max-h-full object-contain' : 'max-w-none'}
              style={zoom !== 1 ? { transform: `scale(${zoom})`, transformOrigin: 'top center' } : undefined}
              draggable={false}
            />
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
