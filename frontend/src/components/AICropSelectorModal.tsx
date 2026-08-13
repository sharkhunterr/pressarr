import { useEffect, useRef, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Loader2, Save, X, Trash2 } from 'lucide-react'
import { toast } from 'sonner'

import {
  getMagazineCrop,
  magazineCoverPreviewUrl,
  setMagazineCrop,
  type CropRect,
} from '@/api/ai'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'

/** Interactive rectangle selector on top of the magazine cover.
 *
 *  Coords are stored as RATIOS 0..1 of the underlying page so the
 *  crop stays valid across issues (which can have slightly different
 *  page sizes) and across viewport widths on the frontend.
 *
 *  Drag flow :
 *  - mousedown/touchstart on the image → set drag start
 *  - mousemove/touchmove → live rect preview
 *  - mouseup/touchend → commit rect (still in local state until Save)
 *  Existing saved rect renders as the initial preview.
 */
interface Props {
  open: boolean
  onClose: () => void
  magazineId: number
  magazineTitle: string
  onSaved?: (rect: CropRect | null) => void
}

export function AICropSelectorModal({
  open,
  onClose,
  magazineId,
  magazineTitle,
  onSaved,
}: Props) {
  const imgRef = useRef<HTMLImageElement>(null)
  const wrapRef = useRef<HTMLDivElement>(null)
  const [rect, setRect] = useState<CropRect | null>(null)
  const [dragging, setDragging] = useState<null | {
    startX: number
    startY: number
  }>(null)
  const [imgLoaded, setImgLoaded] = useState(false)

  const cropQ = useQuery({
    queryKey: ['ai-crop', magazineId],
    queryFn: () => getMagazineCrop(magazineId),
    enabled: open,
  })

  // Hydrate local rect from server value on mount / open.
  useEffect(() => {
    if (open && cropQ.data) {
      setRect(cropQ.data.rect)
      setImgLoaded(false)
    }
    if (!open) {
      setDragging(null)
    }
  }, [open, cropQ.data])

  function relPos(clientX: number, clientY: number): { x: number; y: number } | null {
    const el = imgRef.current
    if (!el) return null
    const b = el.getBoundingClientRect()
    if (b.width === 0 || b.height === 0) return null
    return {
      x: Math.max(0, Math.min(1, (clientX - b.left) / b.width)),
      y: Math.max(0, Math.min(1, (clientY - b.top) / b.height)),
    }
  }

  function handleDown(clientX: number, clientY: number) {
    const p = relPos(clientX, clientY)
    if (!p) return
    setDragging({ startX: p.x, startY: p.y })
    setRect({ x: p.x, y: p.y, w: 0, h: 0 })
  }
  function handleMove(clientX: number, clientY: number) {
    if (!dragging) return
    const p = relPos(clientX, clientY)
    if (!p) return
    const x = Math.min(dragging.startX, p.x)
    const y = Math.min(dragging.startY, p.y)
    const w = Math.abs(p.x - dragging.startX)
    const h = Math.abs(p.y - dragging.startY)
    setRect({ x, y, w, h })
  }
  function handleUp() {
    if (dragging && rect && (rect.w < 0.02 || rect.h < 0.02)) {
      // Trop petit → considéré comme un clic accidentel, on efface.
      setRect(null)
    }
    setDragging(null)
  }

  const saveMut = useMutation({
    mutationFn: () => setMagazineCrop(magazineId, rect),
    onSuccess: (res) => {
      toast.success(
        rect
          ? `Zone IA enregistrée pour ${magazineTitle}`
          : `Zone IA effacée pour ${magazineTitle}`,
      )
      onSaved?.(res.rect)
      onClose()
    },
    onError: (e: Error) => toast.error(`Échec : ${e.message}`),
  })

  const clearMut = useMutation({
    mutationFn: () => setMagazineCrop(magazineId, null),
    onSuccess: () => {
      setRect(null)
      toast.success('Zone IA effacée')
      onSaved?.(null)
    },
    onError: (e: Error) => toast.error(`Échec : ${e.message}`),
  })

  // Style pour l'overlay du rect (en % de l'image).
  const overlayStyle = rect
    ? {
        left: `${rect.x * 100}%`,
        top: `${rect.y * 100}%`,
        width: `${rect.w * 100}%`,
        height: `${rect.h * 100}%`,
      }
    : {}

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) onClose() }}>
      <DialogContent className="sm:max-w-3xl bg-zinc-950 border-zinc-800 max-h-[90vh] flex flex-col overflow-hidden">
        <DialogHeader>
          <DialogTitle className="text-zinc-100">
            Zone IA — {magazineTitle}
          </DialogTitle>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto space-y-3 pr-1">
          <p className="text-xs text-zinc-400">
            Trace un rectangle sur la couverture pour indiquer à l'IA
            vision où chercher le titre, le numéro et la date. Le
            rectangle sera appliqué à <strong>toutes les issues</strong>{' '}
            du magazine. Un clic simple efface la zone.
          </p>

          {cropQ.isLoading ? (
            <div className="flex items-center justify-center h-64">
              <Loader2 className="size-6 animate-spin text-zinc-500" />
            </div>
          ) : (
            <div
              ref={wrapRef}
              className="relative rounded border border-zinc-800 bg-zinc-900/40 overflow-hidden select-none"
              onMouseDown={(e) => handleDown(e.clientX, e.clientY)}
              onMouseMove={(e) => handleMove(e.clientX, e.clientY)}
              onMouseUp={handleUp}
              onMouseLeave={handleUp}
              onTouchStart={(e) => {
                if (e.touches.length !== 1) return
                const t = e.touches[0]
                handleDown(t.clientX, t.clientY)
              }}
              onTouchMove={(e) => {
                if (e.touches.length !== 1) return
                const t = e.touches[0]
                handleMove(t.clientX, t.clientY)
              }}
              onTouchEnd={handleUp}
              onDragStart={(e) => e.preventDefault()}
            >
              {!imgLoaded && (
                <div className="absolute inset-0 flex items-center justify-center text-zinc-500">
                  <Loader2 className="size-6 animate-spin" />
                </div>
              )}
              {open && (
                <img
                  ref={imgRef}
                  src={magazineCoverPreviewUrl(magazineId)}
                  alt="Couverture"
                  className="block max-w-full h-auto pointer-events-none"
                  style={{ userSelect: 'none' }}
                  onLoad={() => setImgLoaded(true)}
                  onError={() => {
                    setImgLoaded(true)
                    toast.error(
                      'Impossible de charger la couverture — le magazine doit avoir au moins une issue avec fichier',
                    )
                  }}
                />
              )}
              {rect && imgLoaded && (
                <div
                  className="absolute border-2 border-purple-400 bg-purple-500/20 pointer-events-none"
                  style={overlayStyle}
                >
                  <div className="absolute -top-6 left-0 text-[10px] px-1.5 py-0.5 rounded bg-purple-500 text-white font-mono whitespace-nowrap">
                    {(rect.w * 100).toFixed(0)} × {(rect.h * 100).toFixed(0)} %
                  </div>
                </div>
              )}
            </div>
          )}

          {rect && (
            <div className="text-xs text-zinc-500 font-mono">
              rect = x:{rect.x.toFixed(3)} y:{rect.y.toFixed(3)}{' '}
              w:{rect.w.toFixed(3)} h:{rect.h.toFixed(3)}
            </div>
          )}
        </div>

        <DialogFooter className="pt-4 border-t border-zinc-800 gap-2">
          <Button
            variant="outline"
            onClick={() => clearMut.mutate()}
            disabled={clearMut.isPending || (!rect && !cropQ.data?.rect)}
            className="text-destructive hover:text-destructive"
          >
            {clearMut.isPending ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <Trash2 className="size-4" />
            )}
            Effacer
          </Button>
          <div className="flex-1" />
          <Button variant="outline" onClick={onClose} disabled={saveMut.isPending}>
            <X className="size-4" />
            Annuler
          </Button>
          <Button
            onClick={() => saveMut.mutate()}
            disabled={saveMut.isPending || !rect}
          >
            {saveMut.isPending ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <Save className="size-4" />
            )}
            Enregistrer
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
