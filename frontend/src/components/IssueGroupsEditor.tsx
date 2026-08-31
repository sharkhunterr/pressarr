/**
 * Éditeur de groupes d'issues.
 *
 * Chaque groupe = liste de weekdays consécutifs qui seront coalescés
 * en une seule issue à la génération (émise sur le dernier jour du
 * groupe). Un label optionnel permet de tagger l'issue (« WEEK-END »,
 * « double numéro »).
 *
 * L'utilisateur peut :
 *   - créer autant de groupes que voulu (bouton « + Nouveau groupe »)
 *   - toggle les weekdays de chaque groupe
 *   - éditer le label du groupe
 *   - supprimer un groupe
 *
 * Un même weekday ne peut appartenir qu'à UN seul groupe (contrainte
 * par construction — sinon coalescing ambigu). Le sélecteur retire
 * automatiquement le jour des autres groupes quand on le coche ailleurs.
 *
 * Séparé du sélecteur `excludedDays` qui reste indépendant (un jour
 * excluded ne peut pas être dans un groupe non plus).
 */
import { useTranslation } from 'react-i18next'
import { Plus, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

export interface IssueGroup {
  days: number[]
  label?: string | null
}

interface Props {
  groups: IssueGroup[]
  excluded: number[]
  onChange: (next: IssueGroup[]) => void
}

const DAYS: [number, string][] = [
  [0, 'addMagazine.mon'],
  [1, 'addMagazine.tue'],
  [2, 'addMagazine.wed'],
  [3, 'addMagazine.thu'],
  [4, 'addMagazine.fri'],
  [5, 'addMagazine.sat'],
  [6, 'addMagazine.sun'],
]

// Palette de 6 couleurs distinctes pour visualiser les groupes.
// Cycle si l'user crée > 6 groupes (peu probable en pratique).
const GROUP_COLORS = [
  'bg-purple-900/50 border-purple-600 text-purple-200',
  'bg-amber-900/50 border-amber-600 text-amber-200',
  'bg-emerald-900/50 border-emerald-600 text-emerald-200',
  'bg-cyan-900/50 border-cyan-600 text-cyan-200',
  'bg-pink-900/50 border-pink-600 text-pink-200',
  'bg-blue-900/50 border-blue-600 text-blue-200',
]

export function IssueGroupsEditor({ groups, excluded, onChange }: Props) {
  const { t } = useTranslation()

  const findGroupOf = (day: number): number => {
    return groups.findIndex((g) => g.days.includes(day))
  }

  const toggleDay = (groupIdx: number, day: number) => {
    // Si le jour est excluded, refuse (pas de sens de le mettre dans un groupe).
    if (excluded.includes(day)) return
    const owningGroup = findGroupOf(day)
    const next = groups.map((g) => ({ ...g, days: [...g.days] }))
    // Retire de tous les groupes (garantit unicité)
    for (const g of next) {
      g.days = g.days.filter((d) => d !== day)
    }
    // Ajoute au groupe cible SI il n'y était pas déjà
    if (owningGroup !== groupIdx) {
      next[groupIdx].days.push(day)
      next[groupIdx].days.sort((a, b) => a - b)
    }
    onChange(next.filter((g) => g.days.length > 0))
  }

  const setLabel = (groupIdx: number, label: string) => {
    const next = groups.map((g, i) =>
      i === groupIdx ? { ...g, label: label || null } : g,
    )
    onChange(next)
  }

  const removeGroup = (groupIdx: number) => {
    onChange(groups.filter((_, i) => i !== groupIdx))
  }

  const addGroup = () => {
    onChange([...groups, { days: [], label: null }])
  }

  return (
    <div className="space-y-3">
      {groups.length === 0 && (
        <div className="text-xs text-zinc-500 italic">
          Aucun groupe défini. Chaque jour non-exclu = 1 issue régulière.
        </div>
      )}

      {groups.map((group, idx) => {
        const cls = GROUP_COLORS[idx % GROUP_COLORS.length]
        return (
          <div
            key={idx}
            className="rounded border border-zinc-800 bg-zinc-900/40 p-3 space-y-2"
          >
            <div className="flex items-center gap-2">
              <span className={`text-[10px] px-2 py-0.5 rounded border font-mono ${cls}`}>
                Groupe {idx + 1}
              </span>
              <Input
                value={group.label ?? ''}
                onChange={(e) => setLabel(idx, e.target.value)}
                placeholder="Label (optionnel — ex. « WEEK-END »)"
                className="flex-1 h-7 text-xs bg-zinc-900 border-zinc-700 text-zinc-100"
              />
              <Button
                variant="ghost"
                size="icon-xs"
                onClick={() => removeGroup(idx)}
                title="Supprimer ce groupe"
              >
                <Trash2 className="size-3 text-red-400" />
              </Button>
            </div>

            <div className="flex gap-1 flex-wrap">
              {DAYS.map(([day, key]) => {
                const inThisGroup = group.days.includes(day)
                const isExcluded = excluded.includes(day)
                const inOtherGroup = !inThisGroup && findGroupOf(day) !== -1
                const baseCls = inThisGroup
                  ? cls
                  : isExcluded
                    ? 'bg-red-900/30 border-red-800 text-red-500 line-through opacity-50 cursor-not-allowed'
                    : inOtherGroup
                      ? 'bg-zinc-800/50 border-zinc-700 text-zinc-600 opacity-40'
                      : 'bg-zinc-900 border-zinc-700 text-zinc-400 hover:border-zinc-600'
                return (
                  <button
                    key={day}
                    type="button"
                    onClick={() => toggleDay(idx, day)}
                    disabled={isExcluded}
                    title={
                      isExcluded
                        ? 'Jour exclu — impossible d\'ajouter à un groupe'
                        : inOtherGroup
                          ? `Déjà dans Groupe ${findGroupOf(day) + 1} — clic pour déplacer ici`
                          : inThisGroup
                            ? 'Clic pour retirer de ce groupe'
                            : 'Clic pour ajouter à ce groupe'
                    }
                    className={`px-2 py-1 text-xs rounded border transition-colors ${baseCls}`}
                  >
                    {t(key)}
                  </button>
                )
              })}
            </div>

            {group.days.length >= 2 && (
              <div className="text-[10px] text-zinc-500">
                {group.days.length} jours coalescés en 1 issue émise sur
                le dernier jour du groupe consécutif.
              </div>
            )}
          </div>
        )
      })}

      <Button
        variant="outline"
        size="sm"
        onClick={addGroup}
        className="w-full"
      >
        <Plus className="size-3.5" />
        Nouveau groupe
      </Button>
    </div>
  )
}
