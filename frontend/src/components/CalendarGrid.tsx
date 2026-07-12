import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { type CalendarEntry } from '@/api/calendar'

interface CalendarGridProps {
  year: number
  month: number
  entries: CalendarEntry[]
}

function getDaysInMonth(year: number, month: number): number {
  return new Date(year, month + 1, 0).getDate()
}

function getFirstDayOfWeek(year: number, month: number): number {
  return new Date(year, month, 1).getDay()
}

export function CalendarGrid({ year, month, entries }: CalendarGridProps) {
  const navigate = useNavigate()
  const { t } = useTranslation()

  const daysInMonth = getDaysInMonth(year, month)
  const firstDay = getFirstDayOfWeek(year, month)

  const dayNames = [
    t('calendar.sun'),
    t('calendar.mon'),
    t('calendar.tue'),
    t('calendar.wed'),
    t('calendar.thu'),
    t('calendar.fri'),
    t('calendar.sat'),
  ]

  // Group entries by day
  const entriesByDay: Record<number, CalendarEntry[]> = {}
  for (const entry of entries) {
    const d = new Date(entry.date)
    if (d.getFullYear() === year && d.getMonth() === month) {
      const day = d.getDate()
      if (!entriesByDay[day]) entriesByDay[day] = []
      entriesByDay[day].push(entry)
    }
  }

  const cells: (number | null)[] = []
  for (let i = 0; i < firstDay; i++) cells.push(null)
  for (let d = 1; d <= daysInMonth; d++) cells.push(d)

  const today = new Date()
  const isToday = (day: number) =>
    today.getFullYear() === year && today.getMonth() === month && today.getDate() === day

  return (
    <div>
      {/* Day headers */}
      <div className="grid grid-cols-7 mb-1">
        {dayNames.map((name) => (
          <div key={name} className="text-center text-xs font-medium text-zinc-500 py-2">
            {name}
          </div>
        ))}
      </div>

      {/* Calendar cells */}
      <div className="grid grid-cols-7 gap-px bg-zinc-800 rounded-lg overflow-hidden">
        {cells.map((day, idx) => (
          <div
            key={idx}
            className={`min-h-24 bg-zinc-950 p-1.5 ${
              day === null ? 'bg-zinc-950/50' : ''
            } ${day !== null && isToday(day) ? 'ring-1 ring-inset ring-[#7C3AED]' : ''}`}
          >
            {day !== null && (
              <>
                <span
                  className={`text-xs font-medium ${
                    isToday(day) ? 'text-[#7C3AED]' : 'text-zinc-400'
                  }`}
                >
                  {day}
                </span>
                <div className="mt-1 space-y-1">
                  {(entriesByDay[day] || []).slice(0, 3).map((entry, i) => (
                    <button
                      key={`${entry.magazineId}-${entry.issueId ?? i}`}
                      type="button"
                      onClick={() => {
                        if (entry.issueId) navigate(`/magazine/${entry.magazineId}`)
                      }}
                      className={`w-full rounded px-1 py-0.5 text-left text-[10px] leading-tight truncate transition hover:opacity-80 ${
                        entry.isForecast
                          ? 'border border-dashed border-zinc-600 text-zinc-400'
                          : 'border border-solid border-[#7C3AED]/50 bg-[#7C3AED]/10 text-zinc-200'
                      }`}
                      title={`${entry.magazineTitle}${entry.number !== null ? ` #${entry.number}` : ''}`}
                    >
                      {entry.coverUrl ? (
                        <img
                          src={entry.coverUrl}
                          alt=""
                          className="size-3 rounded-sm inline-block mr-0.5 object-cover"
                        />
                      ) : null}
                      {entry.magazineTitle}
                    </button>
                  ))}
                  {(entriesByDay[day] || []).length > 3 && (
                    <span className="text-[10px] text-zinc-500">
                      +{(entriesByDay[day] || []).length - 3}
                    </span>
                  )}
                </div>
              </>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
