import { apiFetch } from './client'

export interface PackPattern {
  id: number
  packId: number
  pattern: string
  source: string | null
  uploader: string | null
  lastSeenAt: string
  createdAt: string
}

export interface PackRule {
  id: number
  packId: number
  ruleType: 'include' | 'exclude'
  pattern: string
}

export interface PackStatistics {
  patternCount: number
  ruleCount: number
  totalGrabs: number
  lastGrabDate: string | null
}

export interface Pack {
  id: number
  name: string
  nameSlug: string
  description: string | null
  searchQuery: string
  recurrence: string
  autoSearch: boolean
  autoGrab: boolean
  autoImport: boolean
  monitored: boolean
  qualityProfileId: number
  rootFolderId: number
  addedAt: string
  lastSearchedAt: string | null
  patterns: PackPattern[]
  rules: PackRule[]
  statistics: PackStatistics
}

export interface PackDispatchFile {
  filename: string
  parsedTitle: string | null
  parsedDate: string | null
  matchedMagazineId: number | null
  matchedMagazineTitle: string | null
  matchScore: number
  excluded: boolean
  excludeReason: string | null
}

export interface PackDispatchPreview {
  packId: number
  /** Populé uniquement par le broadcast WebSocket (rendre le nom du
   *  pack dispo dans le toast/modal sans re-fetch). */
  packName?: string
  downloadId: string
  torrentName: string
  files: PackDispatchFile[]
  totalFiles: number
  matchedFiles: number
  excludedFiles: number
  unmatchedFiles: number
}

// ─── Post-hoc reimport (fichiers d'un pack déjà téléchargé) ────
export interface PackPendingFile {
  filename: string
  parsed_title: string | null
  parsed_number: string | null
  matched_magazine_id: number | null
  matched_magazine_title: string | null
  match_score: number
  excluded: boolean
  exclude_reason: string | null
}

export interface PackPendingFilesResponse {
  downloadId: string | null
  savePath?: string
  files: PackPendingFile[]
}

export const getPackPendingFiles = (packId: number, downloadId?: string) => {
  const q = downloadId ? `?download_id=${encodeURIComponent(downloadId)}` : ''
  return apiFetch<PackPendingFilesResponse>(`/pack/${packId}/pending-files${q}`)
}

export interface PackReimportBody {
  downloadId: string
  filename: string
  /** ID d'un magazine existant. Prioritaire sur createMagazine. */
  magazineId?: number
  /** Créer un magazine à la volée. root_folder + quality hérités du pack. */
  createMagazine?: {
    title: string
    frequency?: string
    publisher?: string
    country?: string
    language?: string
    monitored?: boolean
  }
}

export interface PackReimportResult {
  success: boolean
  magazine_id: number | null
  result: {
    filename: string
    success?: boolean
    message?: string
    issue_id?: number | null
  } | null
}

export const reimportPackFile = (packId: number, body: PackReimportBody) =>
  apiFetch<PackReimportResult>(`/pack/${packId}/reimport`, {
    method: 'POST',
    body: JSON.stringify(body),
  })

// CRUD
export const getPacks = () =>
  apiFetch<Pack[]>('/pack')

export const getPack = (id: number) =>
  apiFetch<Pack>(`/pack/${id}`)

export const createPack = (data: {
  name: string
  description?: string
  searchQuery: string
  recurrence?: string
  qualityProfileId: number
  rootFolderId: number
}) =>
  apiFetch<Pack>('/pack', {
    method: 'POST',
    body: JSON.stringify(data),
  })

export const updatePack = (id: number, data: Partial<Pack>) =>
  apiFetch<Pack>(`/pack/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  })

export const deletePack = (id: number) =>
  apiFetch<void>(`/pack/${id}`, { method: 'DELETE' })

// Patterns
export const addPackPattern = (packId: number, data: { pattern: string; source?: string; uploader?: string }) =>
  apiFetch<PackPattern>(`/pack/${packId}/pattern`, {
    method: 'POST',
    body: JSON.stringify(data),
  })

export const deletePackPattern = (packId: number, patternId: number) =>
  apiFetch<void>(`/pack/${packId}/pattern/${patternId}`, { method: 'DELETE' })

// Rules
export const addPackRule = (packId: number, data: { ruleType: string; pattern: string }) =>
  apiFetch<PackRule>(`/pack/${packId}/rule`, {
    method: 'POST',
    body: JSON.stringify(data),
  })

export const deletePackRule = (packId: number, ruleId: number) =>
  apiFetch<void>(`/pack/${packId}/rule/${ruleId}`, { method: 'DELETE' })

// Grab
export const grabPackRelease = (
  packId: number,
  downloadUrl: string,
  title: string,
  protocol: string,
  guid: string,
  indexer: string,
) =>
  apiFetch<{ packId: number; downloadId: string; message: string }>(`/pack/${packId}/grab`, {
    method: 'POST',
    body: JSON.stringify({ downloadUrl, title, protocol, guid, indexer }),
  })

// Dispatch
export const previewPackDispatch = (packId: number, downloadId: string) =>
  apiFetch<PackDispatchPreview>(`/pack/${packId}/dispatch/preview`, {
    method: 'POST',
    body: JSON.stringify({ downloadId }),
  })

export const executePackDispatch = (
  packId: number,
  downloadId: string,
  assignments: Array<{ filename: string; magazineId: number | null; skip: boolean }>,
) =>
  apiFetch<{ results: Array<{ success: boolean; message?: string }>; imported: number; total: number }>(
    `/pack/${packId}/dispatch/execute`,
    {
      method: 'POST',
      body: JSON.stringify({ downloadId, assignments }),
    },
  )
