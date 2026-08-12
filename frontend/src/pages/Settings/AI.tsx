import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Save, RefreshCw, Sparkles, Loader2, CheckCircle2, XCircle } from 'lucide-react'
import { toast } from 'sonner'

import {
  getAISettings,
  probeOllamaModels,
  saveAISettings,
  type AISettings,
} from '@/api/ai'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'

/** Lightweight replacements for missing shadcn primitives.
 *  Match the visual language of the app (zinc bg, subtle borders). */
function Label({ children }: { children: React.ReactNode }) {
  return (
    <label className="text-sm font-medium text-zinc-300 mb-1 block">
      {children}
    </label>
  )
}

function Textarea(props: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      {...props}
      className={
        (props.className ?? '') +
        ' w-full rounded-md border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-600'
      }
    />
  )
}

/** Local editable copy of AISettings — every field non-optional so
 *  React inputs stay controlled. Populated from the server via
 *  `useEffect(setLocal(data))` and dumped back via `saveAISettings`. */
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

  const { data, isLoading } = useQuery({
    queryKey: ['aiSettings'],
    queryFn: getAISettings,
  })
  const probeQ = useQuery({
    queryKey: ['ollamaModels'],
    queryFn: probeOllamaModels,
    staleTime: 30_000,
  })

  // Sync server → local once at load. Subsequent user edits stay
  // local until Save.
  useEffect(() => {
    if (data) {
      setLocal(data)
      setPagesStr((data.enrichmentVisionPages ?? [1]).join(', '))
    }
  }, [data])

  const saveMutation = useMutation({
    mutationFn: (payload: Partial<AISettings>) => saveAISettings(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['aiSettings'] })
      toast.success('Paramètres IA enregistrés')
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

  const models = probeQ.data?.models ?? []
  const reachable = probeQ.data?.reachable ?? false

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-zinc-500" />
      </div>
    )
  }

  return (
    <div className="container mx-auto py-6 space-y-6 max-w-5xl">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Sparkles className="w-6 h-6 text-purple-400" />
          <div>
            <h1 className="text-2xl font-semibold text-zinc-100">
              Intelligence Artificielle
            </h1>
            <p className="text-sm text-zinc-400">
              Enrichissement des métadonnées et ranking des recherches via Ollama.
            </p>
          </div>
        </div>
        <Button onClick={commit} disabled={saveMutation.isPending}>
          {saveMutation.isPending ? (
            <Loader2 className="w-4 h-4 animate-spin mr-2" />
          ) : (
            <Save className="w-4 h-4 mr-2" />
          )}
          Enregistrer
        </Button>
      </div>

      {/* --- Ollama connection ---------------------------------- */}
      <Card className="bg-zinc-950 border-zinc-800">
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-zinc-100">Serveur Ollama</CardTitle>
              <CardDescription className="text-zinc-400">
                URL du serveur Ollama et timeout par appel. Les modèles
                doivent être installés avec <code className="text-zinc-300">ollama pull</code>.
              </CardDescription>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => qc.invalidateQueries({ queryKey: ['ollamaModels'] })}
            >
              <RefreshCw className="w-4 h-4 mr-2" />
              Tester
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-3 gap-4">
            <div className="col-span-2">
              <Label>URL Ollama</Label>
              <Input
                value={local.ollamaUrl}
                onChange={(e) => setLocal({ ...local, ollamaUrl: e.target.value })}
                placeholder="http://192.168.1.24:11434"
              />
            </div>
            <div>
              <Label>Timeout (secondes)</Label>
              <Input
                type="number"
                value={local.ollamaTimeoutS}
                onChange={(e) =>
                  setLocal({ ...local, ollamaTimeoutS: Number(e.target.value) })
                }
              />
            </div>
          </div>
          <div className="flex items-center gap-2 text-sm">
            {reachable ? (
              <>
                <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                <span className="text-zinc-300">
                  Serveur joignable — {models.length} modèle(s) installé(s)
                </span>
              </>
            ) : (
              <>
                <XCircle className="w-4 h-4 text-rose-400" />
                <span className="text-zinc-300">
                  Injoignable — {probeQ.data?.error ?? 'n/a'}
                </span>
              </>
            )}
          </div>
        </CardContent>
      </Card>

      {/* --- Enrichment ---------------------------------------- */}
      <Card className="bg-zinc-950 border-zinc-800">
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-zinc-100">
                Enrichissement métadonnées
              </CardTitle>
              <CardDescription className="text-zinc-400">
                Pipeline : nom torrent → LLM texte → OCR vision (couverture) → arbitre.
              </CardDescription>
            </div>
            <Switch
              checked={local.enrichmentEnabled}
              onCheckedChange={(v) => setLocal({ ...local, enrichmentEnabled: v })}
            />
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label>Modèle texte (torrent + arbitre)</Label>
              <ModelSelect
                value={local.textModel}
                onChange={(v) => setLocal({ ...local, textModel: v })}
                models={models}
                placeholder="mistral:7b"
              />
            </div>
            <div>
              <Label>Modèle vision (OCR couverture)</Label>
              <ModelSelect
                value={local.visionModel}
                onChange={(v) => setLocal({ ...local, visionModel: v })}
                models={models}
                placeholder="minicpm-v:8b"
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label>
                Autorité (que fait l'IA de son résultat)
              </Label>
              <Select
                value={local.enrichmentMode}
                onValueChange={(v: 'remplace' | 'complete' | 'propose') =>
                  setLocal({ ...local, enrichmentMode: v })
                }
              >
                <SelectTrigger>
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
            <div>
              <Label>
                Pages à envoyer au vision (négatif = depuis la fin)
              </Label>
              <Input
                value={pagesStr}
                onChange={(e) => setPagesStr(e.target.value)}
                placeholder="1, -1"
              />
            </div>
          </div>
          <div>
            <Label>Prompt LLM texte (nom torrent)</Label>
            <Textarea
              rows={5}
              value={local.textPrompt}
              onChange={(e) => setLocal({ ...local, textPrompt: e.target.value })}
              className="font-mono text-sm"
            />
          </div>
          <div>
            <Label>Prompt LLM vision (couverture)</Label>
            <Textarea
              rows={5}
              value={local.visionPrompt}
              onChange={(e) => setLocal({ ...local, visionPrompt: e.target.value })}
              className="font-mono text-sm"
            />
          </div>
          <div>
            <Label>Prompt arbitre (fusion torrent + vision)</Label>
            <Textarea
              rows={6}
              value={local.arbiterPrompt}
              onChange={(e) => setLocal({ ...local, arbiterPrompt: e.target.value })}
              className="font-mono text-sm"
            />
          </div>
        </CardContent>
      </Card>

      {/* --- Ranker -------------------------------------------- */}
      <Card className="bg-zinc-950 border-zinc-800">
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-zinc-100">
                Ranker recherche (choix parmi plusieurs releases)
              </CardTitle>
              <CardDescription className="text-zinc-400">
                Envoie les candidats de la recherche à l'IA par petits
                batches et laisse choisir la meilleure correspondance.
              </CardDescription>
            </div>
            <Switch
              checked={local.rankerEnabled}
              onCheckedChange={(v) => setLocal({ ...local, rankerEnabled: v })}
            />
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <Label>Autorité ranker</Label>
            <Select
              value={local.rankerMode}
              onValueChange={(v: 'ai_wins' | 'ai_veto_only' | 'ai_advisory') =>
                setLocal({ ...local, rankerMode: v })
              }
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="ai_advisory">
                  Observation — l'IA log son avis mais n'influence pas
                </SelectItem>
                <SelectItem value="ai_veto_only">
                  Veto seul — l'IA peut rejeter le top scorer
                </SelectItem>
                <SelectItem value="ai_wins">
                  IA tranche — pick de l'IA prioritaire
                </SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="grid grid-cols-3 gap-4">
            <div>
              <Label>Batch size</Label>
              <Input
                type="number"
                min={2}
                max={20}
                value={local.rankerBatchSize}
                onChange={(e) =>
                  setLocal({ ...local, rankerBatchSize: Number(e.target.value) })
                }
              />
            </div>
            <div>
              <Label>Top-K envoyé à l'IA</Label>
              <Input
                type="number"
                min={1}
                max={100}
                value={local.rankerTopK}
                onChange={(e) =>
                  setLocal({ ...local, rankerTopK: Number(e.target.value) })
                }
              />
            </div>
            <div>
              <Label>Seuil de confiance</Label>
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
              />
            </div>
          </div>
          <div>
            <Label>Prompt ranker</Label>
            <Textarea
              rows={6}
              value={local.rankerPrompt}
              onChange={(e) => setLocal({ ...local, rankerPrompt: e.target.value })}
              className="font-mono text-sm"
            />
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

/** Model dropdown that falls back to a raw text input when the
 *  Ollama probe hasn't loaded yet or the desired model isn't in the
 *  server's list. Keeps the user from being locked out when their
 *  target model exists on a server that's temporarily unreachable. */
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
  const inList = models.includes(value)
  if (models.length === 0 || !inList) {
    return (
      <div className="space-y-1">
        <Input
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
        />
        {models.length > 0 && !inList && (
          <p className="text-xs text-amber-400">
            Ce modèle n'est pas dans la liste locale — sera considéré manquant à l'exécution.
          </p>
        )}
      </div>
    )
  }
  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger>
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent>
        {models.map((m) => (
          <SelectItem key={m} value={m}>
            {m}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}
