import { apiFetch } from './client'

export interface HistoryEntry {
  id: number
  eventType: string
  magazineId: number | null
  magazineTitle: string | null
  issueId: number | null
  issueNumber: number | null
  issueDate: string | null
  details: string | null
  data: Record<string, unknown> | null
  date: string
}

export interface HistoryPage {
  records: HistoryEntry[]
  page: number
  pageSize: number
  totalRecords: number
}

export const getHistory = (params: {
  page?: number
  pageSize?: number
  eventType?: string
  magazineId?: number
  issueId?: number
  packId?: number
}) => {
  const search = new URLSearchParams()
  if (params.page !== undefined) search.set('page', String(params.page))
  if (params.pageSize !== undefined) search.set('page_size', String(params.pageSize))
  if (params.eventType) search.set('event_type', params.eventType)
  if (params.magazineId !== undefined) search.set('magazine_id', String(params.magazineId))
  if (params.issueId !== undefined) search.set('issue_id', String(params.issueId))
  if (params.packId !== undefined) search.set('pack_id', String(params.packId))
  return apiFetch<HistoryPage>(`/history?${search.toString()}`)
}
