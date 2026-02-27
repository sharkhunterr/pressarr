import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { type Magazine, getMagazineCoverUrl } from '@/api/magazines'
import { Badge } from '@/components/ui/badge'

function completionPercent(magazine: Magazine): number {
  const stats = magazine.statistics
  if (!stats || stats.issueCount === 0) return 0
  return Math.round((stats.availableCount / stats.issueCount) * 100)
}

interface MagazineCardProps {
  magazine: Magazine
}

export function MagazineCard({ magazine }: MagazineCardProps) {
  const navigate = useNavigate()
  const { t } = useTranslation()

  const percent = completionPercent(magazine)

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

        {/* Status badge */}
        <div className="absolute top-2 right-2">
          <Badge
            variant={magazine.monitored ? 'default' : 'outline'}
            className={magazine.monitored ? 'bg-[#7C3AED]' : ''}
          >
            {magazine.monitored ? t('library.monitored') : t('library.unmonitored')}
          </Badge>
        </div>
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
