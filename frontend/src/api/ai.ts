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
  /** Enable the 3rd deterministic source alongside torrent + LLM vision. */
  pythonOcrEnabled: boolean
  /** Which engine to use for the deterministic OCR : tesseract |
   *  rapidocr | easyocr. Availability is probed via
   *  /ai/python-ocr/engines (missing deps grey out). */
  pythonOcrEngine: 'tesseract' | 'rapidocr' | 'easyocr'
  textModel: string
  visionModel: string
  /** Per-step overrides — null falls back to ``textModel``. Chaque
   *  étape (torrent-analysis, arbiter) accepte son propre modèle. */
  torrentModel: string | null
  arbiterModel: string | null
  textPrompt: string
  visionPrompt: string
  arbiterPrompt: string
  rankerEnabled: boolean
  rankerMode: 'ai_wins' | 'ai_veto_only' | 'ai_advisory'
  rankerBatchSize: number
  rankerTopK: number
  rankerConfidenceThreshold: number
  rankerPrompt: string
  /** Pipeline wanted-issue search (Prowlarr + rules + IA + auto-grab).
   *  Global toggle. False désactive scheduler + auto-triggers ; les
   *  recherches manuelles (bouton UI) restent possibles. */
  wantedSearchEnabled: boolean
  /** Toggle SÉPARÉ pour l'auto-grab automatique. False par défaut
   *  après incident (fichier écrasé) — l'utilisateur doit opt-in
   *  explicitement + s'assurer que ses rules include/exclude sont
   *  solides. Le pipeline continue de tourner et de logguer, il
   *  ne DÉCLENCHE juste plus le grab. */
  wantedSearchAutoGrabEnabled: boolean
  /** Seuil confidence (0-100) au-dessus duquel un winner est
   *  auto-grabé sans intervention utilisateur. */
  wantedSearchAutoGrabThreshold: number
  /** Fuzzy-match plancher entre titre du release et titre magazine.
   *  En dessous, l'auto-grab est bloqué même si le composite est haut.
   *  Garde-fou contre les picks IA off-topic. */
  wantedSearchMinTitleMatch: number
  /** Intervalle du scheduler wanted_search_sync en minutes.
   *  Défaut 240 (4h). Reschedule à chaud au save. */
  wantedSearchIntervalMinutes: number
  /** Cooldown par-issue en heures. Une issue déjà scannée n'est
   *  re-picked qu'après ce délai. */
  wantedSearchCooldownHours: number
  /** Nombre max d'issues traitées par cycle scheduler. Le reste
   *  attend le cycle suivant — évite de saturer l'IA. */
  wantedSearchMaxPerCycle: number
}

export interface PythonOCRProbeEntry {
  engine: 'tesseract' | 'rapidocr' | 'easyocr'
  available: boolean
  error: string | null
}

export const probePythonOCREngines = () =>
  apiFetch<PythonOCRProbeEntry[]>('/ai/python-ocr/engines')

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
    /** Fine-grained toggles pour les steps du pipeline. Null =
     *  fallback (cohérent avec la source parente). */
    includePythonOcr?: boolean | null
    includeAiArbiter?: boolean | null
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
      includePythonOcr: body.includePythonOcr ?? null,
      includeAiArbiter: body.includeAiArbiter ?? null,
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

// --- Custom vision crop zones (drawn visually by user) ---------------

export interface CropZone {
  x: number
  y: number
  w: number
  h: number
  /** Clockwise rotation in degrees {0, 90, 180, 270} applied to
   *  the rendered crop before it hits the vision model. Useful for
   *  narrow vertical bands (e.g. Paris Match tarif strip) whose
   *  text is printed at 90°. Default 0. */
  rotation?: number
  /** Optional free-form label surfaced in History runs
   *  ("masthead", "tarif", ...). */
  label?: string | null
  /** Zone tag from a fixed vocabulary — pilots the vision prompt.
   *  number | date | title | subtitle | price | publisher | issn | all | custom */
  tag?: 'number' | 'date' | 'title' | 'subtitle' | 'price' | 'publisher' | 'issn' | 'all' | 'custom'
  /** Free-text hint used only when tag === "custom".
   *  Injected into the vision prompt for that specific zone. */
  customTag?: string | null
}

export interface CropRectResponse {
  magazineId: number
  zones: CropZone[]
}

export const getMagazineCrop = (magazineId: number) =>
  apiFetch<CropRectResponse>(`/ai/magazine/${magazineId}/crop`)

export const setMagazineCrop = (
  magazineId: number,
  zones: CropZone[],
) =>
  apiFetch<CropRectResponse>(`/ai/magazine/${magazineId}/crop`, {
    method: 'PUT',
    body: JSON.stringify({ zones }),
  })

/** URL directe vers le PNG de la couverture (sert dans <img>) —
 *  ajoute un timestamp pour cache-buster + la clef API en query
 *  string (les <img> ne portent pas les headers Auth normaux). */
export const magazineCoverPreviewUrl = (magazineId: number) => {
  const apiKey = localStorage.getItem('pressarr_api_key') ?? ''
  const key = apiKey ? `&apikey=${encodeURIComponent(apiKey)}` : ''
  return `/api/v1/ai/magazine/${magazineId}/cover-preview?t=${Date.now()}${key}`
}

/** URL directe vers le PNG de la couverture d'UNE issue précise.
 *  Utilisé par le crop editor pour naviguer entre issues et
 *  valider que les zones tombent bien partout. */
export const issueCoverPreviewUrl = (magazineId: number, issueId: number) => {
  const apiKey = localStorage.getItem('pressarr_api_key') ?? ''
  const key = apiKey ? `&apikey=${encodeURIComponent(apiKey)}` : ''
  return (
    `/api/v1/ai/magazine/${magazineId}/issue-cover-preview` +
    `?issueId=${issueId}${key}`
  )
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
