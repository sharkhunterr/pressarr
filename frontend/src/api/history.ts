import { apiFetch } from './client'

export interface HistoryEntry {
  id: number
  eventType: string
  magazineId: number
  magazineTitle: string
  issueId: number | null
  issueNumber: number | null
  details: string
  date: string
}

export interface HistoryPage {
  items: HistoryEntry[]
  page: number
  pageSize: number
  totalItems: number
  totalPages: number
}

export const getHistory = (params: {
  page?: number
  pageSize?: number
  eventType?: string
  magazineId?: number
}) => {
  const search = new URLSearchParams()
  if (params.page !== undefined) search.set('page', String(params.page))
  if (params.pageSize !== undefined) search.set('pageSize', String(params.pageSize))
  if (params.eventType) search.set('eventType', params.eventType)
  if (params.magazineId !== undefined) search.set('magazineId', String(params.magazineId))
  return apiFetch<HistoryPage>(`/history?${search.toString()}`)
}
