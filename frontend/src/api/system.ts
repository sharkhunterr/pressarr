import { apiFetch } from './client'

export interface SystemStatus {
  version: string
  startTime: string
  uptimeSeconds: number
  magazineCount: number
  issueCount: number
  availableCount: number
  missingCount: number
  queueCount: number
  diskSpace: { path: string; freeSpace: number; totalSpace: number }[]
}

export interface HealthCheck {
  database: boolean
  indexer?: boolean
  downloadClient?: boolean
  message: string
}

export interface RootFolder {
  id: number
  path: string
  isDefault: boolean
  freeSpace: number
  totalSpace: number
}

export interface NotificationConfig {
  id: number
  name: string
  type: string
  enabled: boolean
  settings: Record<string, string>
}

export interface GeneralSettings {
  port: number
  logLevel: string
  authEnabled: boolean
  scheduledTaskInterval: number
  importMode: string
}

export interface NamingTemplate {
  template: string
}

export interface MetadataSettings {
  googleBooksApiKey: string
  internetArchiveEnabled: boolean
  annasArchiveEnabled: boolean
  annasArchiveMirror: string
}

// Logs
export interface LogEntry {
  timestamp: string
  level: string
  logger: string
  message: string
}

export const getLogs = (params?: { limit?: number; level?: string; logger?: string }) => {
  const search = new URLSearchParams()
  if (params?.limit) search.set('limit', String(params.limit))
  if (params?.level) search.set('level', params.level)
  if (params?.logger) search.set('logger', params.logger)
  return apiFetch<LogEntry[]>(`/system/logs?${search}`)
}

// System
export const getStatus = () => apiFetch<SystemStatus>('/system/status')

export const getHealth = () => apiFetch<HealthCheck>('/system/health')

// Root folders
export const getRootFolders = () => apiFetch<RootFolder[]>('/rootfolder')

export const createRootFolder = (data: { path: string }) =>
  apiFetch<RootFolder>('/rootfolder', { method: 'POST', body: JSON.stringify(data) })

export const deleteRootFolder = (id: number) =>
  apiFetch<void>(`/rootfolder/${id}`, { method: 'DELETE' })

// Notifications
export const getNotifications = () => apiFetch<NotificationConfig[]>('/notification')

export const saveNotification = (data: Partial<NotificationConfig>) =>
  apiFetch<NotificationConfig>('/notification', { method: 'POST', body: JSON.stringify(data) })

export const testNotification = (data: Partial<NotificationConfig>) =>
  apiFetch<{ isValid: boolean; message: string }>('/notification/test', {
    method: 'POST',
    body: JSON.stringify(data),
  })

// General settings
export const getGeneralSettings = () => apiFetch<GeneralSettings>('/settings/general')

export const saveGeneralSettings = (data: Partial<GeneralSettings>) =>
  apiFetch<GeneralSettings>('/settings/general', { method: 'POST', body: JSON.stringify(data) })

// Naming template
export const getNamingTemplate = () => apiFetch<NamingTemplate>('/settings/naming')

export const saveNamingTemplate = (data: NamingTemplate) =>
  apiFetch<NamingTemplate>('/settings/naming', { method: 'POST', body: JSON.stringify(data) })

// Metadata settings
export const getMetadataSettings = () => apiFetch<MetadataSettings>('/settings/metadata')

export const saveMetadataSettings = (data: Partial<MetadataSettings>) =>
  apiFetch<MetadataSettings>('/settings/metadata', { method: 'POST', body: JSON.stringify(data) })

export const testGoogleBooks = (apiKey: string) =>
  apiFetch<{ isValid: boolean; message: string }>('/settings/metadata/test/googlebooks', {
    method: 'POST',
    body: JSON.stringify({ apiKey }),
  })

export const testInternetArchive = () =>
  apiFetch<{ isValid: boolean; message: string }>('/settings/metadata/test/internetarchive', {
    method: 'POST',
  })

