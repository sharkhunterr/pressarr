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
