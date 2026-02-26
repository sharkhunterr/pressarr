import { apiFetch } from './client'

export interface CalendarEntry {
  issueId: number | null
  magazineId: number
  magazineTitle: string
  coverUrl: string | null
  date: string
  number: number | null
  status: string
  isForecast: boolean
}

export const getCalendar = (
  start: string,
  end: string,
  magazineId?: number,
  includeForecast?: boolean,
) => {
  const params = new URLSearchParams({ start, end })
  if (magazineId !== undefined) params.set('magazineId', String(magazineId))
  if (includeForecast !== undefined) params.set('includeForecast', String(includeForecast))
  return apiFetch<CalendarEntry[]>(`/calendar?${params.toString()}`)
}

export const skipForecast = (issueId: number) =>
  apiFetch<CalendarEntry>(`/calendar/${issueId}/skip`, { method: 'POST' })

export const unskipForecast = (issueId: number) =>
  apiFetch<CalendarEntry>(`/calendar/${issueId}/unskip`, { method: 'POST' })
