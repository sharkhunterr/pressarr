/**
 * Unified Activity API — replaces the ad-hoc Queue endpoint.
 *
 * Server side lives in `/api/v1/activity`. Everything asynchronous
 * (downloads, imports, AI analyses, scans, scheduled jobs) flows
 * through the same registry so the UI shows one coherent list and
 * the sidebar has a live counter.
 */
import { apiFetch } from './client'

export type ActivityKind =
  | 'download'
  | 'direct_download'
  | 'import'
  | 'analyze'
  | 'scan'
  | 'scheduled'

export type ActivityStatus =
  | 'queued'
  | 'running'
  | 'success'
  | 'failed'
  | 'cancelled'

export interface ActivityStep {
  step: string
  label: string
  hint?: string | null
  at?: string
  elapsed_ms?: number
  output?: unknown
  error?: string | null
}

export interface Activity {
  id: number
  kind: ActivityKind | string
  status: ActivityStatus | string
  magazineId: number | null
  issueId: number | null
  title: string
  subtitle: string | null
  progress: number
  statusMessage: string | null
  steps: ActivityStep[]
  payload: Record<string, unknown>
  errorMessage: string | null
  startedAt: string | null
  completedAt: string | null
}

export interface ActivityCounters {
  queued: number
  running: number
  total: number
}

export const listActivities = (params?: {
  kind?: ActivityKind | ActivityKind[]
  status?: ActivityStatus | ActivityStatus[] | 'history'
  magazineId?: number
  issueId?: number
  limit?: number
}) => {
  const s = new URLSearchParams()
  if (params?.kind) {
    s.set('kind', Array.isArray(params.kind) ? params.kind.join(',') : params.kind)
  }
  if (params?.status) {
    s.set('status', Array.isArray(params.status) ? params.status.join(',') : params.status)
  }
  if (params?.magazineId !== undefined) s.set('magazineId', String(params.magazineId))
  if (params?.issueId !== undefined) s.set('issueId', String(params.issueId))
  if (params?.limit !== undefined) s.set('limit', String(params.limit))
  const qs = s.toString()
  return apiFetch<Activity[]>(`/activity${qs ? `?${qs}` : ''}`)
}

export const getActivityCounters = () =>
  apiFetch<ActivityCounters>('/activity/counters')

export const getActivity = (id: number) =>
  apiFetch<Activity>(`/activity/${id}`)

export const cancelActivity = (id: number) =>
  apiFetch<Activity>(`/activity/${id}/cancel`, { method: 'POST' })

export const deleteActivity = (id: number) =>
  apiFetch<void>(`/activity/${id}`, { method: 'DELETE' })

export const purgeActivityHistory = (opts?: {
  kind?: ActivityKind
  olderThanDays?: number
}) => {
  const s = new URLSearchParams()
  if (opts?.kind) s.set('kind', opts.kind)
  if (opts?.olderThanDays !== undefined) s.set('olderThanDays', String(opts.olderThanDays))
  const qs = s.toString()
  return apiFetch<void>(`/activity${qs ? `?${qs}` : ''}`, { method: 'DELETE' })
}
