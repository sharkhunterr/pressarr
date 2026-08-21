/**
 * Detail block for a wanted_search pipeline run.
 *
 * Rendu :
 *   - Bandeau winner (titre + confidence + éligibilité auto-grab)
 *   - Stat tiles pipeline (bruts / après rules / actifs / durée)
 *   - Panels IA + auto-grab
 *   - Table candidats actifs avec breakdown scores/verdicts
 *   - Table candidats rejetés (rule / blocklist)
 *
 * Utilisé par :
 *   - HistoryDetailModal (event `searched` avec nouveau payload)
 *   - WantedSearchNowModal (bouton "Recherche maintenant" sur issue)
 *
 * Le composant ne fait aucune requête réseau — juste render un
 * WantedSearchResultDTO passé en prop.
 */

// Ré-exporte les types depuis le module dédié pour que les callers
// n'aient qu'un seul import.
export interface WantedSearchCandidate {
  guid: string
  title: string
  indexer: string
  quality: string
  size: number
  seeders: number | null
  python_score: number
  rules_verdict: 'included' | 'excluded' | 'neutral'
  rules_reason: string | null
  is_blocklisted: boolean
  ai_verdict: 'picked' | 'not_picked' | 'vetoed' | 'skipped'
  ai_confidence: number | null
  ai_reason: string | null
  final_score: number
  is_winner: boolean
  dropped_reason: string | null
  matched_queries?: string[]
}

export interface WantedSearchWinner {
  guid: string
  title: string
  confidence: number
  python_score: number
  ai_verdict: string
  ai_confidence: number | null
  indexer: string
  quality: string
  auto_grab_eligible: boolean
}

function scoreColor(score: number): string {
  if (score >= 78) return 'text-emerald-400'
  if (score >= 60) return 'text-amber-400'
  return 'text-zinc-500'
}

