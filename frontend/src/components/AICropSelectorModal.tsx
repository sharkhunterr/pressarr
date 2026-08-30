import { useEffect, useMemo, useRef, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import {
  Hand,
  Loader2,
  Maximize2,
  MousePointer2,
  Plus,
  RotateCw,
  Save,
  SquareDashed,
  Trash2,
  X,
  ZoomIn,
  ZoomOut,
} from 'lucide-react'
import { toast } from 'sonner'

import {
  getMagazineCrop,
  setMagazineCropByType,
  type IssueType,
  issueCoverPreviewUrl,
  magazineCoverPreviewUrl,
  type CropZone,
} from '@/api/ai'
import { getIssues, type Issue } from '@/api/issues'
import { getMagazine } from '@/api/magazines'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'

/** Multi-zone crop editor avec zoom + pan.
 *
 *  Coords stored as ratios 0..1 of the underlying page (never
 *  depend on viewport size). Trois modes explicites :
 *  - **draw** (défaut) : cliquer-glisser sur zone vide crée un
 *    rectangle. Cliquer sur une zone existante la sélectionne.
 *  - **select** : cliquer sélectionne, drag déplace la zone.
 *  - **pan** : drag déplace la vue (utile quand zoomé).
 *
 *  Zoom : molette (autour du curseur) + boutons + / - + fit. Range
 *  0.25× à 8×. La touche « Espace » bascule temporairement en pan
 *  tant qu'elle est tenue.
 */
interface Props {
  open: boolean
  onClose: () => void
  magazineId: number
  magazineTitle: string
  onSaved?: (zones: CropZone[]) => void
}

const ROTATIONS = [0, 90, 180, 270] as const

const ZONE_TAGS: Array<{
  value: 'number' | 'date' | 'title' | 'subtitle' | 'price' | 'publisher' | 'issn' | 'all' | 'custom'
  label: string
  hint: string
}> = [
  { value: 'all',       label: 'Tout',       hint: 'OCR exhaustif — lit tout ce qui est visible' },
  { value: 'number',    label: 'N°',         hint: 'Uniquement le numéro d\'édition' },
  { value: 'date',      label: 'Date',       hint: 'Uniquement la date de publication' },
  { value: 'title',     label: 'Titre',      hint: 'Uniquement le titre principal (logo/masthead)' },
  { value: 'subtitle',  label: 'Sous-titre', hint: 'Sous-titre / accroche éditoriale' },
  { value: 'price',     label: 'Prix',       hint: 'Prix + mentions tarifaires étrangères' },
  { value: 'publisher', label: 'Éditeur',    hint: 'Éditeur / mentions légales / domaine' },
  { value: 'issn',      label: 'ISSN',       hint: 'Numéro ISSN (format 1234-5678)' },
  { value: 'custom',    label: 'Custom…',    hint: 'Consigne libre (champ texte ci-dessous)' },
]

const ZOOM_MIN = 0.25
const ZOOM_MAX = 8
const ZOOM_STEP = 1.15  // multiplicatif — 15 % par cran

type Mode = 'draw' | 'select' | 'pan'
type DragKind = 'draw' | 'move' | 'resize' | 'pan' | null
type ResizeHandle = 'nw' | 'n' | 'ne' | 'e' | 'se' | 's' | 'sw' | 'w'

interface DragState {
  kind: DragKind
  startImgX: number  // coord image (ratio 0..1)
  startImgY: number
  startClientX: number
  startClientY: number
  // Snapshot au start pour move/resize/pan
  origZone?: CropZone
  origPanX?: number
  origPanY?: number
  handle?: ResizeHandle  // pour kind=resize
}

const HANDLES: ResizeHandle[] = ['nw', 'n', 'ne', 'e', 'se', 's', 'sw', 'w']
const HANDLE_CURSOR: Record<ResizeHandle, string> = {
  nw: 'nwse-resize', n: 'ns-resize', ne: 'nesw-resize',
  e: 'ew-resize',
  se: 'nwse-resize', s: 'ns-resize', sw: 'nesw-resize',
  w: 'ew-resize',
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
  const [zones, setZones] = useState<CropZone[]>([])
  // Type d'issue actif dans l'éditeur (3 sets distincts).
  // Le switch entre types re-hydrate zones depuis cropQ.data[type].
  const [currentType, setCurrentType] = useState<IssueType>('normal')
  const [selectedIdx, setSelectedIdx] = useState<number | null>(null)
  const [mode, setMode] = useState<Mode>('draw')
  // Espace tenu → override temporaire vers pan
  const [spacePressed, setSpacePressed] = useState(false)
  const activeMode: Mode = spacePressed ? 'pan' : mode

  const [drag, setDrag] = useState<DragState | null>(null)
  const [imgLoaded, setImgLoaded] = useState(false)
  const [imgNaturalSize, setImgNaturalSize] = useState<{ w: number; h: number } | null>(null)

  // Zoom (multiplicatif) + pan (offset en px de la fenêtre de canvas)
  const [zoom, setZoom] = useState(1)
  const [pan, setPan] = useState({ x: 0, y: 0 })
  // Fit initial : quand l'image se charge, ajuste le zoom pour
  // qu'elle tienne dans le viewport.
  const [needsFit, setNeedsFit] = useState(true)

  // Multi-touch (pinch-to-zoom + 2-finger pan). Stocke l'état
  // au début du geste (distance entre les doigts + centre + zoom
  // + pan) pour calculer les deltas propres.
  const [pinch, setPinch] = useState<null | {
    startDist: number
    startZoom: number
    startCenterX: number  // en coords canvas (px)
    startCenterY: number
    startPanX: number
    startPanY: number
  }>(null)

  // Mobile UI : bascule qui minimise le panneau zones pour donner
  // toute la place au canvas. Utile sur téléphone en portrait où
  // les 2 panneaux se marchent dessus.
  const [zonesCollapsed] = useState(false)

  // Which issue to preview
  const [previewIssueId, setPreviewIssueId] = useState<number | null>(null)

  const cropQ = useQuery({
    queryKey: ['ai-crop', magazineId],
    queryFn: () => getMagazineCrop(magazineId),
    enabled: open,
  })

  const issuesQ = useQuery({
    queryKey: ['issues-with-file', magazineId],
    queryFn: () => getIssues(magazineId),
    enabled: open,
  })
  const issuesWithFile = useMemo(
    () => (issuesQ.data ?? []).filter((i) => i.file != null),
    [issuesQ.data],
  )
  const magazineQ = useQuery({
    queryKey: ['magazine', magazineId],
    queryFn: () => getMagazine(magazineId),
    enabled: open,
  })
  const weekendDays = magazineQ.data?.weekendDays ?? null

  // Détermine le type d'une issue (mêmes règles que backend
  // _lookup_magazine_crop : isSpecial → hs, weekday ∈ weekend_days →
  // weekend, sinon normal).
  const getIssueType = (i: Issue): IssueType => {
    if (i.isSpecial) return 'hs'
    if (weekendDays && weekendDays.length > 0 && i.year && i.month && i.day) {
      // JS getDay : 0=Sun..6=Sat → conv 0=Mon..6=Sun
      const d = new Date(i.year, i.month - 1, i.day)
      const wd = d.getDay() === 0 ? 6 : d.getDay() - 1
      if (weekendDays.includes(wd)) return 'weekend'
    }
    return 'normal'
  }

  // Hydrate zones from server on open + à chaque changement de type.
  useEffect(() => {
    if (open && cropQ.data) {
      const typedZones = cropQ.data[currentType] ?? []
      setZones(typedZones)
      setSelectedIdx(typedZones.length > 0 ? 0 : null)
      setImgLoaded(false)
      setNeedsFit(true)
    }
    if (!open) {
      setDrag(null)
      setPreviewIssueId(null)
      setZoom(1)
      setPan({ x: 0, y: 0 })
    }
  }, [open, cropQ.data, currentType])

  // Space key = pan override
  useEffect(() => {
    if (!open) return
    function down(e: KeyboardEvent) {
      if (e.code === 'Space' && !isEditableTarget(e.target)) {
        e.preventDefault()
        setSpacePressed(true)
      }
    }
    function up(e: KeyboardEvent) {
      if (e.code === 'Space') setSpacePressed(false)
    }
    window.addEventListener('keydown', down)
    window.addEventListener('keyup', up)
    return () => {
      window.removeEventListener('keydown', down)
      window.removeEventListener('keyup', up)
    }
  }, [open])

  // Fit-to-view when image loads. Retry avec un requestAnimationFrame
  // pour laisser le layout se stabiliser (le grid parent peut ne pas
  // avoir sa hauteur définitive au tick où l'image se charge).
  useEffect(() => {
    if (needsFit && imgLoaded && imgNaturalSize) {
      const id = requestAnimationFrame(() => {
        fitToView()
        setNeedsFit(false)
      })
      return () => cancelAnimationFrame(id)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [needsFit, imgLoaded, imgNaturalSize])

  // Ré-fit sur resize (rotation portrait/paysage mobile).
  useEffect(() => {
    if (!open) return
    let scheduled = false
    function onResize() {
      if (scheduled) return
      scheduled = true
      requestAnimationFrame(() => {
        scheduled = false
        setNeedsFit(true)
      })
    }
    window.addEventListener('resize', onResize)
    window.addEventListener('orientationchange', onResize)
    return () => {
      window.removeEventListener('resize', onResize)
      window.removeEventListener('orientationchange', onResize)
    }
  }, [open])

  function fitToView() {
    // Zoom = 1 signifie « fit-to-view » par défaut : l'image
    // remplit la fenêtre via CSS (max-width: 100%, max-height:
    // 100%, object-fit: contain). Aucun transform nécessaire.
    // Les valeurs > 1 zooment DANS l'image ; les valeurs < 1
    // dézooment (permet de sortir du fit initial vers plus petit).
    setZoom(1)
    setPan({ x: 0, y: 0 })
  }

  /** Convert (clientX, clientY) → image ratio (0..1). */
  function clientToImgRatio(
    clientX: number,
    clientY: number,
  ): { x: number; y: number } | null {
    const el = imgRef.current
    if (!el) return null
    const b = el.getBoundingClientRect()
    if (b.width === 0 || b.height === 0) return null
    return {
      x: Math.max(0, Math.min(1, (clientX - b.left) / b.width)),
      y: Math.max(0, Math.min(1, (clientY - b.top) / b.height)),
    }
  }

  function hitTestZone(x: number, y: number): number | null {
    for (let i = zones.length - 1; i >= 0; i--) {
      const z = zones[i]
      if (x >= z.x && x <= z.x + z.w && y >= z.y && y <= z.y + z.h) return i
    }
    return null
  }

  function handlePointerDown(e: React.PointerEvent) {
    if (e.button !== 0 && e.button !== 1) return
    // Un pinch touch en cours prend le pas — pas de mono-doigt.
    if (pinch) return
    // Sur touch, si un 2e doigt arrive, on abandonne le drag
    // (handleTouchStart va prendre le relais).
    if (e.pointerType === 'touch' && (e as unknown as { detail?: number }).detail === 2) return
    // Middle-click always = pan.
    const isMiddle = e.button === 1
    const useMode: Mode = isMiddle ? 'pan' : activeMode

    if (useMode === 'pan') {
      e.preventDefault()
      ;(e.target as Element).setPointerCapture?.(e.pointerId)
      setDrag({
        kind: 'pan',
        startImgX: 0, startImgY: 0,
        startClientX: e.clientX, startClientY: e.clientY,
        origPanX: pan.x, origPanY: pan.y,
      })
      return
    }

    const p = clientToImgRatio(e.clientX, e.clientY)
    if (!p) return
    const hit = hitTestZone(p.x, p.y)

    if (useMode === 'select') {
      if (hit !== null) {
        setSelectedIdx(hit)
        ;(e.target as Element).setPointerCapture?.(e.pointerId)
        setDrag({
          kind: 'move',
          startImgX: p.x, startImgY: p.y,
          startClientX: e.clientX, startClientY: e.clientY,
          origZone: zones[hit],
        })
      } else {
        setSelectedIdx(null)
      }
      return
    }

    // Mode draw
    if (hit !== null) {
      // Cliquer sur une zone existante = la sélectionner, pas dessiner.
      setSelectedIdx(hit)
      return
    }
    ;(e.target as Element).setPointerCapture?.(e.pointerId)
    const draft: CropZone = {
      x: p.x, y: p.y, w: 0, h: 0, rotation: 0, tag: 'all',
    }
    setZones((zs) => {
      const next = [...zs, draft]
      setSelectedIdx(next.length - 1)
      return next
    })
    setDrag({
      kind: 'draw',
      startImgX: p.x, startImgY: p.y,
      startClientX: e.clientX, startClientY: e.clientY,
    })
  }

  function handlePointerMove(e: React.PointerEvent) {
    if (!drag) return
    if (drag.kind === 'pan') {
      const dx = e.clientX - drag.startClientX
      const dy = e.clientY - drag.startClientY
      setPan({ x: (drag.origPanX ?? 0) + dx, y: (drag.origPanY ?? 0) + dy })
      return
    }
    const p = clientToImgRatio(e.clientX, e.clientY)
    if (!p) return
    if (drag.kind === 'draw' && selectedIdx != null) {
      const x = Math.min(drag.startImgX, p.x)
      const y = Math.min(drag.startImgY, p.y)
      const w = Math.abs(p.x - drag.startImgX)
      const h = Math.abs(p.y - drag.startImgY)
      setZones((zs) => zs.map((z, i) => (i === selectedIdx ? { ...z, x, y, w, h } : z)))
    } else if (drag.kind === 'move' && selectedIdx != null && drag.origZone) {
      const dx = p.x - drag.startImgX
      const dy = p.y - drag.startImgY
      const origin = drag.origZone
      const nx = Math.max(0, Math.min(1 - origin.w, origin.x + dx))
      const ny = Math.max(0, Math.min(1 - origin.h, origin.y + dy))
      setZones((zs) => zs.map((z, i) => (i === selectedIdx ? { ...z, x: nx, y: ny } : z)))
    } else if (drag.kind === 'resize' && selectedIdx != null && drag.origZone && drag.handle) {
      // Recalcule les bounds selon la poignée saisie. On travaille en
      // coords ratio 0..1 sur l'image. Chaque handle modifie x et/ou
      // w (colonnes) et y et/ou h (lignes). Guard min-size 1% pour
      // ne pas créer de zones dégénérées.
      const dx = p.x - drag.startImgX
      const dy = p.y - drag.startImgY
      const o = drag.origZone
      const h = drag.handle
      let nx = o.x, ny = o.y, nw = o.w, nh = o.h
      // Bord ouest (contient nw, w, sw) → x + w bougent
      if (h === 'nw' || h === 'w' || h === 'sw') {
        const newX = Math.max(0, Math.min(o.x + o.w - 0.01, o.x + dx))
        nw = o.w + (o.x - newX)
        nx = newX
      }
      // Bord est (contient ne, e, se) → w seul bouge
      if (h === 'ne' || h === 'e' || h === 'se') {
        nw = Math.max(0.01, Math.min(1 - o.x, o.w + dx))
      }
      // Bord nord (contient nw, n, ne) → y + h bougent
      if (h === 'nw' || h === 'n' || h === 'ne') {
        const newY = Math.max(0, Math.min(o.y + o.h - 0.01, o.y + dy))
        nh = o.h + (o.y - newY)
        ny = newY
      }
      // Bord sud (contient sw, s, se) → h seul bouge
      if (h === 'sw' || h === 's' || h === 'se') {
        nh = Math.max(0.01, Math.min(1 - o.y, o.h + dy))
      }
      setZones((zs) => zs.map((z, i) =>
        i === selectedIdx ? { ...z, x: nx, y: ny, w: nw, h: nh } : z,
      ))
    }
  }

  function startResize(
    e: React.PointerEvent,
    idx: number,
    handle: ResizeHandle,
  ) {
    e.stopPropagation()
    e.preventDefault()
    ;(e.target as Element).setPointerCapture?.(e.pointerId)
    const p = clientToImgRatio(e.clientX, e.clientY)
    if (!p) return
    setSelectedIdx(idx)
    setDrag({
      kind: 'resize',
      handle,
      startImgX: p.x, startImgY: p.y,
      startClientX: e.clientX, startClientY: e.clientY,
      origZone: zones[idx],
    })
  }

  function handlePointerUp() {
    if (drag?.kind === 'draw' && selectedIdx != null) {
      const z = zones[selectedIdx]
      if (z && (z.w < 0.01 || z.h < 0.01)) {
        // Micro-drag / clic = drop la zone brouillon.
        setZones((zs) => zs.filter((_, i) => i !== selectedIdx))
        setSelectedIdx(null)
      }
    }
    setDrag(null)
  }

  function zoomAround(canvasX: number, canvasY: number, factor: number) {
    // Transform-origin = center → besoin de raisonner en offsets
    // relatifs au centre du wrap pour garder le point sous curseur
    // stable au zoom.
    const wrap = wrapRef.current
    if (!wrap) return
    const cx = wrap.clientWidth / 2
    const cy = wrap.clientHeight / 2
    const newZoom = Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, zoom * factor))
    if (newZoom === zoom) return
    const scaleDelta = newZoom / zoom
    // Offset actuel du point dans la vue transformée
    const relX = canvasX - cx - pan.x
    const relY = canvasY - cy - pan.y
    setZoom(newZoom)
    setPan({
      x: pan.x + relX * (1 - scaleDelta),
      y: pan.y + relY * (1 - scaleDelta),
    })
  }

  function handleWheel(e: React.WheelEvent) {
    e.preventDefault()
    const wrap = wrapRef.current
    if (!wrap) return
    const b = wrap.getBoundingClientRect()
    zoomAround(
      e.clientX - b.left,
      e.clientY - b.top,
      e.deltaY < 0 ? ZOOM_STEP : 1 / ZOOM_STEP,
    )
  }

  /** Multi-touch handlers pour le pinch-to-zoom mobile.
   *
   *  2 doigts : pinch = zoom, drag du centre = pan.
   *  1 doigt : géré par PointerEvents (draw/select/pan selon mode).
   */
  function handleTouchStart(e: React.TouchEvent) {
    if (e.touches.length !== 2) return
    e.preventDefault()
    const wrap = wrapRef.current
    if (!wrap) return
    const b = wrap.getBoundingClientRect()
    const [t1, t2] = [e.touches[0], e.touches[1]]
    const dx = t2.clientX - t1.clientX
    const dy = t2.clientY - t1.clientY
    const dist = Math.hypot(dx, dy)
    setPinch({
      startDist: dist,
      startZoom: zoom,
      startCenterX: (t1.clientX + t2.clientX) / 2 - b.left,
      startCenterY: (t1.clientY + t2.clientY) / 2 - b.top,
      startPanX: pan.x,
      startPanY: pan.y,
    })
    // Annule tout drag mono-doigt en cours
    setDrag(null)
  }

  function handleTouchMove(e: React.TouchEvent) {
    if (!pinch || e.touches.length !== 2) return
    e.preventDefault()
    const wrap = wrapRef.current
    if (!wrap) return
    const b = wrap.getBoundingClientRect()
    const cx = wrap.clientWidth / 2
    const cy = wrap.clientHeight / 2
    const [t1, t2] = [e.touches[0], e.touches[1]]
    const dist = Math.hypot(t2.clientX - t1.clientX, t2.clientY - t1.clientY)
    const centerX = (t1.clientX + t2.clientX) / 2 - b.left
    const centerY = (t1.clientY + t2.clientY) / 2 - b.top
    const factor = dist / pinch.startDist
    const newZoom = Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, pinch.startZoom * factor))
    const scaleDelta = newZoom / pinch.startZoom
    // transform-origin = center. On garde le point sous le centre
    // du pinch stable et on ajoute le déplacement des doigts.
    const relX = pinch.startCenterX - cx - pinch.startPanX
    const relY = pinch.startCenterY - cy - pinch.startPanY
    const dragOffsetX = centerX - pinch.startCenterX
    const dragOffsetY = centerY - pinch.startCenterY
    setZoom(newZoom)
    setPan({
      x: pinch.startPanX + relX * (1 - scaleDelta) + dragOffsetX,
      y: pinch.startPanY + relY * (1 - scaleDelta) + dragOffsetY,
    })
  }

  function handleTouchEnd(e: React.TouchEvent) {
    if (e.touches.length < 2) setPinch(null)
  }

  function updateZone(idx: number, patch: Partial<CropZone>) {
    setZones((zs) => zs.map((z, i) => (i === idx ? { ...z, ...patch } : z)))
  }

  function removeZone(idx: number) {
    setZones((zs) => zs.filter((_, i) => i !== idx))
    setSelectedIdx((s) => (s === idx ? null : s != null && s > idx ? s - 1 : s))
  }

  function rotateSelected() {
    if (selectedIdx == null) return
    const z = zones[selectedIdx]
    const currentIdx = ROTATIONS.indexOf((z.rotation ?? 0) as 0 | 90 | 180 | 270)
    updateZone(selectedIdx, { rotation: ROTATIONS[(currentIdx + 1) % ROTATIONS.length] })
  }

  const saveMut = useMutation({
    // PATCH d'un set spécifique — les 2 autres restent inchangés.
    mutationFn: () => setMagazineCropByType(magazineId, {
      [currentType]: zones,
    }),
    onSuccess: (res) => {
      toast.success(
        zones.length > 0
          ? `${zones.length} zone(s) enregistrée(s) pour ${magazineTitle}`
          : `Zones IA effacées pour ${magazineTitle}`,
      )
      onSaved?.(res.zones)
      onClose()
    },
    onError: (e: Error) => toast.error(`Échec : ${e.message}`),
  })

  const previewSrc = previewIssueId
    ? issueCoverPreviewUrl(magazineId, previewIssueId)
    : magazineCoverPreviewUrl(magazineId)

  function issueLabel(i: { number: number | null; year?: number | null; month?: number | null; day?: number | null }): string {
    const parts: string[] = []
    if (i.number != null) parts.push(`#${i.number}`)
    if (i.year) {
      const ymd = [i.year, i.month, i.day]
        .filter(Boolean)
        .map((n, idx) => (idx === 0 ? String(n) : String(n).padStart(2, '0')))
        .join('-')
      parts.push(ymd)
    }
    return parts.join(' ') || 'issue'
  }

  // Cursor CSS selon le mode + drag
  const canvasCursor =
    drag?.kind === 'pan'
      ? 'grabbing'
      : activeMode === 'pan'
        ? 'grab'
        : activeMode === 'select'
          ? 'default'
          : 'crosshair'

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) onClose() }}>
      <DialogContent className="sm:max-w-6xl bg-zinc-950 border-zinc-800 h-[95vh] flex flex-col overflow-hidden">
        <DialogHeader>
          <DialogTitle className="text-zinc-100">
            Zones IA — {magazineTitle}
          </DialogTitle>
          {/* Tabs type d'issue : chaque set indépendant, badge coloré
              même sémantique que la colonne Type des issues (violet
              weekend, ambre HS, zinc normal). */}
          <div className="flex gap-1 pt-1">
            {([
              { key: 'normal', label: 'Régulier', cls: 'bg-zinc-700 text-zinc-200 border-zinc-600' },
              { key: 'weekend', label: 'Weekend', cls: 'bg-purple-500/20 text-purple-200 border-purple-500/40' },
              { key: 'hs', label: 'Hors-série', cls: 'bg-amber-500/20 text-amber-200 border-amber-500/40' },
            ] as { key: IssueType; label: string; cls: string }[]).map((t) => {
              const active = currentType === t.key
              const count = (cropQ.data?.[t.key]?.length ?? 0)
              return (
                <button
                  key={t.key}
                  type="button"
                  onClick={() => setCurrentType(t.key)}
                  className={`px-3 py-1 text-xs rounded border transition-all ${
                    active
                      ? t.cls + ' ring-1 ring-offset-1 ring-offset-zinc-950 ring-white/20'
                      : 'bg-zinc-900 border-zinc-800 text-zinc-500 hover:text-zinc-300'
                  }`}
                  title={`${t.label} — ${count} zone${count > 1 ? 's' : ''}`}
                >
                  {t.label}
                  {count > 0 && (
                    <span className="ml-1.5 text-[10px] opacity-70">({count})</span>
                  )}
                </button>
              )
            })}
          </div>
        </DialogHeader>

        <div
          className={
            'flex-1 min-h-0 grid gap-3 ' +
            // Desktop : 2 colonnes canvas/zones. Mobile : empilé
            // mais on force une hauteur au canvas (60vh) pour ne
            // pas se retrouver avec un canvas de 100 px, sinon le
            // fit-to-view calcule un zoom minuscule → image noire.
            (zonesCollapsed
              ? 'lg:grid-cols-[1fr_auto]'
              : 'lg:grid-cols-[1fr_320px]')
          }
        >
          {/* --- Canvas column --------------------------------- */}
          <div className="flex flex-col min-w-0 h-[60vh] lg:h-auto lg:min-h-0">
            {/* Toolbar */}
            <div className="flex flex-wrap items-center gap-1 mb-2 shrink-0">
              <div className="flex rounded-md border border-zinc-800 overflow-hidden">
                <ToolBtn
                  active={activeMode === 'draw'}
                  onClick={() => setMode('draw')}
                  title="Dessiner (D)"
                >
                  <SquareDashed className="size-4" />
                </ToolBtn>
                <ToolBtn
                  active={activeMode === 'select'}
                  onClick={() => setMode('select')}
                  title="Sélectionner / déplacer (S)"
                >
                  <MousePointer2 className="size-4" />
                </ToolBtn>
                <ToolBtn
                  active={activeMode === 'pan'}
                  onClick={() => setMode('pan')}
                  title="Naviguer / Espace pour temporaire"
                >
                  <Hand className="size-4" />
                </ToolBtn>
              </div>

              <div className="flex rounded-md border border-zinc-800 overflow-hidden ml-1">
                <ToolBtn
                  onClick={() => setZoom((z) => Math.max(ZOOM_MIN, z / ZOOM_STEP))}
                  title="Dézoomer"
                >
                  <ZoomOut className="size-4" />
                </ToolBtn>
                <span className="px-2 flex items-center text-xs text-zinc-400 min-w-[3.5rem] justify-center">
                  {(zoom * 100).toFixed(0)}%
                </span>
                <ToolBtn
                  onClick={() => setZoom((z) => Math.min(ZOOM_MAX, z * ZOOM_STEP))}
                  title="Zoomer"
                >
                  <ZoomIn className="size-4" />
                </ToolBtn>
                <ToolBtn onClick={fitToView} title="Ajuster à la vue (F)">
                  <Maximize2 className="size-4" />
                </ToolBtn>
              </div>

              <div className="ml-auto text-[10px] text-zinc-500 hidden sm:block">
                {activeMode === 'draw' && 'Dessine un rect'}
                {activeMode === 'select' && 'Clique zone, drag = déplace'}
                {activeMode === 'pan' && 'Drag pour naviguer'}
                {spacePressed && ' · SPACE'}
              </div>
            </div>

            {/* Canvas */}
            <div
              ref={wrapRef}
              className="relative flex-1 min-h-0 rounded border border-zinc-800 bg-zinc-900/40 overflow-hidden select-none"
              onPointerDown={handlePointerDown}
              onPointerMove={handlePointerMove}
              onPointerUp={handlePointerUp}
              onPointerCancel={handlePointerUp}
              onWheel={handleWheel}
              onTouchStart={handleTouchStart}
              onTouchMove={handleTouchMove}
              onTouchEnd={handleTouchEnd}
              onContextMenu={(e) => e.preventDefault()}
              style={{ cursor: canvasCursor, touchAction: 'none' }}
            >
              {!imgLoaded && (
                <div className="absolute inset-0 flex items-center justify-center text-zinc-500 z-10">
                  <Loader2 className="size-6 animate-spin" />
                </div>
              )}
              {open && (
                // Layer intermédiaire qui applique le zoom (multiplicateur
                // au-delà du fit natif) + le pan. À zoom=1 le transform
                // est neutre : c'est le CSS de l'image ci-dessous
                // (max-w-full / max-h-full / object-contain) qui gère
                // le fit — bien plus fiable qu'un fit calculé en JS
                // (marchait pas sur mobile où wrap.clientHeight était 0
                // au tick du onLoad).
                <div
                  className="absolute inset-0 flex items-center justify-center"
                  style={{
                    transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
                    transformOrigin: 'center center',
                  }}
                >
                  <div className="relative">
                    <img
                      key={previewSrc}
                      ref={imgRef}
                      src={previewSrc}
                      alt="Couverture"
                      className="block max-w-full max-h-[60vh] lg:max-h-[85vh] object-contain pointer-events-none"
                      draggable={false}
                      onLoad={(e) => {
                        const el = e.currentTarget
                        setImgNaturalSize({ w: el.naturalWidth, h: el.naturalHeight })
                        setImgLoaded(true)
                      }}
                      onError={() => {
                        setImgLoaded(true)
                        toast.error(
                          "Impossible de charger la couverture — l'issue doit avoir un PDF",
                        )
                      }}
                    />
                    {imgLoaded && zones.map((z, idx) => {
                      const selected = idx === selectedIdx
                      return (
                        <div
                          key={idx}
                          className={
                            'absolute border-2 pointer-events-none ' +
                            (selected
                              ? 'border-purple-400 bg-purple-500/25'
                              : 'border-emerald-400/70 bg-emerald-500/15')
                          }
                          style={{
                            left: `${z.x * 100}%`,
                            top: `${z.y * 100}%`,
                            width: `${z.w * 100}%`,
                            height: `${z.h * 100}%`,
                          }}
                        >
                          <div
                            className={
                              'absolute -top-5 left-0 text-[10px] px-1.5 py-0.5 rounded font-mono whitespace-nowrap pointer-events-none ' +
                              (selected ? 'bg-purple-500 text-white' : 'bg-emerald-500/80 text-white')
                            }
                            style={{ transform: `scale(${1 / zoom})`, transformOrigin: '0 100%' }}
                          >
                            #{idx + 1} · {(z.w * 100).toFixed(0)}×{(z.h * 100).toFixed(0)}%
                            {z.rotation ? ` ↻${z.rotation}°` : ''}
                            {z.tag && z.tag !== 'all' ? ` · ${z.tag}` : ''}
                          </div>
                          {/* Handles de resize — visibles uniquement sur
                              la zone sélectionnée. Contre-scale (1/zoom)
                              pour rester à taille constante à l'écran. */}
                          {selected && HANDLES.map((h) => (
                            <ResizeHandleDot
                              key={h}
                              handle={h}
                              zoom={zoom}
                              onPointerDown={(e) => startResize(e, idx, h)}
                            />
                          ))}
                        </div>
                      )
                    })}
                  </div>
                </div>
              )}
            </div>

            {/* Issue picker under the canvas */}
            {issuesWithFile.length > 0 && (
              <div className="mt-2 shrink-0">
                <div className="text-[10px] uppercase tracking-wide text-zinc-500 mb-1">
                  Aperçu sur une autre issue
                </div>
                <div className="flex flex-wrap gap-1">
                  <IssueChip
                    label="Auto (dernière)"
                    active={previewIssueId == null}
                    onClick={() => { setPreviewIssueId(null); setNeedsFit(true) }}
                  />
                  {issuesWithFile.map((i) => (
                    <IssueChip
                      key={i.id}
                      label={issueLabel(i)}
                      active={previewIssueId === i.id}
                      onClick={() => { setPreviewIssueId(i.id); setNeedsFit(true) }}
                      issueType={getIssueType(i)}
                    />
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* --- Zone list column ------------------------------ */}
          <div className="flex flex-col min-h-0 space-y-2 overflow-y-auto pr-1">
            <div className="flex items-center justify-between">
              <div className="text-xs uppercase tracking-wide text-zinc-500">
                Zones ({zones.length})
              </div>
              <span className="text-[10px] text-zinc-500">
                Molette pour zoomer · Espace = pan
              </span>
            </div>
            {zones.length === 0 ? (
              <p className="text-xs text-zinc-500 italic px-2 py-3">
                Aucune zone. En mode <SquareDashed className="inline size-3" /> dessine
                un rectangle à la souris/au doigt.
              </p>
            ) : (
              <div className="space-y-2">
                {zones.map((z, idx) => (
                  <ZoneRow
                    key={idx}
                    idx={idx}
                    zone={z}
                    selected={idx === selectedIdx}
                    onSelect={() => setSelectedIdx(idx)}
                    onUpdate={(patch) => updateZone(idx, patch)}
                    onRemove={() => removeZone(idx)}
                  />
                ))}
              </div>
            )}
            {selectedIdx != null && (
              <Button
                variant="outline"
                size="sm"
                onClick={rotateSelected}
                className="w-full"
              >
                <RotateCw className="size-3" />
                Pivoter la sélection +90°
              </Button>
            )}
            {selectedIdx == null && zones.length > 0 && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setMode('draw')}
                className="w-full text-purple-400"
              >
                <Plus className="size-3" />
                Ajouter une nouvelle zone
              </Button>
            )}
          </div>
        </div>

        <DialogFooter className="pt-4 border-t border-zinc-800 gap-2 shrink-0">
          <Button
            variant="outline"
            onClick={() => setZones([])}
            disabled={saveMut.isPending || zones.length === 0}
            className="text-destructive hover:text-destructive"
          >
            <Trash2 className="size-4" />
            Tout effacer
          </Button>
          <div className="flex-1" />
          <Button variant="outline" onClick={onClose} disabled={saveMut.isPending}>
            <X className="size-4" />
            Annuler
          </Button>
          <Button
            onClick={() => saveMut.mutate()}
            disabled={saveMut.isPending}
          >
            {saveMut.isPending ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <Save className="size-4" />
            )}
            Enregistrer ({zones.length})
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

/* ----- Sub-components ------------------------------------------- */

function ToolBtn({
  children,
  onClick,
  title,
  active,
}: {
  children: React.ReactNode
  onClick: () => void
  title: string
  active?: boolean
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      className={
        'inline-flex items-center justify-center px-2 h-8 text-xs border-r border-zinc-800 last:border-r-0 ' +
        (active
          ? 'bg-purple-500/20 text-purple-200'
          : 'bg-zinc-900 text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800')
      }
    >
      {children}
    </button>
  )
}

function ResizeHandleDot({
  handle,
  zoom,
  onPointerDown,
}: {
  handle: ResizeHandle
  zoom: number
  onPointerDown: (e: React.PointerEvent) => void
}) {
  // Position en % dans la zone parente : 0 (bord), 50 (milieu), 100 (bord opposé)
  const pos: Record<ResizeHandle, { left: string; top: string }> = {
    nw: { left: '0%',   top: '0%'   },
    n:  { left: '50%',  top: '0%'   },
    ne: { left: '100%', top: '0%'   },
    e:  { left: '100%', top: '50%'  },
    se: { left: '100%', top: '100%' },
    s:  { left: '50%',  top: '100%' },
    sw: { left: '0%',   top: '100%' },
    w:  { left: '0%',   top: '50%'  },
  }
  return (
    <div
      onPointerDown={onPointerDown}
      className="absolute size-3 bg-white border border-purple-600 rounded-sm shadow"
      style={{
        left: pos[handle].left,
        top: pos[handle].top,
        // Centre le carré sur le point (translate -50/-50) puis
        // contre-scale pour rester à taille constante. Ordre matters :
        // scale d'abord, translate ensuite (dans le référentiel scalé).
        transform: `translate(-50%, -50%) scale(${1 / zoom})`,
        cursor: HANDLE_CURSOR[handle],
        pointerEvents: 'auto',
        touchAction: 'none',
      }}
    />
  )
}

function IssueChip({
  label,
  active,
  onClick,
  issueType,
}: {
  label: string
  active: boolean
  onClick: () => void
  /** Type d'issue pour dot coloré à gauche du label. Omit = pas de dot. */
  issueType?: IssueType
}) {
  const dotCls = issueType === 'weekend'
    ? 'bg-purple-400'
    : issueType === 'hs'
      ? 'bg-amber-400'
      : issueType === 'normal'
        ? 'bg-zinc-500'
        : ''
  return (
    <button
      type="button"
      onClick={onClick}
      className={
        'px-2 py-1 text-xs rounded border inline-flex items-center gap-1.5 ' +
        (active
          ? 'bg-purple-900/50 border-purple-600 text-purple-200'
          : 'bg-zinc-900 border-zinc-700 text-zinc-400')
      }
      title={
        issueType === 'weekend'
          ? `${label} — édition weekend`
          : issueType === 'hs'
            ? `${label} — hors-série`
            : label
      }
    >
      {issueType && (
        <span className={`inline-block w-1.5 h-1.5 rounded-full shrink-0 ${dotCls}`} />
      )}
      {label}
    </button>
  )
}

function ZoneRow({
  idx,
  zone,
  selected,
  onSelect,
  onUpdate,
  onRemove,
}: {
  idx: number
  zone: CropZone
  selected: boolean
  onSelect: () => void
  onUpdate: (patch: Partial<CropZone>) => void
  onRemove: () => void
}) {
  return (
    <div
      onClick={onSelect}
      className={
        'rounded border p-2 cursor-pointer transition ' +
        (selected
          ? 'border-purple-500/60 bg-purple-500/5'
          : 'border-zinc-800 bg-zinc-900/40 hover:border-zinc-700')
      }
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs font-mono text-zinc-400">Zone #{idx + 1}</span>
        <Button
          variant="ghost"
          size="icon-xs"
          onClick={(e) => { e.stopPropagation(); onRemove() }}
        >
          <Trash2 className="size-3 text-red-400" />
        </Button>
      </div>
      <div className="mt-1 text-[10px] font-mono text-zinc-500">
        x:{zone.x.toFixed(3)} y:{zone.y.toFixed(3)} w:{zone.w.toFixed(3)} h:{zone.h.toFixed(3)}
      </div>
      <Input
        value={zone.label ?? ''}
        onChange={(e) => onUpdate({ label: e.target.value || null })}
        placeholder="Label libre (masthead, tarif…)"
        onClick={(e) => e.stopPropagation()}
        className="mt-2 h-7 text-xs bg-zinc-900 border-zinc-700 text-zinc-100"
      />
      <div className="mt-2 flex flex-wrap gap-1" onClick={(e) => e.stopPropagation()}>
        <span className="text-[10px] text-zinc-500 w-full">
          Tag (que chercher dans cette zone)
        </span>
        {ZONE_TAGS.map((tg) => (
          <button
            key={tg.value}
            type="button"
            onClick={(e) => { e.stopPropagation(); onUpdate({ tag: tg.value }) }}
            title={tg.hint}
            className={
              'px-1.5 py-0.5 text-[10px] rounded border ' +
              ((zone.tag ?? 'all') === tg.value
                ? 'bg-emerald-900/50 border-emerald-600 text-emerald-200'
                : 'bg-zinc-900 border-zinc-700 text-zinc-400')
            }
          >
            {tg.label}
          </button>
        ))}
      </div>
      {zone.tag === 'custom' && (
        <Input
          value={zone.customTag ?? ''}
          onChange={(e) => onUpdate({ customTag: e.target.value || null })}
          placeholder='Consigne libre (ex. "cherche le code-barre")'
          onClick={(e) => e.stopPropagation()}
          className="mt-2 h-7 text-xs bg-zinc-900 border-zinc-700 text-zinc-100"
        />
      )}
      <div className="mt-2 flex items-center gap-1">
        <span className="text-[10px] text-zinc-500 mr-1">Rotation</span>
        {ROTATIONS.map((r) => (
          <button
            key={r}
            type="button"
            onClick={(e) => { e.stopPropagation(); onUpdate({ rotation: r }) }}
            className={
              'px-1.5 py-0.5 text-[10px] rounded border ' +
              ((zone.rotation ?? 0) === r
                ? 'bg-purple-900/50 border-purple-600 text-purple-200'
                : 'bg-zinc-900 border-zinc-700 text-zinc-400')
            }
          >
            {r}°
          </button>
        ))}
      </div>
    </div>
  )
}

function isEditableTarget(el: EventTarget | null): boolean {
  if (!(el instanceof HTMLElement)) return false
  const tag = el.tagName
  return tag === 'INPUT' || tag === 'TEXTAREA' || el.isContentEditable
}
