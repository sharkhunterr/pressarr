/**
 * PathPicker — browse le filesystem du container pressarr pour choisir
 * un dossier, avec text-entry manuel toujours accessible en fallback.
 *
 * Porté depuis romarr avec deux ajouts UX :
 *  - Chaque entrée affiche son nombre d'items (childCount) + un badge
 *    "read-only" quand !isWritable — permet à l'utilisateur de voir
 *    d'un coup d'œil si le dossier envisagé est utilisable.
 *  - Bouton "..↑" reste dispo tant que parent != null.
 *
 * Usage :
 *   <PathPicker value={path} onChange={setPath} disabled={busy} />
 */

import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ChevronUp, Folder, HardDrive, Loader2, Lock } from 'lucide-react'
import { useTranslation } from 'react-i18next'

import { browseFilesystem, type FsListing } from '@/api/system'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

interface Props {
  value: string
  onChange: (next: string) => void
  disabled?: boolean
  placeholder?: string
}

function _parentOf(path: string): string {
  if (!path || path === '/') return '/'
  const trimmed = path.replace(/\/+$/, '')
  const idx = trimmed.lastIndexOf('/')
  return idx <= 0 ? '/' : trimmed.slice(0, idx)
}

function _crumbs(path: string): { label: string; path: string }[] {
  if (!path || path === '/') return [{ label: '/', path: '/' }]
  const parts = path.split('/').filter(Boolean)
  const acc: { label: string; path: string }[] = [{ label: '/', path: '/' }]
  let cur = ''
  for (const part of parts) {
    cur = `${cur}/${part}`
    acc.push({ label: part, path: cur })
  }
  return acc
}