function verdictBadge(verdict: string): { label: string; cls: string } {
  switch (verdict) {
    case 'picked':
      return { label: 'IA ✓', cls: 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30' }
    case 'vetoed':
      return { label: 'IA veto', cls: 'bg-red-500/20 text-red-300 border border-red-500/30' }
    case 'not_picked':
      return { label: 'IA –', cls: 'bg-zinc-800 text-zinc-400 border border-zinc-700' }
    case 'skipped':
    default:
      return { label: 'IA off', cls: 'bg-zinc-900 text-zinc-500 border border-zinc-800' }
  }
}

function rulesBadge(verdict: string): { label: string; cls: string } | null {
  if (verdict === 'excluded') return { label: 'exclu', cls: 'bg-red-500/20 text-red-300 border border-red-500/30' }
  if (verdict === 'included') return { label: 'inclus', cls: 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30' }
  return null
}

export interface WantedSearchDetailProps {
  data: Record<string, unknown>
}

export function WantedSearchDetail({ data }: WantedSearchDetailProps) {
  const candidates = (data.candidates as WantedSearchCandidate[]) || []
  const winner = data.winner as WantedSearchWinner | null | undefined
  const totals = data.totals as {
    raw?: number
    after_rules?: number
    after_blocklist?: number
    candidates_persisted?: number
  } | undefined
  const ai = data.ai as {
    used?: boolean
    mode?: string | null
    run_id?: number | null
  } | undefined
  const autoGrab = data.auto_grab as {
    threshold?: number
    eligible?: boolean
    attempted?: boolean
    success?: boolean | null
    message?: string | null
  } | undefined
  const elapsed = data.elapsed_ms as number | undefined

  // Le POST /search/wanted/:id retourne un payload plat sans les nesting
  // que le history event a. Fallback : construire les blocs à partir des
  // champs racine si totals/ai/auto_grab sont absents.
  const totalsResolved = totals ?? {
    raw: data.total_raw as number | undefined,
    after_rules: data.total_after_rules as number | undefined,
    after_blocklist: data.total_after_blocklist as number | undefined,
  }
  const aiResolved = ai ?? {
    used: data.ai_used as boolean | undefined,
    mode: data.ai_mode as string | null | undefined,
    run_id: data.ai_run_id as number | null | undefined,
  }
  const autoGrabResolved = autoGrab ?? {
    threshold: data.auto_grab_threshold as number | undefined,
    eligible: data.auto_grab_eligible as boolean | undefined,
    attempted: data.auto_grab_attempted as boolean | undefined,
    success: data.auto_grab_success as boolean | null | undefined,
    message: data.auto_grab_message as string | null | undefined,
  }
  // Winner peut être null (aucun candidat) OU construit depuis les
  // champs racine (winner_guid, winner_title, winner_confidence).
  const winnerResolved: WantedSearchWinner | null = winner
    ? winner
    : data.winner_guid && data.winner_title
      ? {
          guid: data.winner_guid as string,
          title: data.winner_title as string,
          confidence: (data.winner_confidence as number) ?? 0,
          python_score: 0,
          ai_verdict: '',
          ai_confidence: null,
          indexer: '',
          quality: '',
          auto_grab_eligible: !!autoGrabResolved.eligible,
        }
      : null

  const dropped = candidates.filter((c) => c.dropped_reason)
  const active = candidates.filter((c) => !c.dropped_reason)

  return (
    <div className="space-y-3">
      {/* Bandeau winner */}
      {winnerResolved && (
        <div className="rounded-lg border border-purple-500/30 bg-purple-500/5 p-3">
          <div className="flex items-center gap-2 text-xs uppercase tracking-wide text-purple-300 mb-1">
            <span>Winner</span>
            <span className={`font-mono ${scoreColor(winnerResolved.confidence)}`}>
              {winnerResolved.confidence.toFixed(1)}%
            </span>
            {winnerResolved.auto_grab_eligible && (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                éligible auto-grab
              </span>
            )}
          </div>
          <div className="text-sm text-zinc-100 break-all">{winnerResolved.title}</div>
          {winnerResolved.indexer && (
            <div className="text-xs text-zinc-500 mt-1 flex flex-wrap gap-x-3 gap-y-0.5">
              <span>indexer: {winnerResolved.indexer}</span>
              <span>qualité: {winnerResolved.quality}</span>
              <span>python: {winnerResolved.python_score.toFixed(1)}</span>
              <span>
                IA: {winnerResolved.ai_verdict}
                {winnerResolved.ai_confidence != null
                  ? ` (${(winnerResolved.ai_confidence * 100).toFixed(0)}%)`
                  : ''}
              </span>
            </div>
          )}
        </div>
      )}
      {!winnerResolved && candidates.length > 0 && (
        <div className="rounded border border-amber-500/30 bg-amber-500/5 p-3 text-xs text-amber-200">
          Aucun winner (tous les candidats ont été filtrés par rules/blocklist).
        </div>
      )}
      {!winnerResolved && candidates.length === 0 && (
        <div className="rounded border border-zinc-800 bg-zinc-900/40 p-3 text-xs text-zinc-500">
          Aucun candidat trouvé sur les indexers.
        </div>
      )}

      {/* Queries envoyées à Prowlarr */}
      {Array.isArray(data.queries) && (data.queries as string[]).length > 0 && (
        <div className="rounded border border-zinc-800 bg-zinc-900/40 p-2.5">
          <div className="text-[10px] uppercase tracking-wide text-zinc-500 mb-1.5">
            Queries envoyées à Prowlarr ({(data.queries as string[]).length})
          </div>
          <div className="flex flex-wrap gap-1">
            {(data.queries as string[]).map((q, i) => (
              <span
                key={i}
                className="text-[11px] font-mono px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-300 border border-zinc-700"
              >
                {q}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Stats pipeline */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        <StatTile label="Bruts" value={totalsResolved?.raw ?? 0} />
        <StatTile label="Après rules" value={totalsResolved?.after_rules ?? 0} />
        <StatTile label="Actifs" value={totalsResolved?.after_blocklist ?? 0} />
        <StatTile
          label="Durée"
          value={elapsed != null ? `${(elapsed / 1000).toFixed(1)}s` : '—'}
        />
      </div>

      {/* IA + auto-grab */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        <div className="rounded border border-zinc-800 bg-zinc-900/40 p-2.5 text-xs">
          <div className="text-zinc-500 uppercase tracking-wide mb-1">IA ranker</div>
          {aiResolved?.used ? (
            <div className="space-y-0.5">
              <div className="text-zinc-200">
                Actif · mode <span className="font-mono">{aiResolved.mode ?? '?'}</span>
              </div>
              {aiResolved.run_id != null && (
                <div className="text-zinc-500 font-mono">run #{aiResolved.run_id}</div>
              )}
            </div>
          ) : (
            <div className="text-zinc-500">Désactivée ou skippée (≤ 1 candidat)</div>
          )}
        </div>
        <div className="rounded border border-zinc-800 bg-zinc-900/40 p-2.5 text-xs">
          <div className="text-zinc-500 uppercase tracking-wide mb-1">Auto-grab</div>
          <div className="space-y-0.5">
            <div className="text-zinc-400">
              Seuil{' '}
              <span className="font-mono">
                {autoGrabResolved?.threshold?.toFixed(0) ?? '78'}%
              </span>
              {' · '}
              {autoGrabResolved?.eligible ? (
                <span className="text-emerald-400">éligible</span>
              ) : (
                <span className="text-zinc-500">sous seuil</span>
              )}
            </div>
            {autoGrabResolved?.attempted && (
              <div className={autoGrabResolved.success ? 'text-emerald-400' : 'text-red-400'}>
                {autoGrabResolved.success ? '✓ grab réussi' : '✕ grab échoué'}
                {autoGrabResolved.message && (
                  <span className="text-zinc-500 ml-1 font-mono text-[10px]">
                    {autoGrabResolved.message}
                  </span>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Table candidats actifs */}
      {active.length > 0 && (
        <div>
          <h4 className="text-xs font-medium text-zinc-400 uppercase tracking-wide mb-2">
            Candidats ({active.length})
          </h4>
          <div className="rounded border border-zinc-800 overflow-hidden overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="bg-zinc-900/50 text-zinc-500">
                  <th className="text-left px-2 py-1.5 font-medium">Titre</th>
                  <th className="text-left px-2 py-1.5 font-medium">Indexer</th>
                  <th className="text-left px-2 py-1.5 font-medium">Qualité</th>
                  <th className="text-right px-2 py-1.5 font-medium">Seeds</th>
                  <th className="text-right px-2 py-1.5 font-medium">Python</th>
                  <th className="text-center px-2 py-1.5 font-medium">Rules</th>
                  <th className="text-center px-2 py-1.5 font-medium">IA</th>
                  <th className="text-right px-2 py-1.5 font-medium">Final %</th>
                </tr>
              </thead>
              <tbody>
                {active.map((c, i) => {
                  const vb = verdictBadge(c.ai_verdict)
                  const rb = rulesBadge(c.rules_verdict)
                  return (
                    <tr
                      key={c.guid || i}
                      className={`border-t border-zinc-800/50 hover:bg-zinc-900/30 ${
                        c.is_winner ? 'bg-purple-500/5' : ''
                      }`}
                    >
                      <td
                        className="px-2 py-1.5 text-zinc-200 max-w-[280px] truncate"
                        title={
                          c.matched_queries && c.matched_queries.length > 0
                            ? `${c.title}\n\nRemonté via :\n${c.matched_queries.map((q) => `  • ${q}`).join('\n')}`
                            : c.title
                        }
                      >
                        {c.is_winner && <span className="text-purple-400 mr-1">★</span>}
                        {c.title}
                        {c.matched_queries && c.matched_queries.length > 1 && (
                          <span className="ml-1 text-[9px] text-zinc-500 align-top">
                            ×{c.matched_queries.length}
                          </span>
                        )}
                      </td>
                      <td className="px-2 py-1.5 text-zinc-400">{c.indexer}</td>
                      <td className="px-2 py-1.5 text-zinc-400">{c.quality}</td>
                      <td className="px-2 py-1.5 text-zinc-400 text-right">{c.seeders ?? '-'}</td>
                      <td className="px-2 py-1.5 text-zinc-300 text-right font-mono">
                        {c.python_score.toFixed(1)}
                      </td>
                      <td className="px-2 py-1.5 text-center">
                        {rb ? (
                          <span className={`text-[10px] px-1.5 py-0.5 rounded ${rb.cls}`}>
                            {rb.label}
                          </span>
                        ) : (
                          <span className="text-zinc-600">–</span>
                        )}
                      </td>
                      <td className="px-2 py-1.5 text-center">
                        <span
                          className={`text-[10px] px-1.5 py-0.5 rounded ${vb.cls}`}
                          title={c.ai_reason ?? undefined}
                        >
                          {vb.label}
                          {c.ai_confidence != null && (
                            <span className="ml-1 opacity-70">
                              {(c.ai_confidence * 100).toFixed(0)}%
                            </span>
                          )}
                        </span>
                      </td>
                      <td className={`px-2 py-1.5 text-right font-mono ${scoreColor(c.final_score)}`}>
                        {c.final_score.toFixed(1)}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Candidats droppés */}
      {dropped.length > 0 && (
        <div>
          <h4 className="text-xs font-medium text-zinc-500 uppercase tracking-wide mb-2">
            Rejetés ({dropped.length})
          </h4>
          <div className="rounded border border-zinc-800/60 overflow-hidden overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="bg-zinc-950 text-zinc-600">
                  <th className="text-left px-2 py-1.5 font-medium">Titre</th>
                  <th className="text-left px-2 py-1.5 font-medium">Raison</th>
                  <th className="text-right px-2 py-1.5 font-medium">Python</th>
                </tr>
              </thead>
              <tbody>
                {dropped.map((c, i) => (
                  <tr key={c.guid || i} className="border-t border-zinc-800/40 opacity-60">
                    <td className="px-2 py-1.5 text-zinc-400 max-w-[300px] truncate" title={c.title}>
                      {c.title}
                    </td>
                    <td
                      className="px-2 py-1.5 text-red-400 max-w-[200px] truncate"
                      title={c.dropped_reason ?? undefined}
                    >
                      {c.dropped_reason}
                    </td>
                    <td className="px-2 py-1.5 text-zinc-500 text-right font-mono">
                      {c.python_score.toFixed(1)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

function StatTile({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded border border-zinc-800 bg-zinc-900/40 p-2 text-center">
      <div className="text-[10px] uppercase tracking-wide text-zinc-500">{label}</div>
      <div className="text-lg font-mono text-zinc-100 tabular-nums">{value}</div>
    </div>
  )
}
