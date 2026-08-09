/**
 * Global file manager API — vue agrégée sur tous les IssueFile du
 * système. Aligné sur `/api/v1/file` (backend).
 */
import { apiFetch } from './client'

export interface MagazineSummary {
  id: number
  title: string
}

export interface IssueSummary {
  id: number
  number: number | null
  year: number | null
  month: number | null
  day: number | null
}

export interface FileManagerRow {
  id: number
  filename: string
  path: string
  relativePath: string
  size: number
  format: string
  quality: string
  releaseGroup: string | null
  language: string | null
  importedAt: string
  magazine: MagazineSummary
  issue: IssueSummary | null
  existsOnDisk: boolean
}

export interface FileManagerPage {
  records: FileManagerRow[]
  page: number
  pageSize: number
  total: number
  totalAssigned: number
  totalUnassigned: number
  totalMissingOnDisk: number
}

export type AssignedFilter = 'all' | 'yes' | 'no'

export interface FileListParams {
  magazineId?: number
  assigned?: AssignedFilter
  quality?: string
  format?: string
  search?: string
  page?: number
  pageSize?: number
}

export const getFiles = (params: FileListParams = {}) => {
  const search = new URLSearchParams()
  if (params.magazineId !== undefined) search.set('magazineId', String(params.magazineId))
  if (params.assigned && params.assigned !== 'all') search.set('assigned', params.assigned)
  if (params.quality) search.set('quality', params.quality)
  if (params.format) search.set('format', params.format)
  if (params.search) search.set('search', params.search)
  if (params.page !== undefined) search.set('page', String(params.page))
  if (params.pageSize !== undefined) search.set('page_size', String(params.pageSize))
  return apiFetch<FileManagerPage>(`/file?${search.toString()}`)
}

export const assignFile = (
  fileId: number,
  body: { issueId?: number | null; magazineId?: number | null },
) =>
  apiFetch<FileManagerRow>(`/file/${fileId}/assign`, {
    method: 'PUT',
    body: JSON.stringify(body),
  })

export const deleteFile = (fileId: number, deleteOnDisk = true) =>
  apiFetch<void>(
    `/file/${fileId}?deleteOnDisk=${deleteOnDisk ? 'true' : 'false'}`,
    { method: 'DELETE' },
  )
