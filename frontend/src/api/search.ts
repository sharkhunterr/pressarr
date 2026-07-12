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

export const searchIndexers = (query: string, magazineId?: number) => {
  const params = new URLSearchParams({ query })
  if (magazineId) params.set('magazineId', String(magazineId))
  return apiFetch<SearchResult[]>(`/search?${params}`)
}

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

// Scene magazine indexers (Bookys, telecharger-magazines.org).
// Different shape from SearchResult — each release carries a
// list of hoster links, dispatched via JD2 folder-watch rather
// than torrent/usenet.
export interface MagazineReleaseHoster {
  hoster: string
  url: string
}

export interface MagazineRelease {
  id: number
  magazineId: number
  source: string
  sourceUrl: string
  title: string
  issueLabel: string | null
  year: number | null
  language: string | null
  fileFormat: string | null
  sizeBytes: number | null
  publishedAt: string | null
  coverUrl: string | null
  hosterLinks: MagazineReleaseHoster[]
  status: 'available' | 'grabbed' | 'imported' | 'failed'
  statusMessage: string | null
  grabbedAt: string | null
  discoveredAt: string | null
}

// List the releases pressarr already has cached for this
// magazine. ``source`` filters to one indexer — the UI passes
// it so each tab only sees its own rows.
export const listMagazineSceneReleases = (
  magazineId: number,
  source?: string,
) => {
  const qs = source ? `?source=${encodeURIComponent(source)}` : ''
  return apiFetch<MagazineRelease[]>(`/magazine/${magazineId}/releases${qs}`)
}

// Run a fresh scrape. Same ``source`` semantics; omit for
// "scrape every enabled indexer in parallel".
export const scanMagazineSceneReleases = (
  magazineId: number,
  source?: string,
) => {
  const qs = source ? `?source=${encodeURIComponent(source)}` : ''
  return apiFetch<MagazineRelease[]>(
    `/magazine/${magazineId}/releases/scan${qs}`,
    { method: 'POST' },
  )
}

export const grabMagazineSceneRelease = (
  magazineId: number,
  releaseId: number,
) =>
  apiFetch<MagazineRelease>(
    `/magazine/${magazineId}/releases/${releaseId}/grab`,
    { method: 'POST' },
  )
