import { useMemo, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { Loader2, Sparkles, X } from 'lucide-react'
import { toast } from 'sonner'

import { refreshBatch } from '@/api/ai'
import type { Issue } from '@/api/issues'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Switch } from '@/components/ui/switch'

/** Modal chosen by the user when they want to bulk-refresh a
 *  magazine's issues with the full stack of enrichment layers.
 *
 *  Toggles map 1:1 to backend `include_metadata` / `include_ai_text`
 *  / `include_ai_vision`. Issue list is filtered client-side to
 *  those with a file (no file = nothing to OCR).
 */
interface AIRefreshModalProps {
  open: boolean
  onClose: () => void
  magazineId: number
  magazineTitle: string
  issues: Issue[]
  onDone?: () => void
}

export function AIRefreshModal({
  open,
  onClose,
  magazineId,
  magazineTitle,
  issues,
  onDone,
}: AIRefreshModalProps) {
  const [includeMetadata, setIncludeMetadata] = useState(true)
  const [includeAiText, setIncludeAiText] = useState(true)
  const [includeAiVision, setIncludeAiVision] = useState(true)
  const [applyResult, setApplyResult] = useState(true)
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set())

  // Only offer issues that have a file — text-only enrichment CAN
  // work without a file but the user's mental model is "re-analyze
  // downloaded issues". Empty-file issues get quietly excluded.
  const analysable = useMemo(
    () => issues.filter((i) => i.file != null),
    [issues],
  )

  const allSelected =
    analysable.length > 0 && selectedIds.size === analysable.length
  const noneSelected = selectedIds.size === 0

  function toggleAll() {
    if (allSelected) setSelectedIds(new Set())
    else setSelectedIds(new Set(analysable.map((i) => i.id)))
  }
  function toggleOne(id: number) {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const mutation = useMutation({
    mutationFn: () =>
      refreshBatch(magazineId, {
        issueIds: Array.from(selectedIds),
        includeMetadata,
        includeAiText,
        includeAiVision,
        applyResult,
      }),
    onSuccess: (res) => {
      const ok = res.results.filter((r) => r.status === 'success').length
      const skip = res.results.filter((r) => r.status === 'skipped').length
      const err = res.results.filter((r) => r.status === 'error').length
      toast.success(
        `${ok} succès · ${skip} sauté(es) · ${err} erreur(s) sur ${res.total} issue(s)`,
      )
      onDone?.()
      onClose()
    },
    onError: (e: Error) => toast.error(`Échec : ${e.message}`),
  })

  const canRun =
    !mutation.isPending &&
    (includeMetadata || includeAiText || includeAiVision) &&
    !noneSelected

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) onClose() }}>
      <DialogContent className="sm:max-w-2xl bg-zinc-950 border-zinc-800 max-h-[90vh] flex flex-col">
        <DialogHeader>
          <DialogTitle className="text-zinc-100 flex items-center gap-2">
            <Sparkles className="size-5 text-purple-400" />
            Refresh avec IA — {magazineTitle}
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-5 overflow-y-auto flex-1 pr-1">
          {/* --- Sources ---------------------------------------- */}
          <div className="space-y-2">
            <div className="text-xs uppercase tracking-wide text-zinc-500">
              Sources d'enrichissement
            </div>
            <SourceRow
              label="Métadonnées classiques"
              hint="Google Books, Internet Archive, Anna's Archive"
              checked={includeMetadata}
              onChange={setIncludeMetadata}
            />
            <SourceRow
              label="IA texte (nom du fichier)"
              hint="Analyse le nom du torrent avec le LLM texte"
              checked={includeAiText}
              onChange={setIncludeAiText}
            />
            <SourceRow
              label="IA vision (couverture)"
              hint="OCR de la première page du PDF avec le LLM vision"
              checked={includeAiVision}
              onChange={setIncludeAiVision}
            />
          </div>

          {/* --- Autorité ---------------------------------------- */}
          <div>
            <div className="text-xs uppercase tracking-wide text-zinc-500 mb-2">
              Autorité
            </div>
            <SourceRow
              label="Appliquer les résultats"
              hint="Sinon : dry-run — les runs sont archivés mais rien n'est écrit sur les issues"
              checked={applyResult}
              onChange={setApplyResult}
            />
          </div>

          {/* --- Issues ----------------------------------------- */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <div className="text-xs uppercase tracking-wide text-zinc-500">
                Issues à réviser ({selectedIds.size} / {analysable.length})
              </div>
              <button
                type="button"
                onClick={toggleAll}
                className="text-xs text-purple-400 hover:text-purple-300"
                disabled={analysable.length === 0}
              >
                {allSelected ? 'Tout désélectionner' : 'Tout sélectionner'}
              </button>
            </div>

            {analysable.length === 0 ? (
              <p className="text-sm text-zinc-500 italic px-2 py-3">
                Aucune issue avec fichier disponible.
              </p>
            ) : (
              <div className="rounded border border-zinc-800 divide-y divide-zinc-800 max-h-64 overflow-y-auto">
                {analysable.map((iss) => {
                  const selected = selectedIds.has(iss.id)
                  return (
                    <label
                      key={iss.id}
                      className={
                        'flex items-center gap-3 px-3 py-2 cursor-pointer hover:bg-zinc-900/60 ' +
                        (selected ? 'bg-zinc-900/40' : '')
                      }
                    >
                      <input
                        type="checkbox"
                        checked={selected}
                        onChange={() => toggleOne(iss.id)}
                        className="size-4 rounded border-zinc-600 bg-zinc-900 accent-purple-500"
                      />
                      <div className="flex-1 min-w-0">
                        <div className="text-sm text-zinc-100 truncate">
                          #{iss.number ?? '?'}{' '}
                          {iss.year && (
                            <span className="text-zinc-500">
                              ({iss.year}{iss.month ? `-${String(iss.month).padStart(2, '0')}` : ''})
                            </span>
                          )}
                        </div>
                      </div>
                    </label>
                  )
                })}
              </div>
            )}
          </div>

          {/* --- Warning --------------------------------------- */}
          {includeAiVision && selectedIds.size > 5 && (
            <div className="rounded border border-amber-800/40 bg-amber-950/20 p-3 text-xs text-amber-300">
              ⚠ IA vision sur {selectedIds.size} issues peut prendre
              plusieurs minutes (5-60 s par PDF selon ton hardware Ollama).
              La progression est visible dans la Queue.
            </div>
          )}
        </div>

        <DialogFooter className="pt-4 border-t border-zinc-800">
          <Button variant="outline" onClick={onClose} disabled={mutation.isPending}>
            <X className="size-4" />
            Annuler
          </Button>
          <Button onClick={() => mutation.mutate()} disabled={!canRun}>
            {mutation.isPending ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <Sparkles className="size-4" />
            )}
            Lancer sur {selectedIds.size} issue{selectedIds.size !== 1 && 's'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function SourceRow({
  label,
  hint,
  checked,
  onChange,
}: {
  label: string
  hint: string
  checked: boolean
  onChange: (v: boolean) => void
}) {
  return (
    <div className="flex items-start justify-between gap-3 rounded border border-zinc-800 bg-zinc-900/40 px-3 py-2">
      <div className="min-w-0 flex-1">
        <div className="text-sm text-zinc-100">{label}</div>
        <div className="text-xs text-zinc-500">{hint}</div>
      </div>
      <Switch checked={checked} onCheckedChange={(v) => onChange(v === true)} />
    </div>
  )
}
