/**
 * PackFileReimportDialog — re-processing manuel d'un fichier d'un pack.
 *
 * L'utilisateur peut :
 *  - Sélectionner un magazine EXISTANT (autocomplete par titre)
 *  - Créer un nouveau magazine à la volée (titre + frequency ; le
 *    root_folder + quality_profile sont hérités du pack côté back).
 *
 * L'issue est créée automatiquement par le back via
 * parse_magazine_filename(filename) si elle n'existe pas déjà —
 * pas d'input pour l'issue ici (KISS).
 */

import { useMemo, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { Loader2, Plus, Search } from 'lucide-react'

import { getMagazines, type Magazine } from '@/api/magazines'
import {
  reimportPackFile,
  type PackReimportBody,
} from '@/api/packs'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

const FREQUENCIES = [
  { value: 'daily', label: 'Quotidien' },
  { value: 'weekly', label: 'Hebdo' },
  { value: 'biweekly', label: 'Bi-hebdo' },
  { value: 'monthly', label: 'Mensuel' },
  { value: 'bimonthly', label: 'Bi-mensuel' },
  { value: 'quarterly', label: 'Trimestriel' },
  { value: 'yearly', label: 'Annuel' },
]

interface Props {
  packId: number
  downloadId: string | null
  filename: string
  proposedTitle?: string | null
  open: boolean
  onOpenChange: (open: boolean) => void
}

type Mode = 'existing' | 'create'

export function PackFileReimportDialog({
  packId,
  downloadId,
  filename,
  proposedTitle,
  open,
  onOpenChange,
}: Props) {
  const { t } = useTranslation()
  const qc = useQueryClient()

  const [mode, setMode] = useState<Mode>('existing')
  const [search, setSearch] = useState('')
  const [magazineId, setMagazineId] = useState<number | null>(null)
  const [newTitle, setNewTitle] = useState(proposedTitle ?? '')
  const [newFrequency, setNewFrequency] = useState('monthly')
  const [busy, setBusy] = useState(false)

  const { data: magazines = [] } = useQuery<Magazine[]>({
    queryKey: ['magazines'],
    queryFn: getMagazines,
    enabled: open && mode === 'existing',
  })

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    if (!q) return magazines.slice(0, 30)
    return magazines
      .filter((m) => m.title.toLowerCase().includes(q))
      .slice(0, 30)
  }, [magazines, search])

  const canSubmit = useMemo(() => {
    if (mode === 'existing') return magazineId !== null && !!downloadId
    return newTitle.trim().length >= 2 && !!downloadId
  }, [mode, magazineId, newTitle, downloadId])

  async function handleSubmit() {
    if (!downloadId) return
    setBusy(true)
    try {
      const body: PackReimportBody = { downloadId, filename }
      if (mode === 'existing' && magazineId) {
        body.magazineId = magazineId
      } else {
        body.createMagazine = {
          title: newTitle.trim(),
          frequency: newFrequency,
          monitored: true,
        }
      }
      const res = await reimportPackFile(packId, body)
      if (res.success) {
        toast.success(
          t('packs.reimportOk', 'Fichier réimporté'),
          {
            description: res.result?.message ?? undefined,
          },
        )
        qc.invalidateQueries({ queryKey: ['pack-import-history', packId] })
        qc.invalidateQueries({ queryKey: ['pack-pending-files', packId] })
        qc.invalidateQueries({ queryKey: ['magazines'] })
        onOpenChange(false)
      } else {
        toast.error(
          t('packs.reimportFailed', 'Reimport échoué'),
          {
            description: res.result?.message ?? 'Erreur inconnue',
          },
        )
      }
    } catch (e) {
      toast.error(
        t('packs.reimportError', 'Erreur reimport'),
        { description: (e as Error).message },
      )
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-xl bg-zinc-950 border-zinc-800">
        <DialogHeader>
          <DialogTitle className="text-zinc-100">
            {t('packs.reimportTitle', 'Réimporter ce fichier')}
          </DialogTitle>
          <DialogDescription className="text-zinc-400 font-mono text-xs break-all">
            {filename}
          </DialogDescription>
        </DialogHeader>

        {!downloadId && (
          <p className="text-sm text-amber-400 py-2">
            {t(
              'packs.reimportNoDownload',
              '⚠ Pas de download source connu — impossible de re-processor. Le torrent a peut-être été supprimé du client.',
            )}
          </p>
        )}

        {/* Mode toggle */}
        <div className="flex gap-2 pb-2">
          <Button
            type="button"
            size="sm"
            variant={mode === 'existing' ? 'default' : 'outline'}
            onClick={() => setMode('existing')}
            className={mode === 'existing' ? 'bg-violet-600 hover:bg-violet-500 text-white' : ''}
          >
            <Search className="size-3 mr-1" />
            {t('packs.reimportUseExisting', 'Magazine existant')}
          </Button>
          <Button
            type="button"
            size="sm"
            variant={mode === 'create' ? 'default' : 'outline'}
            onClick={() => setMode('create')}
            className={mode === 'create' ? 'bg-violet-600 hover:bg-violet-500 text-white' : ''}
          >
            <Plus className="size-3 mr-1" />
            {t('packs.reimportCreateNew', 'Créer un magazine')}
          </Button>
        </div>

        {mode === 'existing' ? (
          <div className="grid gap-2 py-1">
            <Input
              placeholder={t(
                'packs.reimportSearch',
                'Filtrer par titre…',
              )}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="bg-zinc-900 border-zinc-700 text-zinc-100"
              autoFocus
            />
            <div className="max-h-64 overflow-y-auto rounded border border-zinc-800 bg-zinc-950/60">
              {filtered.length === 0 ? (
                <p className="p-3 text-xs text-zinc-500">
                  {t(
                    'packs.reimportNoMatch',
                    'Aucun magazine correspondant.',
                  )}
                </p>
              ) : (
                filtered.map((m) => (
                  <label
                    key={m.id}
                    className={
                      'flex items-center gap-2 px-3 py-2 cursor-pointer hover:bg-zinc-800/60 '
                      + (magazineId === m.id
                        ? 'bg-violet-950/40 border-l-2 border-l-violet-500'
                        : '')
                    }
                  >
                    <input
                      type="radio"
                      name="magazine"
                      checked={magazineId === m.id}
                      onChange={() => setMagazineId(m.id)}
                      className="accent-violet-500"
                    />
                    <span className="text-sm text-zinc-100">{m.title}</span>
                    {m.publisher && (
                      <span className="ml-auto text-[10px] text-zinc-500">
                        {m.publisher}
                      </span>
                    )}
                  </label>
                ))
              )}
            </div>
          </div>
        ) : (
          <div className="grid gap-3 py-1">
            <div className="grid gap-1.5">
              <label className="text-xs font-medium text-zinc-300">
                {t('packs.reimportNewTitle', 'Titre du magazine')}
              </label>
              <Input
                value={newTitle}
                onChange={(e) => setNewTitle(e.target.value)}
                placeholder="ex : Le Monde"
                className="bg-zinc-900 border-zinc-700 text-zinc-100"
                autoFocus
              />
              {proposedTitle && (
                <button
                  type="button"
                  className="text-[10px] text-violet-400 hover:underline text-left"
                  onClick={() => setNewTitle(proposedTitle)}
                >
                  {t('packs.reimportUseParsed', 'Utiliser le titre parsé :')}{' '}
                  <span className="font-mono">« {proposedTitle} »</span>
                </button>
              )}
            </div>
            <div className="grid gap-1.5">
              <label className="text-xs font-medium text-zinc-300">
                {t('packs.reimportNewFrequency', 'Fréquence')}
              </label>
              <Select value={newFrequency} onValueChange={setNewFrequency}>
                <SelectTrigger className="bg-zinc-900 border-zinc-700 text-zinc-100">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-zinc-900 border-zinc-700">
                  {FREQUENCIES.map((f) => (
                    <SelectItem key={f.value} value={f.value}>
                      {f.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <p className="text-[10px] text-zinc-500">
              {t(
                'packs.reimportInherit',
                '💡 root_folder + quality_profile hérités du pack. Une issue sera créée automatiquement pour ce fichier.',
              )}
            </p>
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            {t('common.cancel', 'Annuler')}
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={!canSubmit || busy}
            className="bg-violet-600 hover:bg-violet-500 text-white"
          >
            {busy && <Loader2 className="size-3 mr-1 animate-spin" />}
            {t('packs.reimportDo', 'Réimporter')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
