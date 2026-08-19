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

/** Payload structuré retourné par le pipeline wanted_search
 *  (~= WantedSearchResult côté backend). Utilisé par le bouton
 *  "Recherche maintenant" pour afficher le breakdown directement,
 *  sans passer par l'historique. Shape identique à celle attendue
 *  par WantedSearchDetail dans HistoryDetailModal. */
export interface WantedSearchCandidateDTO {
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
  download_url: string
  publish_date: string | null
  parsed_number: number | null
  parsed_year: number | null
  parsed_month: number | null
  parsed_day: number | null
  python_score: number
  rules_verdict: 'included' | 'excluded' | 'neutral'
  rules_reason: string | null
  is_blocklisted: boolean
  ai_verdict: 'picked' | 'not_picked' | 'vetoed' | 'skipped'
  ai_confidence: number | null
  ai_reason: string | null
  ai_batch_index: number | null
  final_score: number
  is_winner: boolean
  dropped_reason: string | null
}

export interface WantedSearchResultDTO {
  magazine_id: number
  magazine_title: string
  issue_id: number
  issue_label: string
  query: string
  trigger: string
  started_at: string
  finished_at: string
  elapsed_ms: number
  indexers_queried: string[]
  indexer_errors: Array<{ indexer: string; error: string }>
  total_raw: number
  total_after_rules: number
  total_after_blocklist: number
  ai_used: boolean
  ai_run_id: number | null
  ai_mode: string | null
  winner_guid: string | null
  winner_title: string | null
  winner_confidence: number | null
  auto_grab_threshold: number
  auto_grab_eligible: boolean
  auto_grab_attempted: boolean
  auto_grab_success: boolean | null
  auto_grab_message: string | null
  candidates: WantedSearchCandidateDTO[]
}

/** Lance le pipeline unifié synchronement sur une issue et retourne
 *  le résultat structuré complet (breakdown pipeline). Trigger =
 *  "manual" — outrepasse le toggle global. */
export const wantedSearchNow = (issueId: number) =>
  apiFetch<WantedSearchResultDTO>(`/search/wanted/${issueId}`, {
    method: 'POST',
  })

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
  overrides?: { targetIssueId?: number; targetDate?: string },
) =>
  apiFetch<void>('/search/grab', {
    method: 'POST',
    body: JSON.stringify({
      issueId: issueId || undefined,
      downloadUrl,
      title,
      protocol,
      guid,
      magazineId,
      targetIssueId: overrides?.targetIssueId,
      targetDate: overrides?.targetDate,
    }),
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
  overrides?: { targetIssueId?: number; targetDate?: string },
) =>
  apiFetch<{ issueId: number; downloadId: string; message: string }>(
    '/search/internetarchive/download',
    {
      method: 'POST',
      body: JSON.stringify({
        identifier, filename, title, issueId, magazineId,
        targetIssueId: overrides?.targetIssueId,
        targetDate: overrides?.targetDate,
      }),
    },
  )

// Anna's Archive
export const searchAnnasArchive = (query: string, magazineId?: number) => {
  const params = new URLSearchParams({ query })
  if (magazineId) params.set('magazineId', String(magazineId))
  return apiFetch<SearchResult[]>(`/search/annasarchive?${params}`)
}

export const downloadFromAA = (
  md5: string,
  title: string,
  issueId?: number,
  magazineId?: number,
  overrides?: { targetIssueId?: number; targetDate?: string },
) =>
  apiFetch<{ issueId: number; downloadId: string; message: string }>(
    '/search/annasarchive/download',
    {
      method: 'POST',
      body: JSON.stringify({
        md5, title, issueId, magazineId,
        targetIssueId: overrides?.targetIssueId,
        targetDate: overrides?.targetDate,
      }),
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
