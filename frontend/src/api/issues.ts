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

export const deleteIssueFile = (id: number) =>
  apiFetch<void>(`/issue/${id}/file`, { method: 'DELETE' })

export const getIssueCoverUrl = (id: number) =>
  `/api/v1/issue/${id}/cover`
