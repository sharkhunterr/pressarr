import { apiFetch } from './client'

export interface QueueEntry {
  id: number
  magazineId: number
  magazineTitle: string
  issueId: number
  issueNumber: number | null
  title: string
  status: string
  protocol: string
  downloadClient: string
  size: number
  sizeLeft: number
  speed: number
  eta: string | null
  addedAt: string
  errorMessage: string | null
}

export const getQueue = () =>
  apiFetch<QueueEntry[]>('/queue')

export const removeFromQueue = (id: number, blocklist?: boolean) => {
  const params = blocklist ? '?blocklist=true' : ''
  return apiFetch<void>(`/queue/${id}${params}`, { method: 'DELETE' })
}

export const bulkRemove = (ids: number[], blocklist?: boolean) =>
  apiFetch<void>('/queue/bulk', {
    method: 'DELETE',
    body: JSON.stringify({ ids, blocklist: blocklist ?? false }),
  })