export function PathPicker(props: Props) {
  const { t } = useTranslation()
  const [browseOpen, setBrowseOpen] = useState(false)
  const [browsePath, setBrowsePath] = useState<string>(
    props.value ? _parentOf(props.value) : '/',
  )

  // Ré-ancre à `value` à chaque ouverture (évite d'être coincé sur un
  // état stale après une édition manuelle du champ texte).
  useEffect(() => {
    if (browseOpen) {
      setBrowsePath(props.value ? _parentOf(props.value) : '/')
    }
  }, [browseOpen, props.value])

  const listing = useQuery<FsListing, Error>({
    queryKey: ['filesystem', browsePath],
    queryFn: () => browseFilesystem(browsePath),
    enabled: browseOpen,
    retry: false,
  })

  return (
    <div className="space-y-2">
      {/* Text entry — toujours visible pour paste rapide */}
      <div className="flex gap-2">
        <Input
          value={props.value}
          onChange={(e) => props.onChange(e.target.value)}
          placeholder={props.placeholder ?? '/magazines'}
          disabled={props.disabled}
          className="flex-1 font-mono bg-zinc-950 border-zinc-700 text-zinc-100"
        />
        <Button
          type="button"
          variant="outline"
          onClick={() => setBrowseOpen((v) => !v)}
          disabled={props.disabled}
          aria-expanded={browseOpen}
          className="shrink-0 border-zinc-700 text-zinc-200"
        >
          {browseOpen
            ? t('pathPicker.close', 'Fermer')
            : t('pathPicker.browse', 'Parcourir…')}
        </Button>
      </div>

      {browseOpen && (
        <div className="rounded-md border border-zinc-800 bg-zinc-950/60 p-2">
          {/* Breadcrumbs — chaque segment cliquable pour remonter */}
          <div className="mb-2 flex flex-wrap items-baseline gap-1 font-mono text-xs">
            {_crumbs(browsePath).map((c, i, arr) => (
              <span key={c.path} className="flex items-baseline gap-1">
                <button
                  type="button"
                  onClick={() => setBrowsePath(c.path)}
                  className="rounded px-1 text-violet-400 hover:bg-zinc-800"
                >
                  {c.label}
                </button>
                {i < arr.length - 1 && <span className="text-zinc-600">/</span>}
              </span>
            ))}
          </div>

          {listing.isPending && (
            <p className="flex items-center gap-2 p-2 text-xs text-zinc-500">
              <Loader2 className="size-3 animate-spin" />
              {t('pathPicker.loading', 'Chargement…')}
            </p>
          )}
          {listing.isError && (
            <p role="alert" className="p-2 text-xs text-red-300">
              {listing.error.message}
            </p>
          )}

          {listing.isSuccess && (
            <ul className="max-h-64 space-y-0.5 overflow-y-auto">
              {listing.data.parent !== null && (
                <li>
                  <button
                    type="button"
                    onClick={() => setBrowsePath(listing.data.parent!)}
                    className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left font-mono text-xs text-zinc-400 hover:bg-zinc-800/60"
                  >
                    <ChevronUp className="size-3" aria-hidden />
                    <span>..</span>
                    <span className="ml-auto text-[10px] text-zinc-600">
                      {listing.data.parent}
                    </span>
                  </button>
                </li>
              )}
              {listing.data.entries.length === 0 && (
                <li className="p-2 text-xs text-zinc-500">
                  {t('pathPicker.empty', '(aucun sous-dossier)')}
                </li>
              )}
              {listing.data.entries.map((entry) => {
                const count = entry.childCount
                const countLabel =
                  count === null
                    ? '?'
                    : count >= 5000
                      ? '5000+'
                      : String(count)
                return (
                  <li key={entry.path} className="flex items-center gap-1">
                    <button
                      type="button"
                      onClick={() => setBrowsePath(entry.path)}
                      className="flex flex-1 items-center gap-2 rounded px-2 py-1.5 text-left font-mono text-xs text-zinc-100 hover:bg-zinc-800/60"
                    >
                      <Folder
                        className="size-3.5 shrink-0 text-zinc-500"
                        aria-hidden
                      />
                      <span className="truncate">{entry.name}</span>
                      {entry.isMount && (
                        <span
                          title={t(
                            'pathPicker.mountHint',
                            'Système de fichiers différent — probablement un volume Docker',
                          )}
                          className="inline-flex items-center gap-0.5 rounded bg-violet-500/20 px-1.5 py-0.5 text-[9px] uppercase tracking-wider text-violet-300"
                        >
                          <HardDrive className="size-2.5" aria-hidden />
                          mount
                        </span>
                      )}
                      {!entry.isWritable && (
                        <span
                          title={t(
                            'pathPicker.readOnlyHint',
                            'Pressarr ne peut pas écrire dans ce dossier',
                          )}
                          className="inline-flex items-center gap-0.5 rounded bg-amber-950/50 px-1.5 py-0.5 text-[9px] uppercase tracking-wider text-amber-400"
                        >
                          <Lock className="size-2.5" aria-hidden />
                          RO
                        </span>
                      )}
                      <span className="ml-auto shrink-0 text-[10px] text-zinc-500">
                        {countLabel} {t('pathPicker.items', 'items')}
                      </span>
                    </button>
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      onClick={() => {
                        props.onChange(entry.path)
                        setBrowseOpen(false)
                      }}
                      className="h-7 shrink-0 text-[11px] text-violet-400 hover:bg-zinc-800 hover:text-violet-300"
                    >
                      {t('pathPicker.pick', 'Choisir')}
                    </Button>
                  </li>
                )
              })}
            </ul>
          )}

          {/* Pick-current-directory shortcut */}
          {listing.isSuccess && browsePath !== '/' && (
            <div className="mt-2 border-t border-zinc-800 pt-2">
              <Button
                type="button"
                size="sm"
                onClick={() => {
                  props.onChange(browsePath)
                  setBrowseOpen(false)
                }}
                className="w-full bg-violet-600 text-white hover:bg-violet-500"
              >
                {t('pathPicker.pickCurrent', 'Choisir ce dossier :')}{' '}
                <span className="ml-1 font-mono">{browsePath}</span>
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
