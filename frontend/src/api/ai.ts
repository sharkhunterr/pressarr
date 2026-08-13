/**
 * API client for AI features (enrichment + ranker).
 *
 * Mirrors the shape defined in backend/app/api/v1/ai.py — every
 * field is camelCase to match CamelModel serialisation.
 */
import { apiFetch } from './client'

export interface AISettings {
  ollamaUrl: string
  ollamaTimeoutS: number
  enrichmentEnabled: boolean
  enrichmentMode: 'remplace' | 'complete' | 'propose'
  enrichmentVisionPages: number[]
  enrichmentVisionCrop: 'full' | 'top' | 'bottom' | 'top_bottom'
  textModel: string
  visionModel: string
  textPrompt: string
  visionPrompt: string
  arbiterPrompt: string
  rankerEnabled: boolean
  rankerMode: 'ai_wins' | 'ai_veto_only' | 'ai_advisory'
  rankerBatchSize: number
  rankerTopK: number
  rankerConfidenceThreshold: number
  rankerPrompt: string
}

export interface OllamaModelsProbe {
  reachable: boolean
  url: string
  models: string[]
  error?: string | null
}

export interface EnrichmentRun {
  id: number
  magazineId: number | null
  issueId: number | null
  trigger: string
  status: string
  appliedMode: string
  steps: Array<Record<string, unknown>>
  final: Record<string, unknown>
  errorMessage: string | null
  startedAt: string
  completedAt: string | null
  totalElapsedMs: number
}

export interface RankerRun {
  id: number
  magazineId: number | null
  patternId: number | null
  status: string
  appliedMode: string
  modelUsed: string
  candidates: Array<Record<string, unknown>>
  batches: Array<Record<string, unknown>>
  final: Record<string, unknown>
  scorerTopIndex: number | null
  aiPickedIndex: number | null
  confidence: number | null
  reason: string | null
  startedAt: string
  completedAt: string | null
  totalElapsedMs: number
}

export interface Proposal {
  id: number
  magazineId: number | null
  issueId: number | null
  runId: number
  proposed: Record<string, unknown>
  status: string
  createdAt: string
  reviewedAt: string | null
}

export interface ReanalyzeResponse {
  runId: number
  appliedMode: string
  final: Record<string, unknown>
  steps: Array<Record<string, unknown>>
  totalElapsedMs: number
}

export const getAISettings = () => apiFetch<AISettings>('/ai/settings')

export const saveAISettings = (data: Partial<AISettings>) =>
  apiFetch<AISettings>('/ai/settings', {
    method: 'POST',
    body: JSON.stringify(data),
  })

export const probeOllamaModels = (url?: string) => {
  const qs = url ? `?url=${encodeURIComponent(url)}` : ''
  return apiFetch<OllamaModelsProbe>(`/ai/ollama/models${qs}`)
}

export const reanalyzeMagazine = (
  magazineId: number,
  opts?: { issueId?: number; applyResult?: boolean },
) =>
  apiFetch<ReanalyzeResponse>(`/ai/reanalyze/${magazineId}`, {
    method: 'POST',
    body: JSON.stringify({
      issueId: opts?.issueId ?? null,
      applyResult: opts?.applyResult ?? true,
    }),
  })

export interface BatchRefreshResponse {
  magazineId: number
  total: number
  queued: number
  background: boolean
  skippedNoFile: number[]
}

export const refreshBatch = (
  magazineId: number,
  body: {
    issueIds?: number[]
    includeMetadata?: boolean
    includeAiText?: boolean
    includeAiVision?: boolean
    applyResult?: boolean
    force?: boolean
  },
) =>
  apiFetch<BatchRefreshResponse>(`/ai/refresh-batch/${magazineId}`, {
    method: 'POST',
    body: JSON.stringify({
      issueIds: body.issueIds ?? [],
      includeMetadata: body.includeMetadata ?? true,
      includeAiText: body.includeAiText ?? true,
      includeAiVision: body.includeAiVision ?? true,
      applyResult: body.applyResult ?? true,
      force: body.force ?? true,
    }),
  })

export const listEnrichmentRuns = (params?: {
  magazineId?: number
  limit?: number
}) => {
  const s = new URLSearchParams()
  if (params?.magazineId !== undefined) s.set('magazine_id', String(params.magazineId))
  if (params?.limit !== undefined) s.set('limit', String(params.limit))
  const qs = s.toString()
  return apiFetch<EnrichmentRun[]>(
    `/ai/runs/enrichment${qs ? `?${qs}` : ''}`,
  )
}

export const listRankerRuns = (params?: {
  magazineId?: number
  limit?: number
}) => {
  const s = new URLSearchParams()
  if (params?.magazineId !== undefined) s.set('magazine_id', String(params.magazineId))
  if (params?.limit !== undefined) s.set('limit', String(params.limit))
  const qs = s.toString()
  return apiFetch<RankerRun[]>(`/ai/runs/ranker${qs ? `?${qs}` : ''}`)
}

// --- Custom vision crop rectangle (drawn visually by user) -----------

export interface CropRect {
  x: number
  y: number
  w: number
  h: number
}

export interface CropRectResponse {
  magazineId: number
  rect: CropRect | null
}

export const getMagazineCrop = (magazineId: number) =>
  apiFetch<CropRectResponse>(`/ai/magazine/${magazineId}/crop`)

export const setMagazineCrop = (
  magazineId: number,
  rect: CropRect | null,
) =>
  apiFetch<CropRectResponse>(`/ai/magazine/${magazineId}/crop`, {
    method: 'PUT',
    body: JSON.stringify(rect),
  })

/** URL directe vers le PNG de la couverture (sert dans <img>) —
 *  ajoute un timestamp pour cache-buster + la clef API en query
 *  string (les <img> ne portent pas les headers Auth normaux). */
export const magazineCoverPreviewUrl = (magazineId: number) => {
  const apiKey = localStorage.getItem('pressarr_api_key') ?? ''
  const key = apiKey ? `&apikey=${encodeURIComponent(apiKey)}` : ''
  return `/api/v1/ai/magazine/${magazineId}/cover-preview?t=${Date.now()}${key}`
}

export const listProposals = (params?: {
  magazineId?: number
  status?: string
}) => {
  const s = new URLSearchParams()
  if (params?.magazineId !== undefined) s.set('magazine_id', String(params.magazineId))
  if (params?.status !== undefined) s.set('status', params.status)
  const qs = s.toString()
  return apiFetch<Proposal[]>(`/ai/proposals${qs ? `?${qs}` : ''}`)
}

export const acceptProposal = (id: number) =>
  apiFetch<{ status: string }>(`/ai/proposals/${id}/accept`, { method: 'POST' })

export const rejectProposal = (id: number) =>
  apiFetch<{ status: string }>(`/ai/proposals/${id}/reject`, { method: 'POST' })
