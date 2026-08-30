/**
 * Sélecteur weekday à 3 états — cycle au clic :
 *   neutre → exclu → weekend → neutre
 *
 * Un jour ne peut pas être exclu ET regroupé weekend en même temps
 * (par construction) — d'où le cycle plutôt que deux sélecteurs
 * séparés qui doublonnent visuellement.
 *
 * Neutre  = jour publié normalement, aucun traitement spécial
 * Exclu   = pas d'édition ce jour (excludedDays)
 * Weekend = fait partie d'une édition combinée weekend (weekendDays)
 *
 * Utilisé dans AddMagazine et MagazineDetail edit modal.
 */
import { useTranslation } from 'react-i18next'

interface Props {
  excluded: number[]
  weekend: number[]
  onChange: (next: { excluded: number[]; weekend: number[] }) => void
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

type DayState = 'neutral' | 'excluded' | 'weekend'

function stateOf(day: number, excluded: number[], weekend: number[]): DayState {
  if (excluded.includes(day)) return 'excluded'
  if (weekend.includes(day)) return 'weekend'
  return 'neutral'
}

function cycle(state: DayState): DayState {
  if (state === 'neutral') return 'excluded'
  if (state === 'excluded') return 'weekend'
  return 'neutral'
}

const CLASS: Record<DayState, string> = {
  neutral: 'bg-zinc-900 border-zinc-700 text-zinc-400',
  excluded: 'bg-red-900/50 border-red-700 text-red-300',
  weekend: 'bg-purple-900/50 border-purple-600 text-purple-200',
}

const LABEL: Record<DayState, string> = {
  neutral: 'jour normal (publie)',
  excluded: 'exclu (pas d\'édition)',
  weekend: 'regroupé dans l\'édition weekend',
}

export function WeekdaySelector({ excluded, weekend, onChange }: Props) {
  const { t } = useTranslation()

  const handleClick = (day: number) => {
    const current = stateOf(day, excluded, weekend)
    const next = cycle(current)
    // Remove from both, then insert into the target list
    const cleanEx = excluded.filter((d) => d !== day)
    const cleanWk = weekend.filter((d) => d !== day)
    if (next === 'excluded') {
      onChange({ excluded: [...cleanEx, day], weekend: cleanWk })
    } else if (next === 'weekend') {
      onChange({ excluded: cleanEx, weekend: [...cleanWk, day] })
    } else {
      onChange({ excluded: cleanEx, weekend: cleanWk })
    }
  }

  return (
    <div className="space-y-2">
      <div className="flex gap-1 flex-wrap">
        {DAYS.map(([day, key]) => {
          const s = stateOf(day, excluded, weekend)
          return (
            <button
              key={day}
              type="button"
              onClick={() => handleClick(day)}
              title={LABEL[s]}
              className={`px-2 py-1 text-xs rounded border transition-colors ${CLASS[s]}`}
            >
              {t(key)}
            </button>
          )
        })}
      </div>
      <div className="flex flex-wrap gap-3 text-xs text-zinc-500">
        <span className="inline-flex items-center gap-1.5">
          <span className="inline-block w-2 h-2 rounded bg-zinc-700" />
          normal
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="inline-block w-2 h-2 rounded bg-red-700" />
          exclu (pas d'édition)
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="inline-block w-2 h-2 rounded bg-purple-600" />
          weekend (édition combinée)
        </span>
        <span className="italic opacity-60">clic pour cycler</span>
      </div>
    </div>
  )
}
