import { apiFetch } from './client'

export interface Magazine {
  id: number
  title: string
  year: number | null
  publisher: string | null
  frequency: string | null
  description: string | null
  coverPath: string | null
  rootFolderPath: string
  qualityProfileId: number
  monitored: boolean
  monitoringStartDate: string | null
  issueCount: number
  availableCount: number
  missingCount: number
  addedAt: string
  lastRefreshed: string | null
  metadataSource: string | null
  metadataId: string | null
}

export interface MetadataSearchResult {
  metadataId: string
  title: string
  year: number | null
  publisher: string | null
  description: string | null
  coverUrl: string | null
  source: string
  alreadyInLibrary: boolean
}

export const getMagazines = () =>
  apiFetch<Magazine[]>('/magazine')

export const getMagazine = (id: number) =>
  apiFetch<Magazine>(`/magazine/${id}`)

export const createMagazine = (data: Partial<Magazine> & { searchForMissingIssues?: boolean }) =>
  apiFetch<Magazine>('/magazine', {
    method: 'POST',
    body: JSON.stringify(data),
  })

export const updateMagazine = (id: number, data: Partial<Magazine>) =>
  apiFetch<Magazine>(`/magazine/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  })

export const deleteMagazine = (id: number, deleteFiles?: boolean) =>
  apiFetch<void>(`/magazine/${id}${deleteFiles ? '?deleteFiles=true' : ''}`, {
    method: 'DELETE',
  })

export const searchMetadata = (query: string) =>
  apiFetch<MetadataSearchResult[]>(`/magazine/search?query=${encodeURIComponent(query)}`)

export const refreshMetadata = (id: number) =>
  apiFetch<Magazine>(`/magazine/${id}/refresh`, { method: 'POST' })

export const getMagazineCoverUrl = (id: number) =>
  `/api/v1/magazine/${id}/cover`
