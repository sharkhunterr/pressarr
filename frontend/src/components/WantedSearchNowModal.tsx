/**
 * Modal "Recherche maintenant" — appelle POST /search/wanted/{id} et
 * affiche le breakdown pipeline (WantedSearchDetail) directement, sans
 * passer par l'historique.
 *
 * Ouverture (contrôlée par le parent) déclenche le fetch. Rechargement
 * possible via le bouton dédié. En cas d'auto-grab succès, invalide
 * les queries magazine/issues/queue pour rafraîchir la vue.
 */
import { useEffect, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Loader2, RotateCw, Sparkles } from 'lucide-react'
import { toast } from 'sonner'

import { wantedSearchNow, type WantedSearchResultDTO } from '@/api/search'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { WantedSearchDetail } from '@/components/WantedSearchDetail'

interface Props {
  issueId: number | null
  magazineId?: number
  onClose: () => void
}

export function WantedSearchNowModal({ issueId, magazineId, onClose }: Props) {
  const qc = useQueryClient()
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<WantedSearchResultDTO | null>(null)
  const [error, setError] = useState<string | null>(null)

  const run = async (id: number) => {
    setLoading(true)
    setError(null)
    setResult(null)
    toast.loading(
      'Recherche en cours — Prowlarr + IA + rules · peut prendre 30-90s…',
      { id: `wanted-search-${id}` },
    )
    try {
      const res = await wantedSearchNow(id)
      setResult(res)
      const winnerLabel = res.winner_title
        ? `winner ${res.winner_confidence?.toFixed(0) ?? '?'}% · ${res.winner_title.slice(0, 60)}`
        : 'aucun candidat'
      const grabMsg = res.auto_grab_success
        ? ' · auto-grab ✓'
        : res.auto_grab_attempted
          ? ' · auto-grab ✕'
          : ''
      toast.success(`${winnerLabel}${grabMsg}`, { id: `wanted-search-${id}`, duration: 6000 })
      // Rafraîchit les vues connexes si un grab a eu lieu
      if (res.auto_grab_success) {
        qc.invalidateQueries({ queryKey: ['issues', magazineId] })
        qc.invalidateQueries({ queryKey: ['queue'] })
      }
      qc.invalidateQueries({ queryKey: ['history'] })
    } catch (e) {
      const msg = (e as Error).message
      setError(msg)
      toast.error(`Échec : ${msg}`, { id: `wanted-search-${id}` })
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (issueId != null) {
      void run(issueId)
    } else {
      setResult(null)
      setError(null)
      setLoading(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [issueId])

  if (issueId == null) return null

  return (
    <Dialog open onOpenChange={(v) => { if (!v) onClose() }}>
      <DialogContent className="sm:max-w-3xl bg-zinc-950 border-zinc-800 max-h-[90vh] flex flex-col">
        <DialogHeader>
          <DialogTitle className="text-zinc-100 flex items-center gap-2">
            <Sparkles className="size-5 text-purple-400" />
            <span>Recherche wanted</span>
            {result?.issue_label && (
              <span className="text-sm text-zinc-500 font-normal">
                · {result.magazine_title} {result.issue_label}
              </span>
            )}
          </DialogTitle>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto pr-1 space-y-3">
          {loading && (
            <div className="flex items-center justify-center py-12 text-zinc-400 text-sm gap-2">
              <Loader2 className="size-4 animate-spin" />
              Pipeline en cours (Prowlarr → parse → rules → IA batch → arbitre)…
            </div>
          )}

          {error && !loading && (
            <div className="rounded border border-red-500/30 bg-red-500/5 p-3 text-sm text-red-300">
              <div className="font-medium mb-1">Échec de la recherche</div>
              <div className="text-xs font-mono opacity-80">{error}</div>
            </div>
          )}

          {result && !loading && (
            <WantedSearchDetail data={result as unknown as Record<string, unknown>} />
          )}
        </div>

        <DialogFooter className="pt-4 border-t border-zinc-800">
          <Button
            variant="outline"
            onClick={() => run(issueId)}
            disabled={loading}
          >
            {loading ? (
              <Loader2 className="size-3.5 animate-spin" />
            ) : (
              <RotateCw className="size-3.5" />
            )}
            Relancer
          </Button>
          <Button variant="outline" onClick={onClose}>
            Fermer
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
