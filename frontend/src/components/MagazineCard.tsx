import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { type Magazine, getMagazineCoverUrl } from '@/api/magazines'
import { Badge } from '@/components/ui/badge'

function completionPercent(magazine: Magazine): number {
  const stats = magazine.statistics
  if (!stats || stats.issueCount === 0) return 0
  return Math.round((stats.availableCount / stats.issueCount) * 100)
}

function formatNextDate(dateStr: string, t: (key: string, opts?: Record<string, unknown>) => string): string {
  const date = new Date(dateStr + 'T00:00:00')
  const now = new Date()
  now.setHours(0, 0, 0, 0)
  const diffMs = date.getTime() - now.getTime()
  const diffDays = Math.round(diffMs / (1000 * 60 * 60 * 24))

  if (diffDays === 0) return t('library.today')
  if (diffDays === 1) return t('library.tomorrow')
  if (diffDays > 1 && diffDays <= 7) return t('library.inDays', { count: diffDays })

  return date.toLocaleDateString(undefined, { day: 'numeric', month: 'short' })
}

interface MagazineCardProps {
  magazine: Magazine
}

export function MagazineCard({ magazine }: MagazineCardProps) {
  const navigate = useNavigate()
  const { t } = useTranslation()

  const percent = completionPercent(magazine)
  const nextDate = magazine.statistics?.nextIssueDate

  return (
    <button
      type="button"
      onClick={() => navigate(`/magazine/${magazine.id}`)}
      className="group rounded-lg bg-zinc-950 border border-zinc-800 overflow-hidden text-left transition hover:border-zinc-700 hover:shadow-lg focus:outline-none focus:ring-2 focus:ring-[#7C3AED]/50"
    >
      {/* Cover */}
      <div className="relative aspect-[3/4] bg-zinc-900 overflow-hidden">
        {magazine.coverPath ? (
          <img
            src={getMagazineCoverUrl(magazine.id, magazine.coverPath ?? undefined)}
            alt={magazine.title}
            className="h-full w-full object-cover transition group-hover:scale-105"
          />
        ) : (
          <div className="flex h-full items-center justify-center">
            <span className="text-zinc-600 text-sm">{t('library.noCover')}</span>
          </div>
        )}

        {/* Top badges */}
        <div className="absolute top-2 left-2 right-2 flex items-start justify-between gap-1">
          {/* Frequency badge (left) */}
          {magazine.monitored && magazine.frequency && magazine.frequency !== 'irregular' ? (
            <Badge variant="secondary" className="bg-zinc-900/80 text-zinc-300 text-[10px] px-1.5 py-0.5 backdrop-blur-sm">
              {t(`addMagazine.${magazine.frequency}`)}
            </Badge>
          ) : <div />}

          {/* Monitored badge (right) */}
          <Badge
            variant={magazine.monitored ? 'default' : 'secondary'}
            className={magazine.monitored ? 'bg-[#7C3AED] text-white' : ''}
          >
            {magazine.monitored ? t('library.monitored') : t('library.unmonitored')}
          </Badge>
        </div>

        {/* Next issue date badge (bottom) */}
        {magazine.monitored && nextDate && (
          <div className="absolute bottom-2 left-2">
            <Badge variant="secondary" className="bg-zinc-900/80 text-zinc-300 text-[10px] px-1.5 py-0.5 backdrop-blur-sm">
              {formatNextDate(nextDate, t)}
            </Badge>
          </div>
        )}
      </div>

      {/* Info */}
      <div className="p-3">
        <h3 className="text-sm font-medium text-zinc-100 truncate">{magazine.title}</h3>

        {/* Issue count stats */}
        <p className="text-xs text-zinc-500 mt-1">
          {t('library.issueStats', {
            available: magazine.statistics?.availableCount ?? 0,
            total: magazine.statistics?.issueCount ?? 0,
          })}
        </p>

        {/* Progress bar */}
        <div className="mt-2 h-1.5 rounded-full bg-zinc-800 overflow-hidden">
          <div
            className="h-full rounded-full bg-[#7C3AED] transition-all"
            style={{ width: `${percent}%` }}
          />
        </div>
        <p className="text-xs text-zinc-500 mt-1 text-right">{percent}%</p>
      </div>
    </button>
  )
}
