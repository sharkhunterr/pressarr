import { apiFetch } from './client'

export interface QueueEntry {
  id: number
  magazineId: number | null
  magazineTitle: string | null
  issueId: number | null
  issueNumber: number | null
  title: string
  status: string
  protocol: string
  downloadClient: string | null
  size: number
  sizeLeft: number
  progress: number
  speed: number
  eta: number | null
  added: string | null
  errorMessage: string | null
  /** Optional live message for post-download activities
   *  (« IA · OCR couverture — page 1/3 »). Non-null only for
   *  the pressarr internal import tracker items. */
  statusMessage: string | null
  /** Ordered list of steps traversed by an import activity.
   *  Each entry has {step, label, hint?, at}. Non-null only for
   *  the internal import tracker items. */
  steps: Array<{ step: string; label: string; hint?: string | null; at: string }> | null
}

export const getQueue = () =>
  apiFetch<QueueEntry[]>('/queue')

export const removeFromQueue = (id: number, opts?: { blocklist?: boolean; removeFromClient?: boolean }) => {
  const params = new URLSearchParams()
  if (opts?.blocklist) params.set('blocklist', 'true')
  if (opts?.removeFromClient) params.set('remove_from_client', 'true')
  const qs = params.toString() ? `?${params.toString()}` : ''
  return apiFetch<void>(`/queue/${id}${qs}`, { method: 'DELETE' })
}

export const bulkRemove = (ids: number[], blocklist?: boolean) =>
  apiFetch<void>('/queue/bulk', {
    method: 'DELETE',
    body: JSON.stringify({ ids, blocklist: blocklist ?? false }),
  })

export const triggerImport = (id: number) =>
  apiFetch<{ success: boolean; message?: string }>(`/queue/${id}/import`, { method: 'POST' })
