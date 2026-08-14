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
  /** Pipeline IA complet (torrent → python-OCR → vision → arbiter)
   *  sur chaque fichier. False = parser filename seul (10× plus rapide,
   *  moins précis). */
  deepAiAnalysis: boolean
  /** Si aucun magazine ne matche fortement, créer un placeholder à la
   *  volée + auto-import. False = fichier reste en pending_user. */
  autoCreateMissingMagazines: boolean
  /** ON = rien n'est jamais auto-importé, tout va en pending_user. */
  previewBeforeImport: boolean
  /** Fréquence appliquée aux magazines placeholder auto-créés. */
  defaultNewMagazineFrequency: string
  monitored: boolean
  qualityProfileId: number
  rootFolderId: number
  addedAt: string
  lastSearchedAt: string | null
  patterns: PackPattern[]
  rules: PackRule[]
  statistics: PackStatistics
}

/** Nouveau : fichier extrait d'un pack + analyse IA + décision. */
export interface PackDispatchFile {
  id: number
  packId: number
  downloadId: string
  filename: string
  path: string
  size: number
  status:
    | 'pending_analysis'
    | 'analyzed'
    | 'pending_user'
    | 'imported'
    | 'ignored'
    | 'error'
  errorMessage: string | null
  aiRunId: number | null
  extractedMetadata: {
    title?: string | null
    issue_number?: number | null
    year?: number | null
    month?: number | null
    day?: number | null
    issn?: string | null
    source?: string
    run_id?: number | null
  } | null
  matchedMagazineId: number | null
  matchedMagazineTitle: string | null
  matchScore: number | null
  matchSource: 'parser' | 'fuzzy' | 'vision' | 'arbiter' | 'issn' | 'manual' | null
  proposedMagazineData: {
    title?: string
    issn?: string | null
    frequency?: string
  } | null
  userAction: 'assign_existing' | 'create_magazine' | 'ignore' | null
  userActionMagazineId: number | null
  resolvedIssueId: number | null
  createdAt: string
  analyzedAt: string | null
  resolvedAt: string | null
}

export interface PackDispatchMetadataOverrides {
  title?: string
  issue_number?: number
  year?: number
  month?: number
  day?: number
  issn?: string | null
}

export interface PackDispatchResolveBody {
  action: 'assign_existing' | 'create_magazine' | 'ignore'
  magazineId?: number
  magazineData?: {
    title: string
    frequency?: string
    publisher?: string
    country?: string
    language?: string
    monitored?: boolean
    issn?: string | null
  }
  /** Overrides éditables sur les metadata extraites — permet à
   *  l'utilisateur de corriger les erreurs d'IA avant résolution. */
  metadataOverrides?: PackDispatchMetadataOverrides
}

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

// Dispatch (nouveau pipeline persistent)
export const listPackDispatchFiles = (
  packId: number,
  status?: PackDispatchFile['status'],
) => {
  const qs = status ? `?status=${encodeURIComponent(status)}` : ''
  return apiFetch<PackDispatchFile[]>(`/pack/${packId}/dispatch${qs}`)
}

export const resolvePackDispatchFile = (
  packId: number,
  fileId: number,
  body: PackDispatchResolveBody,
) =>
  apiFetch<PackDispatchFile>(`/pack/${packId}/dispatch/${fileId}/resolve`, {
    method: 'POST',
    body: JSON.stringify(body),
  })

export const reanalyzePackDispatchFile = (packId: number, fileId: number) =>
  apiFetch<PackDispatchFile>(`/pack/${packId}/dispatch/${fileId}/reanalyze`, {
    method: 'POST',
  })

/** Édite les metadata extraites d'un fichier dispatch (title, N°,
 *  date, ISSN). Merge shallow — seuls les champs fournis écrasent. */
export const updatePackDispatchMetadata = (
  packId: number,
  fileId: number,
  overrides: PackDispatchMetadataOverrides,
) =>
  apiFetch<PackDispatchFile>(`/pack/${packId}/dispatch/${fileId}`, {
    method: 'PATCH',
    body: JSON.stringify(overrides),
  })

export const deletePackDispatchFile = (packId: number, fileId: number) =>
  apiFetch<void>(`/pack/${packId}/dispatch/${fileId}`, { method: 'DELETE' })
