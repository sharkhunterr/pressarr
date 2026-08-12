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
  saveAISettings,
  type AISettings,
  type OllamaModelsProbe,
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
  textModel: 'mistral:7b',
  visionModel: 'minicpm-v:8b',
  textPrompt: '',
  visionPrompt: '',
  arbiterPrompt: '',
  rankerEnabled: false,
  rankerMode: 'ai_advisory',
  rankerBatchSize: 5,
  rankerTopK: 15,
  rankerConfidenceThreshold: 0.6,
  rankerPrompt: '',
}

export default function AISettingsPage() {
  const qc = useQueryClient()
  const [local, setLocal] = useState<LocalState>(DEFAULT)
  const [pagesStr, setPagesStr] = useState('1')
  const [probe, setProbe] = useState<OllamaModelsProbe | null>(null)
  const [probing, setProbing] = useState(false)

  const { isLoading } = useQuery({
    queryKey: ['aiSettings'],
    queryFn: getAISettings,
    select: (data) => {
      setLocal(data)
      setPagesStr((data.enrichmentVisionPages ?? [1]).join(', '))
      return data
    },
  })

  // Auto-probe on mount + whenever the saved URL changes.
  useEffect(() => {
    if (isLoading) return
    void runProbe(local.ollamaUrl)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isLoading])

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
    onSuccess: (fresh) => {
      qc.invalidateQueries({ queryKey: ['aiSettings'] })
      toast.success('Paramètres IA enregistrés')
      // Re-probe after save in case the URL/timeout changed.
      void runProbe(fresh.ollamaUrl)
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
                  Modèle texte (torrent + arbitre)
                </label>
                <ModelSelect
                  value={local.textModel}
                  onChange={(v) => setLocal({ ...local, textModel: v })}
                  models={models}
                  placeholder="mistral:7b"
                />
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
