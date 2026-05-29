import { apiFetch } from './client'

export interface MagazinePattern {
  id: number
  magazineId: number
  pattern: string
  source: string | null
  uploader: string | null
  lastSeenAt: string
  createdAt: string
}

export interface MagazineRule {
  id: number
  magazineId: number
  ruleType: 'include' | 'exclude'
  pattern: string
}

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
  useLatestIssueCover: boolean
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
  excludedDays: number[] | null
  patterns: MagazinePattern[]
  rules: MagazineRule[]
  statistics: {
    issueCount: number
    availableCount: number
    missingCount: number
    percentComplete: number
    nextIssueDate: string | null
  }
}

export interface SourceInfo {
  provider: string
  providerId: string
  count: number
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
  sources: SourceInfo[]
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

export interface RenamePreview {
  old_path: string
  new_path: string
}

export interface RenameResult {
  renamed: number
  results: RenamePreview[]
}

export const previewRename = (id: number) =>
  apiFetch<RenamePreview[]>(`/magazine/${id}/rename`)

export const executeRename = (id: number) =>
  apiFetch<RenameResult>(`/magazine/${id}/rename`, { method: 'POST' })

export const uploadMagazineCover = (id: number, data: FormData) =>
  apiFetch<Magazine>(`/magazine/${id}/cover`, { method: 'POST', body: data })

export const getMagazineCoverUrl = (id: number, cacheBuster?: string) =>
  `/api/v1/magazine/${id}/cover${cacheBuster ? `?v=${encodeURIComponent(cacheBuster)}` : ''}`

// Pattern management
export const addMagazinePattern = (magazineId: number, data: { pattern: string; source?: string; uploader?: string }) =>
  apiFetch<MagazinePattern>(`/magazine/${magazineId}/pattern`, {
    method: 'POST',
    body: JSON.stringify(data),
  })

export const updateMagazinePattern = (magazineId: number, patternId: number, data: { pattern?: string; source?: string; uploader?: string }) =>
  apiFetch<MagazinePattern>(`/magazine/${magazineId}/pattern/${patternId}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  })

export const deleteMagazinePattern = (magazineId: number, patternId: number) =>
  apiFetch<void>(`/magazine/${magazineId}/pattern/${patternId}`, { method: 'DELETE' })

export const convertPatternToExcludeRule = (magazineId: number, patternId: number) =>
  apiFetch<MagazineRule>(`/magazine/${magazineId}/pattern/${patternId}/to-exclude-rule`, {
    method: 'POST',
  })

// Rule management
export const addMagazineRule = (magazineId: number, data: { ruleType: string; pattern: string }) =>
  apiFetch<MagazineRule>(`/magazine/${magazineId}/rule`, {
    method: 'POST',
    body: JSON.stringify(data),
  })

export const updateMagazineRule = (magazineId: number, ruleId: number, data: { ruleType?: string; pattern?: string }) =>
  apiFetch<MagazineRule>(`/magazine/${magazineId}/rule/${ruleId}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  })

export const deleteMagazineRule = (magazineId: number, ruleId: number) =>
  apiFetch<void>(`/magazine/${magazineId}/rule/${ruleId}`, { method: 'DELETE' })
