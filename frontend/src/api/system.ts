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
