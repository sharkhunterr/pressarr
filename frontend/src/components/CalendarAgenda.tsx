import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { SkipForward } from 'lucide-react'

import { type CalendarEntry } from '@/api/calendar'
import { StatusBadge } from '@/components/StatusBadge'
import { Button } from '@/components/ui/button'

interface CalendarAgendaProps {
  entries: CalendarEntry[]
  onSkip: (issueId: number) => void
}

export function CalendarAgenda({ entries, onSkip }: CalendarAgendaProps) {
  const navigate = useNavigate()
  const { t } = useTranslation()

  // Group by date
  const grouped: Record<string, CalendarEntry[]> = {}
  for (const entry of entries) {
    const dateKey = entry.date.slice(0, 10)
    if (!grouped[dateKey]) grouped[dateKey] = []
    grouped[dateKey].push(entry)
  }

  const sortedDates = Object.keys(grouped).sort()

  if (sortedDates.length === 0) {
    return (
      <p className="text-zinc-500 text-center py-8">{t('calendar.noEntries')}</p>
    )
  }

  return (
    <div className="space-y-6">
      {sortedDates.map((dateKey) => (
        <div key={dateKey}>
          <h3 className="text-sm font-medium text-zinc-400 mb-2 border-b border-zinc-800 pb-1">
            {new Date(dateKey + 'T00:00:00').toLocaleDateString(undefined, {
              weekday: 'long',
              year: 'numeric',
              month: 'long',
              day: 'numeric',
            })}
          </h3>
          <div className="space-y-2">
            {grouped[dateKey].map((entry, i) => (
              <div
                key={`${entry.magazineId}-${entry.issueId ?? i}`}
                className={`flex items-center gap-3 rounded-md px-3 py-2 transition ${
                  entry.isForecast
                    ? 'border border-dashed border-zinc-700 bg-zinc-950'
                    : 'border border-zinc-800 bg-zinc-950 hover:bg-zinc-900/50'
                }`}
              >
                {/* Cover thumbnail */}
                <div className="size-10 shrink-0 rounded bg-zinc-800 overflow-hidden">
                  {entry.coverUrl ? (
                    <img
                      src={entry.coverUrl}
                      alt=""
                      className="h-full w-full object-cover"
                    />
                  ) : (
                    <div className="flex items-center justify-center h-full text-zinc-600 text-[8px]">
                      N/A
                    </div>
                  )}
                </div>

                {/* Info */}
                <button
                  type="button"
                  onClick={() => navigate(`/magazine/${entry.magazineId}`)}
                  className="flex-1 min-w-0 text-left"
                >
                  <p className="text-sm text-zinc-100 truncate">{entry.magazineTitle}</p>
                  <p className="text-xs text-zinc-500">
                    {entry.number !== null ? `#${entry.number}` : t('calendar.noNumber')}
                  </p>
                </button>

                {/* Status */}
                <StatusBadge status={entry.status} />

                {/* Skip button for forecasts */}
                {entry.isForecast && entry.issueId !== null && (
                  <Button
                    variant="ghost"
                    size="icon-xs"
                    onClick={() => onSkip(entry.issueId!)}
                    title={t('calendar.skip')}
                  >
                    <SkipForward className="size-3.5 text-zinc-400" />
                  </Button>
                )}
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}
