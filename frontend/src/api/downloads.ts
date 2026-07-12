import { apiFetch } from './client'

export interface IndexerOverrideEntry {
  enabled: boolean
  categories?: string | null
}

export interface IndexerConfig {
  id: number
  name: string
  url: string
  apiKey?: string
  categories: string
  enabled: boolean
  indexerOverrides: Record<string, IndexerOverrideEntry>
}

export interface DownloadClient {
  id: number
  name: string
  clientType: string
  protocol: string
  host: string
  port: number
  useSsl: boolean
  username?: string
  password?: string
  apiKey?: string
  category: string
  remotePath?: string
  localPath?: string
  isDefault: boolean
  priority: number
}

export interface ProwlarrIndexerInfo {
  id: number
  name: string
  categories: number[]
}

export interface TestResult {
  isValid: boolean
  message: string
  indexers?: ProwlarrIndexerInfo[]
}

// Indexer CRUD + test
export const getIndexers = () => apiFetch<IndexerConfig[]>('/indexer')

export const createIndexer = (
  data: Partial<IndexerConfig> & { apiKey: string },
) => apiFetch<IndexerConfig>('/indexer', { method: 'POST', body: JSON.stringify(data) })

export const updateIndexer = (
  id: number,
  data: Partial<IndexerConfig> & { apiKey?: string },
) => apiFetch<IndexerConfig>(`/indexer/${id}`, { method: 'PUT', body: JSON.stringify(data) })

export const deleteIndexer = (id: number) =>
  apiFetch<void>(`/indexer/${id}`, { method: 'DELETE' })

export const testIndexer = (data: { url: string; apiKey: string }) =>
  apiFetch<TestResult>('/indexer/test', { method: 'POST', body: JSON.stringify(data) })

export const testIndexerById = (id: number) =>
  apiFetch<TestResult>(`/indexer/${id}/test`, { method: 'POST' })

// Download client CRUD + test
export const getClients = () => apiFetch<DownloadClient[]>('/downloadclient')

export const createClient = (data: Partial<DownloadClient>) =>
  apiFetch<DownloadClient>('/downloadclient', { method: 'POST', body: JSON.stringify(data) })

export const updateClient = (id: number, data: Partial<DownloadClient>) =>
  apiFetch<DownloadClient>(`/downloadclient/${id}`, { method: 'PUT', body: JSON.stringify(data) })

export const deleteClient = (id: number) =>
  apiFetch<void>(`/downloadclient/${id}`, { method: 'DELETE' })

export const testClient = (data: Partial<DownloadClient>) =>
  apiFetch<TestResult>('/downloadclient/test', { method: 'POST', body: JSON.stringify(data) })
