import { apiFetch } from './client'

export interface Magazine {
  id: number
  title: string
  titleSlug: string
  issn: string | null
  publisher: string | null
  country: string | null
  frequency: string
  description: string | null
  coverPath: string | null
  rootFolderId: number
  qualityProfileId: number
  monitored: boolean
  monitoringStartDate: string | null
  searchTerms: string | null
  metadataProvider: string | null
  metadataProviderId: string | null
  addedAt: string
  lastSearchedAt: string | null
  lastMetadataRefresh: string | null
  statistics: {
    issueCount: number
    availableCount: number
    missingCount: number
    percentComplete: number
  }
}

export interface MetadataSearchResult {
  provider: string
  providerId: string
  title: string
  publisher: string | null
  country: string | null
  description: string | null
  coverUrl: string | null
  issn: string | null
  frequency: string | null
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
  apiFetch<MetadataSearchResult[]>(`/magazine/lookup?query=${encodeURIComponent(query)}`)

export const refreshMetadata = (id: number) =>
  apiFetch<Magazine>(`/magazine/${id}/refresh`, { method: 'POST' })

export const getMagazineCoverUrl = (id: number) =>
  `/api/v1/magazine/${id}/cover`