export const testAnnasArchive = (mirror: string) =>
  apiFetch<{ isValid: boolean; message: string }>('/settings/metadata/test/annasarchive', {
    method: 'POST',
    body: JSON.stringify({ mirror }),
  })

// Scene magazine indexers (Bookys, telecharger-magazines.org)
// + FlareSolverr bypass + JDownloader 2 folder-watch.
export interface SceneIndexersSettings {
  bookysEnabled: boolean
  bookysUrl: string
  bookysUsername: string
  /** Masked ("***") on read; UI sends back ``"***"`` to keep
   *  the stored value, or a new string to replace, or empty to
   *  clear. */
  bookysPassword: string
  telechargerMagazinesEnabled: boolean
  telechargerMagazinesUrl: string
  flaresolverrUrl: string
  flaresolverrTimeoutMs: number
  jdownloaderEnabled: boolean
  jdownloaderFolderwatch: string
  jdownloaderOutputPath: string
}

export const getSceneIndexers = () =>
  apiFetch<SceneIndexersSettings>('/settings/scene-indexers')

export const saveSceneIndexers = (data: Partial<SceneIndexersSettings>) =>
  apiFetch<SceneIndexersSettings>('/settings/scene-indexers', {
    method: 'POST',
    body: JSON.stringify(data),
  })

export const testBookys = () =>
  apiFetch<{ isValid: boolean; message: string }>(
    '/settings/scene-indexers/test/bookys',
    { method: 'POST' },
  )

export const testTelechargerMagazines = () =>
  apiFetch<{ isValid: boolean; message: string }>(
    '/settings/scene-indexers/test/telecharger-magazines',
    { method: 'POST' },
  )

export const testFlaresolverr = () =>
  apiFetch<{ isValid: boolean; message: string }>(
    '/settings/scene-indexers/test/flaresolverr',
    { method: 'POST' },
  )

// ---------------------------------------------------------------------------
// JDownloader 2 queue inspection — pressarr-side view of what JD2 is doing
// (no JD2 RPC required, reads/writes the shared folderwatch + output paths).
// ---------------------------------------------------------------------------

export interface CrawljobItem {
  filename: string
  packageName: string | null
  downloadFolder: string | null
  textUrlCount: number
  primaryUrl: string | null
  releaseId: number | null
  writtenAtMs: number
}

export interface CompletedFile {
  name: string
  sizeBytes: number
  isPart: boolean
}

export interface CompletedFolder {
  folderName: string
  fileCount: number
  totalSizeBytes: number
  files: CompletedFile[]
}

export interface JDownloaderState {
  enabled: boolean
  folderwatchPath: string
  outputPath: string
  folderwatchExists: boolean
  outputExists: boolean
  pendingJobs: CrawljobItem[]
  completedFolders: CompletedFolder[]
}

export const getJDownloaderState = () =>
  apiFetch<JDownloaderState>('/jdownloader/state')

export const deleteCrawljob = (filename: string) =>
  apiFetch<{ deleted: string }>(
    `/jdownloader/folderwatch/${encodeURIComponent(filename)}`,
    { method: 'DELETE' },
  )

export const clearAllCrawljobs = () =>
  apiFetch<{ deleted: number }>('/jdownloader/folderwatch/clear', {
    method: 'POST',
  })

export const deleteCompletedFolder = (folderName: string) =>
  apiFetch<{ deleted: string }>(
    `/jdownloader/output/${encodeURIComponent(folderName)}`,
    { method: 'DELETE' },
  )

// Commands
export interface CommandResource {
  id: number
  name: string
  status: 'queued' | 'started' | 'completed' | 'failed'
  started: string | null
  ended: string | null
  message: string | null
  trigger: string
}

export const executeCommand = (name: string, body?: Record<string, unknown>) =>
  apiFetch<CommandResource>('/command', {
    method: 'POST',
    body: JSON.stringify({ name, body }),
  })
