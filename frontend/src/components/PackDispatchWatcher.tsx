/**
 * PackDispatchWatcher — écoute globale du WS `pack:dispatch_ready` et
 * ouvre le PackDispatchModal automatiquement quand un pack a fini son
 * download (auto_import=false → dispatch en attente de validation).
 *
 * Le back émet le event avec la preview complète (files + matched
 * magazine + issue proposé). Sans ce watcher, le event partait dans
 * le vide → aucun feedback UI → le user devait ouvrir File Manager
 * de chaque magazine pour comprendre ce qu'il s'était passé.
 *
 * Mount une fois au niveau App (à côté de <ApiKeyPrompt/>). Ne bloque
 * pas la navigation — juste un modal qui pop.
 */

import { useEffect, useState } from 'react'
import { toast } from 'sonner'

import { useWebSocket } from '@/hooks/useWebSocket'
import { type PackDispatchPreview } from '@/api/packs'
import { PackDispatchModal } from './PackDispatchModal'

export function PackDispatchWatcher() {
  const { on } = useWebSocket()
  const [preview, setPreview] = useState<PackDispatchPreview | null>(null)

  useEffect(() => {
    const off = on('pack:dispatch_ready', (payload: unknown) => {
      const p = payload as PackDispatchPreview | null
      if (!p) return
      setPreview(p)
      toast.info(
        `Pack « ${p.packName ?? p.packId} » prêt à dispatcher — `
        + `${p.matchedFiles}/${p.totalFiles} fichier(s) matché(s)`,
        {
          description: 'Ouvre le dialog pour confirmer ou corriger les associations.',
          duration: 8000,
        },
      )
    })
    return () => {
      off?.()
    }
  }, [on])

  if (!preview) return null

  return (
    <PackDispatchModal
      open={true}
      onOpenChange={(o) => {
        if (!o) setPreview(null)
      }}
      preview={preview}
      onComplete={() => setPreview(null)}
    />
  )
}
