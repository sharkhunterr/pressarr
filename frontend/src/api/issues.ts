import { apiFetch } from './client'

export interface IssueFile {
  id: number
  path: string
  relativePath: string
  size: number
  format: string
  quality: string
  originalFilename: string
  releaseGroup: string | null
  language: string | null
  importedAt: string
}

export interface Issue {
  id: number
  magazineId: number
  number: number | null
  volume: number | null
  title: string | null
  publicationDate: string | null
  year: number | null
  month: number | null
  day: number | null
  status: string
  monitored: boolean
  isSpecial: boolean
  isForecast: boolean
  coverPath: string | null
  addedAt: string
  file: IssueFile | null
}

export const getIssues = (magazineId: number, status?: string) => {
  const params = new URLSearchParams({ magazineId: String(magazineId) })
  if (status) params.set('status', status)
  return apiFetch<Issue[]>(`/issue?${params.toString()}`)
}

export const getIssue = (id: number) =>
  apiFetch<Issue>(`/issue/${id}`)

export const updateIssueMonitored = (id: number, monitored: boolean) =>
  apiFetch<Issue>(`/issue/${id}`, {
    method: 'PUT',
    body: JSON.stringify({ monitored }),
  })

export const batchMonitor = (issueIds: number[], monitored: boolean) =>
  apiFetch<Issue[]>('/issue/monitor', {
    method: 'PUT',
    body: JSON.stringify({ issueIds, monitored }),
  })

export interface IssueUpdate {
  number?: number | null
  volume?: number | null
  title?: string | null
  year?: number | null
  month?: number | null
  day?: number | null
  monitored?: boolean
  isSpecial?: boolean
  quality?: string | null
  format?: string | null
  releaseGroup?: string | null
  language?: string | null
}

export const updateIssue = (id: number, data: IssueUpdate) =>
  apiFetch<Issue>(`/issue/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  })

export const deleteIssueFile = (id: number, unmonitor = false) =>
  apiFetch<void>(`/issue/${id}/file?unmonitor=${unmonitor}`, { method: 'DELETE' })

export const deleteIssue = (id: number) =>
  apiFetch<void>(`/issue/${id}`, { method: 'DELETE' })

export const refreshIssue = (id: number) =>
  apiFetch<unknown>(`/issue/${id}/refresh`, { method: 'POST' })

export const triggerIssueImport = (id: number) =>
  apiFetch<{ success: boolean; message?: string }>(`/issue/${id}/import`, { method: 'POST' })

export const getIssueCoverUrl = (id: number) =>
  `/api/v1/issue/${id}/cover`

export const getIssuePageCount = (id: number) =>
  apiFetch<{ pageCount: number; format: string }>(`/issue/${id}/pages`)

export const getIssuePageUrl = (id: number, page: number) =>
  `/api/v1/issue/${id}/page/${page}`
