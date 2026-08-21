import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Save,
  RefreshCw,
  Loader2,
  CheckCircle2,
  XCircle,
  Sparkles,
  FlaskConical,
  Info,
} from 'lucide-react'
import { toast } from 'sonner'

import {
  getAISettings,
  probeOllamaModels,
  probePythonOCREngines,
  saveAISettings,
  type AISettings,
  type OllamaModelsProbe,
  type PythonOCRProbeEntry,
} from '@/api/ai'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'

/** Local editable copy — every field non-optional so React inputs
 *  stay controlled. Populated from the server via `useEffect`, dumped
 *  back on Save. */
type LocalState = AISettings

const DEFAULT: LocalState = {
  ollamaUrl: 'http://localhost:11434',
  ollamaTimeoutS: 300,
  enrichmentEnabled: false,
  enrichmentMode: 'remplace',
  enrichmentVisionPages: [1],
  enrichmentVisionCrop: 'full',
  pythonOcrEnabled: true,
  pythonOcrEngine: 'easyocr',
  textModel: 'mistral:7b',
  visionModel: 'minicpm-v:8b',
  torrentModel: null,
  arbiterModel: null,
  textPrompt: '',
  visionPrompt: '',
  arbiterPrompt: '',
  rankerEnabled: false,
  rankerMode: 'ai_advisory',
  rankerBatchSize: 5,
  rankerTopK: 15,
  rankerConfidenceThreshold: 0.6,
  rankerPrompt: '',
  wantedSearchEnabled: true,
  wantedSearchAutoGrabEnabled: false,
  wantedSearchAutoGrabThreshold: 78,
  wantedSearchMinTitleMatch: 60,
  wantedSearchIntervalMinutes: 240,
  wantedSearchCooldownHours: 12,
  wantedSearchMaxPerCycle: 30,
  wantedSearchQueryTemplates: [
    '{title} N{number}',
    '{title} N°{number}',
    '{title} #{number}',
    '{title} {year} {month_pad} {day_pad}',
    '{title} {day_pad} {month_pad} {year}',
    '{title} {day_pad}-{month_pad}-{year}',
    '{title} {day_pad}/{month_pad}/{year}',
    '{title} {month_pad}-{day_pad}-{year}',
    '{title} {day_pad} {month_fr} {year}',
    '{title} {day_pad} {month_en} {year}',
    '{title} {month_fr} {year}',
  ],
}

