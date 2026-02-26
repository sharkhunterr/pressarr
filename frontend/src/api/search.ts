import { apiFetch } from './client'

export interface SearchResult {
  guid: string
  title: string
  indexer: string
  size: number
  age: number
  protocol: string
  seeders: number | null
  quality: string
  language: string
  score: number
  isBlocklisted: boolean
  downloadUrl: string
}

export const searchIssue = (issueId: number) =>
  apiFetch<SearchResult[]>(`/search?issueId=${issueId}`)

export const searchMagazine = (magazineId: number) =>
  apiFetch<SearchResult[]>(`/search?magazineId=${magazineId}`)

export const grabRelease = (
  issueId: number,
  downloadUrl: string,
  title: string,
  protocol: string,
  guid: string,
) =>
  apiFetch<void>('/search/grab', {
    method: 'POST',
    body: JSON.stringify({ issueId, downloadUrl, title, protocol, guid }),
  })

// Internet Archive
export const searchInternetArchive = (query: string, magazineId?: number) => {
  const params = new URLSearchParams({ query })
  if (magazineId) params.set('magazineId', String(magazineId))
  return apiFetch<SearchResult[]>(`/search/internetarchive?${params}`)
}

export const downloadFromIA = (
  identifier: string,
  filename: string,
  issueId?: number,
  magazineId?: number,
) =>
  apiFetch<{ issueId: number; downloadId: string; message: string }>(
    '/search/internetarchive/download',
    {
      method: 'POST',
      body: JSON.stringify({ identifier, filename, issueId, magazineId }),
    },
  )

// Anna's Archive
export const searchAnnasArchive = (query: string, magazineId?: number) => {
  const params = new URLSearchParams({ query })
  if (magazineId) params.set('magazineId', String(magazineId))
  return apiFetch<SearchResult[]>(`/search/annasarchive?${params}`)
}

export const downloadFromAA = (md5: string, issueId?: number, magazineId?: number) =>
  apiFetch<{ issueId: number; downloadId: string; message: string }>(
    '/search/annasarchive/download',
    {
      method: 'POST',
      body: JSON.stringify({ md5, issueId, magazineId }),
    },
  )
