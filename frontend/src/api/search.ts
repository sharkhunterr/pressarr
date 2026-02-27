import { apiFetch } from './client'

export interface SearchResult {
  guid: string
  title: string
  indexer: string
  source: string
  size: number
  age: number
  protocol: string
  seeders: number | null
  quality: string
  language: string
  score: number
  isBlocklisted: boolean
  downloadUrl: string
  publishDate: string | null
}

export const searchIssue = (issueId: number) =>
  apiFetch<SearchResult[]>(`/search?issueId=${issueId}`)

export const searchMagazine = (magazineId: number) =>
  apiFetch<SearchResult[]>(`/search?magazineId=${magazineId}`)

export const searchIndexers = (query: string) =>
  apiFetch<SearchResult[]>(`/search?query=${encodeURIComponent(query)}`)

export const grabRelease = (
  issueId: number,
  downloadUrl: string,
  title: string,
  protocol: string,
  guid: string,
  magazineId?: number,
) =>
  apiFetch<void>('/search/grab', {
    method: 'POST',
    body: JSON.stringify({ issueId: issueId || undefined, downloadUrl, title, protocol, guid, magazineId }),
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
  title: string,
  issueId?: number,
  magazineId?: number,
) =>
  apiFetch<{ issueId: number; downloadId: string; message: string }>(
    '/search/internetarchive/download',
    {
      method: 'POST',
      body: JSON.stringify({ identifier, filename, title, issueId, magazineId }),
    },
  )

// Anna's Archive
export const searchAnnasArchive = (query: string, magazineId?: number) => {
  const params = new URLSearchParams({ query })
  if (magazineId) params.set('magazineId', String(magazineId))
  return apiFetch<SearchResult[]>(`/search/annasarchive?${params}`)
}

export const downloadFromAA = (md5: string, title: string, issueId?: number, magazineId?: number) =>
  apiFetch<{ issueId: number; downloadId: string; message: string }>(
    '/search/annasarchive/download',
    {
      method: 'POST',
      body: JSON.stringify({ md5, title, issueId, magazineId }),
    },
  )