export default function AISettingsPage() {
  const qc = useQueryClient()
  const [local, setLocal] = useState<LocalState>(DEFAULT)
  const [pagesStr, setPagesStr] = useState('1')
  const [probe, setProbe] = useState<OllamaModelsProbe | null>(null)
  const [probing, setProbing] = useState(false)

  const { data: serverSettings, isLoading } = useQuery({
    queryKey: ['aiSettings'],
    queryFn: getAISettings,
  })

  // Sync server → local exactly once when the query resolves. Using
  // `select` for this side-effect caused an infinite render loop
  // (setState inside render). useEffect isolates it to post-render.
  const [initialised, setInitialised] = useState(false)
  useEffect(() => {
    if (!serverSettings || initialised) return
    setLocal(serverSettings)
    setPagesStr((serverSettings.enrichmentVisionPages ?? [1]).join(', '))
    setInitialised(true)
    // Pas d'auto-probe au load — le probe est distant, prend
    // ~500 ms et bloque la page. L'utilisateur clique « Test »
    // quand il veut vérifier la connexion.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [serverSettings, initialised])

  async function runProbe(url?: string) {
    setProbing(true)
    try {
      const p = await probeOllamaModels(url ?? local.ollamaUrl)
      setProbe(p)
    } catch (e) {
      setProbe({
        reachable: false,
        url: url ?? local.ollamaUrl,
        models: [],
        error: (e as Error).message,
      })
    } finally {
      setProbing(false)
    }
  }

  const saveMutation = useMutation({
    mutationFn: (payload: Partial<AISettings>) => saveAISettings(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['aiSettings'] })
      toast.success('Paramètres IA enregistrés')
      // Pas de re-probe automatique — l'utilisateur clique
      // « Test » s'il veut vérifier après un changement d'URL.
    },
    onError: (e: Error) => toast.error(`Erreur: ${e.message}`),
  })

  function commit() {
    const pages = pagesStr
      .split(',')
      .map((x) => x.trim())
      .filter((x) => x !== '')
      .map((x) => Number(x))
      .filter((n) => Number.isInteger(n) && n !== 0)
    saveMutation.mutate({ ...local, enrichmentVisionPages: pages })
  }

  const models = probe?.models ?? []
  const reachable = probe?.reachable ?? false

  if (isLoading) {
    return (
      <div className="p-4 lg:p-8 text-zinc-400">Chargement…</div>
    )
  }

  return (
    <div className="p-4 lg:p-8">
      {/* --- Page header --------------------------------------- */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Sparkles className="size-6 text-purple-400" />
          <h1 className="text-2xl font-bold text-zinc-100">
            Intelligence Artificielle
          </h1>
        </div>
        <Button onClick={commit} disabled={saveMutation.isPending}>
          {saveMutation.isPending ? (
            <Loader2 className="size-4 animate-spin" />
          ) : (
            <Save className="size-4" />
          )}
          Enregistrer
        </Button>
      </div>

      <p className="text-sm text-zinc-400 mb-6">
        Enrichissement automatique des métadonnées via un LLM local
        (Ollama) et ranking des résultats de recherche. Toutes les
        données restent chez toi.
      </p>

      <div className="grid gap-6">
        {/* --- Ollama connection ------------------------------ */}
        <Card className="bg-zinc-950 border-zinc-800">
          <CardHeader>
            <CardTitle className="text-zinc-100">Serveur Ollama</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-1.5">
              <label className="text-sm font-medium text-zinc-300">
                URL du serveur
              </label>
              <Input
                value={local.ollamaUrl}
                onChange={(e) => setLocal({ ...local, ollamaUrl: e.target.value })}
                placeholder="http://192.168.1.24:11434"
                className="bg-zinc-900 border-zinc-700 text-zinc-100"
              />
              <p className="text-xs text-zinc-500">
                Les modèles doivent être installés avec{' '}
                <code className="text-zinc-300 bg-zinc-900 px-1 py-0.5 rounded">
                  ollama pull &lt;nom&gt;
                </code>
              </p>
            </div>

            <div className="grid gap-1.5">
              <label className="text-sm font-medium text-zinc-300">
                Timeout par appel (secondes)
              </label>
              <Input
                type="number"
                value={local.ollamaTimeoutS}
                onChange={(e) =>
                  setLocal({ ...local, ollamaTimeoutS: Number(e.target.value) })
                }
                className="bg-zinc-900 border-zinc-700 text-zinc-100 w-40"
              />
            </div>

            <div className="flex items-center gap-3">
              <Button
                variant="outline"
                onClick={() => runProbe(local.ollamaUrl)}
                disabled={probing}
              >
                {probing ? (
                  <Loader2 className="size-4 animate-spin" />
                ) : (
                  <FlaskConical className="size-4" />
                )}
                Tester la connexion
              </Button>

              {probe && (
                <div className="flex items-center gap-2 text-sm">
                  {reachable ? (
                    <>
                      <CheckCircle2 className="size-4 text-emerald-400" />
                      <span className="text-zinc-300">
                        {models.length} modèle{models.length !== 1 && 's'} détecté
                        {models.length !== 1 && 's'}
                      </span>
                    </>
                  ) : (
                    <>
                      <XCircle className="size-4 text-rose-400" />
                      <span className="text-zinc-300">
                        Injoignable — {probe.error ?? 'aucune réponse'}
                      </span>
                    </>
                  )}
                </div>
              )}
            </div>

            {reachable && models.length > 0 && (
              <div className="rounded border border-zinc-800 bg-zinc-900/40 p-3">
                <div className="text-xs uppercase tracking-wide text-zinc-500 mb-2">
                  Modèles disponibles
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {models.map((m) => (
                    <span
                      key={m}
                      className="text-xs px-2 py-1 rounded bg-zinc-800 text-zinc-300 font-mono"
                    >
                      {m}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* --- Enrichment ------------------------------------- */}
        <Card className="bg-zinc-950 border-zinc-800">
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="text-zinc-100">
                Enrichissement des métadonnées
              </CardTitle>
              <Switch
                checked={local.enrichmentEnabled}
                onCheckedChange={(v) =>
                  setLocal({ ...local, enrichmentEnabled: v === true })
                }
              />
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-xs text-zinc-500 -mt-2">
              Pipeline séquentiel : nom du torrent → LLM texte → OCR
              vision de la couverture → arbitre qui fusionne.
            </p>

            <div className="grid sm:grid-cols-2 gap-4">
              <div className="grid gap-1.5">
                <label className="text-sm font-medium text-zinc-300">
                  Modèle par défaut (fallback)
                </label>
                <ModelSelect
                  value={local.textModel}
                  onChange={(v) => setLocal({ ...local, textModel: v })}
                  models={models}
                  placeholder="mistral:7b"
                />
                <p className="text-xs text-zinc-500">
                  Utilisé pour l'analyse torrent et l'arbitre quand les
                  champs par-étape ci-dessous restent vides.
                </p>
              </div>
              <div className="grid gap-1.5">
                <label className="text-sm font-medium text-zinc-300">
                  Modèle vision (OCR couverture)
                </label>
                <ModelSelect
                  value={local.visionModel}
                  onChange={(v) => setLocal({ ...local, visionModel: v })}
                  models={models}
                  placeholder="minicpm-v:8b"
                />
              </div>
            </div>

            {/* Per-step overrides. Vide → tombe sur le modèle par
                défaut ci-dessus. Séparer les modèles permet de mettre
                un gros modèle sur l'arbitre (qwen3:8b) et garder un
                modèle rapide pour l'analyse torrent (mistral:7b). */}
            <div className="grid sm:grid-cols-2 gap-4">
              <div className="grid gap-1.5">
                <label className="text-sm font-medium text-zinc-300">
                  Modèle « analyse nom torrent » (override)
                </label>
                <OverrideModelSelect
                  value={local.torrentModel}
                  onChange={(v) => setLocal({ ...local, torrentModel: v })}
                  models={models}
                  fallback={local.textModel}
                />
                <p className="text-xs text-zinc-500">
                  Peut rester « défaut ». Tâche courte, un modèle
                  rapide suffit (mistral:7b).
                </p>
              </div>
              <div className="grid gap-1.5">
                <label className="text-sm font-medium text-zinc-300">
                  Modèle « arbiter » (override)
                </label>
                <OverrideModelSelect
                  value={local.arbiterModel}
                  onChange={(v) => setLocal({ ...local, arbiterModel: v })}
                  models={models}
                  fallback={local.textModel}
                />
                <p className="text-xs text-zinc-500">
                  Voit toutes les sources et tranche. Un « gros »
                  modèle (qwen3:8b, gemma3:12b) donne un meilleur
                  arbitrage.
                </p>
              </div>
            </div>

            <div className="grid sm:grid-cols-2 gap-4">
              <div className="grid gap-1.5">
                <label className="text-sm font-medium text-zinc-300">
                  Autorité — que fait l'IA de son résultat
                </label>
                <Select
                  value={local.enrichmentMode}
                  onValueChange={(v: 'remplace' | 'complete' | 'propose') =>
                    setLocal({ ...local, enrichmentMode: v })
                  }
                >
                  <SelectTrigger className="bg-zinc-900 border-zinc-700 text-zinc-100">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="remplace">
                      Remplace — écrase les valeurs existantes
                    </SelectItem>
                    <SelectItem value="complete">
                      Complète — remplit uniquement les champs vides
                    </SelectItem>
                    <SelectItem value="propose">
                      Propose — validation manuelle requise
                    </SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="grid gap-1.5">
                <label className="text-sm font-medium text-zinc-300">
                  Pages à envoyer au vision
                </label>
                <Input
                  value={pagesStr}
                  onChange={(e) => setPagesStr(e.target.value)}
                  placeholder="1, -1"
                  className="bg-zinc-900 border-zinc-700 text-zinc-100"
                />
                <p className="text-xs text-zinc-500">
                  Séparé par virgules. Négatif = compte depuis la fin
                  (<code>-1</code> = dernière page). Ex.{' '}
                  <code>1, -1</code> = couverture + dos.
                </p>
              </div>
            </div>

            {/* Crop zone : chaque layout de magazine met le N° à un endroit
                différent. L'user choisit selon son cas. */}
            <div className="grid gap-1.5">
              <label className="text-sm font-medium text-zinc-300">
                Zone envoyée au vision LLM
              </label>
              <Select
                value={local.enrichmentVisionCrop}
                onValueChange={(v: 'full' | 'top' | 'bottom' | 'top_bottom') =>
                  setLocal({ ...local, enrichmentVisionCrop: v })
                }
              >
                <SelectTrigger className="bg-zinc-900 border-zinc-700 text-zinc-100">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="full">
                    Page entière — safe pour tout, moins précis
                  </SelectItem>
                  <SelectItem value="top">
                    Haut 45 % — quotidiens FR (L'Équipe, Le Figaro, Le Monde)
                  </SelectItem>
                  <SelectItem value="bottom">
                    Bas 45 % — rare
                  </SelectItem>
                  <SelectItem value="top_bottom">
                    Haut + Bas (2 appels) — robuste, plus lent
                  </SelectItem>
                </SelectContent>
              </Select>
              <p className="text-xs text-zinc-500">
                Le layout diffère par magazine : les quotidiens FR ont le
                N° sous le titre (haut), certains mensuels (GEO, Sciences &
                Vie) ont le N° en pied de couverture. Le mode{' '}
                <code>top_bottom</code> couvre les deux mais double le
                temps d'inférence.
              </p>
            </div>

            {/* Python OCR : 3ᵉ source d'extraction texte, deterministic. */}
            <PythonOCRPicker
              enabled={local.pythonOcrEnabled}
              engine={local.pythonOcrEngine}
              onToggle={(v) => setLocal({ ...local, pythonOcrEnabled: v })}
              onEngineChange={(e) => setLocal({ ...local, pythonOcrEngine: e })}
            />

            <PromptField
              label="Prompt LLM texte (analyse du nom torrent)"
              value={local.textPrompt}
              onChange={(v) => setLocal({ ...local, textPrompt: v })}
            />
            <PromptField
              label="Prompt LLM vision (OCR de la couverture)"
              value={local.visionPrompt}
              onChange={(v) => setLocal({ ...local, visionPrompt: v })}
            />
            <PromptField
              label="Prompt arbitre (fusion torrent + vision)"
              value={local.arbiterPrompt}
              onChange={(v) => setLocal({ ...local, arbiterPrompt: v })}
              rows={7}
            />
          </CardContent>
        </Card>

        {/* --- Ranker ----------------------------------------- */}
        <Card className="bg-zinc-950 border-zinc-800">
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="text-zinc-100">
                Ranker recherche
              </CardTitle>
              <Switch
                checked={local.rankerEnabled}
                onCheckedChange={(v) =>
                  setLocal({ ...local, rankerEnabled: v === true })
                }
              />
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-xs text-zinc-500 -mt-2">
              Envoie les candidats de la recherche à l'IA par petits
              batches et laisse choisir la meilleure correspondance.
              Utilise le même modèle texte que l'enrichissement.
            </p>

            <div className="rounded border border-zinc-800 bg-zinc-900/40 p-3 flex items-start gap-2">
              <Info className="size-4 text-blue-400 shrink-0 mt-0.5" />
              <p className="text-xs text-zinc-400">
                Recommandé : commencer en mode <strong>Observation</strong>{' '}
                pour voir les décisions de l'IA dans l'historique avant
                de basculer sur <strong>IA tranche</strong>.
              </p>
            </div>

            <div className="grid gap-1.5">
              <label className="text-sm font-medium text-zinc-300">
                Autorité du ranker
              </label>
              <Select
                value={local.rankerMode}
                onValueChange={(v: 'ai_wins' | 'ai_veto_only' | 'ai_advisory') =>
                  setLocal({ ...local, rankerMode: v })
                }
              >
                <SelectTrigger className="bg-zinc-900 border-zinc-700 text-zinc-100">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="ai_advisory">
                    Observation — log seul, aucune influence
                  </SelectItem>
                  <SelectItem value="ai_veto_only">
                    Veto — l'IA peut refuser le top scorer
                  </SelectItem>
                  <SelectItem value="ai_wins">
                    IA tranche — pick de l'IA prioritaire
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="grid sm:grid-cols-3 gap-4">
              <div className="grid gap-1.5">
                <label className="text-sm font-medium text-zinc-300">
                  Batch size
                </label>
                <Input
                  type="number"
                  min={2}
                  max={20}
                  value={local.rankerBatchSize}
                  onChange={(e) =>
                    setLocal({ ...local, rankerBatchSize: Number(e.target.value) })
                  }
                  className="bg-zinc-900 border-zinc-700 text-zinc-100"
                />
              </div>
              <div className="grid gap-1.5">
                <label className="text-sm font-medium text-zinc-300">
                  Top-K envoyé à l'IA
                </label>
                <Input
                  type="number"
                  min={1}
                  max={100}
                  value={local.rankerTopK}
                  onChange={(e) =>
                    setLocal({ ...local, rankerTopK: Number(e.target.value) })
                  }
                  className="bg-zinc-900 border-zinc-700 text-zinc-100"
                />
              </div>
              <div className="grid gap-1.5">
                <label className="text-sm font-medium text-zinc-300">
                  Seuil de confiance
                </label>
                <Input
                  type="number"
                  step="0.05"
                  min={0}
                  max={1}
                  value={local.rankerConfidenceThreshold}
                  onChange={(e) =>
                    setLocal({
                      ...local,
                      rankerConfidenceThreshold: Number(e.target.value),
                    })
                  }
                  className="bg-zinc-900 border-zinc-700 text-zinc-100"
                />
              </div>
            </div>

            <PromptField
              label="Prompt du ranker"
              value={local.rankerPrompt}
              onChange={(v) => setLocal({ ...local, rankerPrompt: v })}
              rows={7}
            />
          </CardContent>
        </Card>

        {/* --- Wanted search pipeline -------------------------- */}
        <Card className="bg-zinc-950 border-zinc-800">
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="text-zinc-100">
                Recherche wanted (auto)
              </CardTitle>
              <Switch
                checked={local.wantedSearchEnabled}
                onCheckedChange={(v) =>
                  setLocal({ ...local, wantedSearchEnabled: v === true })
                }
              />
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-xs text-zinc-500 -mt-2">
              Pipeline unifié Prowlarr → scoring Python → rules
              include/exclude → IA batch + arbitre (utilise le ranker
              ci-dessus) → composite score → auto-grab si winner ≥ seuil.
              Toggle OFF désactive le scheduler périodique + les
              auto-triggers à la création d'issue wanted.
            </p>

            <div className="rounded border border-zinc-800 bg-zinc-900/40 p-3 flex items-start gap-2">
              <Info className="size-4 text-blue-400 shrink-0 mt-0.5" />
              <p className="text-xs text-zinc-400">
                Les recherches <strong>manuelles</strong> (bouton
                « Recherche maintenant » sur une issue) restent
                possibles même toggle OFF — utile pour tester ou faire
                du one-shot sans laisser tourner l'automatisme.
              </p>
            </div>

            <div className="flex items-center justify-between border-t border-zinc-800 pt-4">
              <div className="flex-1 pr-3">
                <label className="text-sm font-medium text-zinc-300 block">
                  Auto-grab automatique
                </label>
                <p className="text-xs text-zinc-500 mt-0.5">
                  <strong className="text-amber-400">OFF par défaut (recommandé)</strong>{' '}
                  — quand ON, un winner qui passe le seuil est envoyé au client
                  de téléchargement sans intervention. Assure-toi d'avoir des
                  <em> rules include/exclude</em> solides sur tes magazines
                  avant d'activer. Sans auto-grab, le pipeline continue de
                  chercher + logguer mais ne grab rien tout seul.
                </p>
              </div>
              <Switch
                checked={local.wantedSearchAutoGrabEnabled}
                onCheckedChange={(v) =>
                  setLocal({ ...local, wantedSearchAutoGrabEnabled: v === true })
                }
              />
            </div>

            <div className="grid gap-1.5">
              <label className="text-sm font-medium text-zinc-300">
                Seuil auto-grab (%)
              </label>
              <Input
                type="number"
                step="1"
                min={0}
                max={100}
                value={local.wantedSearchAutoGrabThreshold}
                onChange={(e) =>
                  setLocal({
                    ...local,
                    wantedSearchAutoGrabThreshold: Number(e.target.value),
                  })
                }
                disabled={!local.wantedSearchAutoGrabEnabled}
                className="bg-zinc-900 border-zinc-700 text-zinc-100"
              />
              <p className="text-xs text-zinc-500">
                Au-dessus de ce score composite (Python + IA), le
                winner est envoyé au client de téléchargement
                automatiquement. Défaut 78% — aligné sur le seuil
                dispatch de pack.
              </p>
            </div>

            <div className="grid gap-1.5">
              <label className="text-sm font-medium text-zinc-300">
                Plancher fuzzy titre release (%)
              </label>
              <Input
                type="number"
                step="1"
                min={0}
                max={100}
                value={local.wantedSearchMinTitleMatch}
                onChange={(e) =>
                  setLocal({
                    ...local,
                    wantedSearchMinTitleMatch: Number(e.target.value),
                  })
                }
                disabled={!local.wantedSearchAutoGrabEnabled}
                className="bg-zinc-900 border-zinc-700 text-zinc-100"
              />
              <p className="text-xs text-zinc-500">
                Garde-fou indépendant du composite : le titre du release
                doit fuzzy-matcher le titre magazine à ≥ ce plancher.
                Empêche l'IA d'auto-grab un release off-topic (ex.
                "Le Figaro Magazine" pour "Le Monde") même à confidence
                1.0. Défaut 60%.
              </p>
            </div>

            <div className="border-t border-zinc-800 pt-4 space-y-4">
              <div className="text-xs uppercase tracking-wide text-zinc-500">
                Cadence
              </div>

              <div className="grid gap-1.5">
                <label className="text-sm font-medium text-zinc-300">
                  Intervalle du scheduler (minutes)
                </label>
                <Input
                  type="number"
                  step="1"
                  min={1}
                  max={10080}
                  value={local.wantedSearchIntervalMinutes}
                  onChange={(e) =>
                    setLocal({
                      ...local,
                      wantedSearchIntervalMinutes: Number(e.target.value),
                    })
                  }
                  disabled={!local.wantedSearchEnabled}
                  className="bg-zinc-900 border-zinc-700 text-zinc-100"
                />
                <p className="text-xs text-zinc-500">
                  Toutes les X minutes, le scheduler passe en revue les
                  issues wanted et lance le pipeline. Défaut{' '}
                  <strong>240 min (4h)</strong>. Reschedule appliqué à
                  chaud au save — pas besoin de restart. Repères :
                  60 = agressif, 240 = équilibré, 720 = 2×/jour.
                </p>
              </div>

              <div className="grid gap-1.5">
                <label className="text-sm font-medium text-zinc-300">
                  Cooldown par-issue (heures)
                </label>
                <Input
                  type="number"
                  step="1"
                  min={0}
                  max={720}
                  value={local.wantedSearchCooldownHours}
                  onChange={(e) =>
                    setLocal({
                      ...local,
                      wantedSearchCooldownHours: Number(e.target.value),
                    })
                  }
                  disabled={!local.wantedSearchEnabled}
                  className="bg-zinc-900 border-zinc-700 text-zinc-100"
                />
                <p className="text-xs text-zinc-500">
                  Une issue déjà scannée n'est re-picked qu'après ce
                  délai (via <code>last_searched_at</code>). Découplé
                  de l'intervalle scheduler : tu peux scan souvent mais
                  chaque issue rare. Défaut 12h. 0 = pas de cooldown
                  (à chaque cycle).
                </p>
              </div>

              <div className="grid gap-1.5">
                <label className="text-sm font-medium text-zinc-300">
                  Cap issues par cycle
                </label>
                <Input
                  type="number"
                  step="1"
                  min={1}
                  max={500}
                  value={local.wantedSearchMaxPerCycle}
                  onChange={(e) =>
                    setLocal({
                      ...local,
                      wantedSearchMaxPerCycle: Number(e.target.value),
                    })
                  }
                  disabled={!local.wantedSearchEnabled}
                  className="bg-zinc-900 border-zinc-700 text-zinc-100"
                />
                <p className="text-xs text-zinc-500">
                  Nombre max d'issues traitées par cycle. Le reste
                  attend le cycle suivant. Défaut 30. Chaque issue coûte
                  30-60s avec IA vision + arbitre — sur un backlog de
                  100+ wanted, un cap bas évite de bloquer Ollama.
                </p>
              </div>
            </div>

            <div className="border-t border-zinc-800 pt-4 space-y-2">
              <div className="text-xs uppercase tracking-wide text-zinc-500">
                Templates de query
              </div>
              <div className="grid gap-1.5">
                <label className="text-sm font-medium text-zinc-300">
                  Formats de recherche envoyés aux indexers
                </label>
                <textarea
                  rows={12}
                  value={local.wantedSearchQueryTemplates.join('\n')}
                  onChange={(e) =>
                    setLocal({
                      ...local,
                      wantedSearchQueryTemplates: e.target.value
                        .split('\n')
                        .map((l) => l.trim())
                        .filter(Boolean),
                    })
                  }
                  disabled={!local.wantedSearchEnabled}
                  className="w-full rounded bg-zinc-900 border border-zinc-700 text-zinc-100 font-mono text-xs p-2 focus:border-purple-500 focus:outline-none"
                  spellCheck={false}
                />
                <p className="text-xs text-zinc-500">
                  <strong>Un template par ligne.</strong> Chaque template
                  dont TOUS les placeholders ont une valeur est rendu et
                  envoyé à Prowlarr — les résultats sont dédupés par GUID.
                  Un template avec <code>{'{number}'}</code> est skippé
                  pour une issue sans numéro (idem pour la date). Multi-
                  format = couvre les conventions d'uploaders variables
                  (FR/EN, dash/slash, mois nommé, etc.).
                </p>
                <p className="text-xs text-zinc-500">
                  <strong>Placeholders</strong> : <code>{'{title}'}</code>{' '}
                  <code>{'{number}'}</code>{' '}
                  <code>{'{year}'}</code>{' '}
                  <code>{'{month}'}</code>{' '}
                  <code>{'{day}'}</code>{' '}
                  <code>{'{month_pad}'}</code> (08){' '}
                  <code>{'{day_pad}'}</code> (02){' '}
                  <code>{'{month_fr}'}</code> (août){' '}
                  <code>{'{month_en}'}</code> (august)
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

/** Prompt editor with consistent styling — textarea that matches
 *  the app's input aesthetic. Isolated so I can tune it once. */
function PromptField({
  label,
  value,
  onChange,
  rows = 5,
}: {
  label: string
  value: string
  onChange: (v: string) => void
  rows?: number
}) {
  return (
    <div className="grid gap-1.5">
      <label className="text-sm font-medium text-zinc-300">{label}</label>
      <textarea
        rows={rows}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-500 font-mono"
      />
    </div>
  )
}

/** Model picker : always a Select when the Ollama probe returned
 *  models. When the current value isn't in the list (e.g. user typed
 *  a model that's not yet pulled), show it as a hint and offer an
 *  "Autre…" option that reveals a raw text input.
 *
 *  When the probe hasn't returned yet (or 0 models), fall back to a
 *  raw input so the user isn't locked out. */
function ModelSelect({
  value,
  onChange,
  models,
  placeholder,
}: {
  value: string
  onChange: (v: string) => void
  models: string[]
  placeholder: string
}) {
  const CUSTOM = '__custom__'
  const inList = models.includes(value)
  const [showCustom, setShowCustom] = useState(false)

  if (models.length === 0) {
    return (
      <div className="grid gap-1">
        <Input
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          className="bg-zinc-900 border-zinc-700 text-zinc-100"
        />
        <p className="text-xs text-zinc-500">
          Aucun modèle détecté — teste la connexion Ollama d'abord.
        </p>
      </div>
    )
  }

  if (showCustom || (!inList && value !== '')) {
    return (
      <div className="grid gap-1">
        <Input
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          className="bg-zinc-900 border-zinc-700 text-zinc-100"
        />
        <div className="flex items-center gap-2 text-xs">
          {!inList && (
            <span className="text-amber-400">
              Ce modèle n'est pas dans la liste — sera considéré manquant
              à l'exécution.
            </span>
          )}
          <button
            type="button"
            className="text-zinc-400 hover:text-zinc-200 underline"
            onClick={() => {
              setShowCustom(false)
              if (!inList && models.length > 0) onChange(models[0])
            }}
          >
            revenir au sélecteur
          </button>
        </div>
      </div>
    )
  }

  return (
    <Select
      value={value}
      onValueChange={(v) => {
        if (v === CUSTOM) {
          setShowCustom(true)
          return
        }
        onChange(v)
      }}
    >
      <SelectTrigger className="bg-zinc-900 border-zinc-700 text-zinc-100">
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent>
        {models.map((m) => (
          <SelectItem key={m} value={m}>
            {m}
          </SelectItem>
        ))}
        <SelectItem value={CUSTOM}>Autre… (saisie libre)</SelectItem>
      </SelectContent>
    </Select>
  )
}


/** Variant de ``ModelSelect`` acceptant ``null`` pour représenter
 *  « pas d'override — fallback sur le modèle par défaut ». Radix
 *  Select refuse les value="" donc on utilise le sentinel ``DEFAULT``. */
function OverrideModelSelect({
  value,
  onChange,
  models,
  fallback,
}: {
  value: string | null
  onChange: (v: string | null) => void
  models: string[]
  fallback: string
}) {
  const DEFAULT = '__default__'
  const current = value ?? DEFAULT
  return (
    <Select
      value={current}
      onValueChange={(v) => onChange(v === DEFAULT ? null : v)}
    >
      <SelectTrigger className="bg-zinc-900 border-zinc-700 text-zinc-100">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value={DEFAULT}>
          — défaut ({fallback || 'aucun'}) —
        </SelectItem>
        {models.map((m) => (
          <SelectItem key={m} value={m}>
            {m}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}


// ---- Python OCR (Tesseract / RapidOCR / EasyOCR) ------------------

const ENGINE_META: Record<
  'tesseract' | 'rapidocr' | 'easyocr',
  { label: string; hint: string }
> = {
  tesseract: {
    label: 'Tesseract',
    hint: 'Rapide (~1 s), léger. Excellent en texte imprimé net, moins bon sur textes stylisés. Nécessite le paquet système tesseract-ocr-fra.',
  },
  rapidocr: {
    label: 'RapidOCR (ONNX)',
    hint: 'Compromis vitesse/précision. Pas d\'install système. Modèles ONNX ~100 MB.',
  },
  easyocr: {
    label: 'EasyOCR (PyTorch)',
    hint: 'Le plus robuste sur textes stylisés / inclinés. Warm-up ~5 s premier appel, cache ensuite.',
  },
}

function PythonOCRPicker({
  enabled,
  engine,
  onToggle,
  onEngineChange,
}: {
  enabled: boolean
  engine: 'tesseract' | 'rapidocr' | 'easyocr'
  onToggle: (v: boolean) => void
  onEngineChange: (e: 'tesseract' | 'rapidocr' | 'easyocr') => void
}) {
  const probeQ = useQuery({
    queryKey: ['pyocr-probe'],
    queryFn: probePythonOCREngines,
    // Cache 5 min — install status ne bouge pas en runtime.
    staleTime: 5 * 60_000,
  })

  return (
    <div className="rounded border border-zinc-800 bg-zinc-900/30 p-3 space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="text-sm text-zinc-100">
            OCR algorithmique (source déterministe)
          </div>
          <div className="text-xs text-zinc-500">
            Tourne sur la MÊME image que l'IA vision. Ne peut pas
            halluciner et corrobore (ou contredit) le vision LLM —
            l'arbiter tranche.
          </div>
        </div>
        <Switch
          checked={enabled}
          onCheckedChange={(v) => onToggle(v === true)}
        />
      </div>

      {enabled && (
        <div className="grid gap-1.5">
          <label className="text-xs font-medium text-zinc-400">
            Moteur
          </label>
          <Select
            value={engine}
            onValueChange={(v: 'tesseract' | 'rapidocr' | 'easyocr') =>
              onEngineChange(v)
            }
          >
            <SelectTrigger className="bg-zinc-900 border-zinc-700 text-zinc-100">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {(['tesseract', 'rapidocr', 'easyocr'] as const).map((key) => {
                const probe = probeQ.data?.find((p) => p.engine === key)
                const avail = probe?.available ?? true
                return (
                  <SelectItem key={key} value={key} disabled={!avail}>
                    {ENGINE_META[key].label}
                    {!avail && ' — indisponible'}
                  </SelectItem>
                )
              })}
            </SelectContent>
          </Select>
          <p className="text-xs text-zinc-500">
            {ENGINE_META[engine].hint}
          </p>
          {probeQ.data && (
            <div className="mt-1 flex flex-wrap gap-1">
              {probeQ.data.map((p: PythonOCRProbeEntry) => (
                <span
                  key={p.engine}
                  className={
                    'inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-[10px] ' +
                    (p.available
                      ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300'
                      : 'border-red-500/30 bg-red-500/10 text-red-300')
                  }
                  title={p.error ?? ''}
                >
                  {ENGINE_META[p.engine].label} · {p.available ? 'ok' : 'ko'}
                </span>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
