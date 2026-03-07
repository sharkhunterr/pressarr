import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { type Pack } from '@/api/packs'
import { Badge } from '@/components/ui/badge'

interface PackCardProps {
  pack: Pack
}

export function PackCard({ pack }: PackCardProps) {
  const navigate = useNavigate()
  const { t } = useTranslation()

  const lastGrab = pack.statistics?.lastGrabDate
    ? new Date(pack.statistics.lastGrabDate).toLocaleDateString()
    : null

  return (
    <button
      type="button"
      onClick={() => navigate(`/pack/${pack.id}`)}
      className="group rounded-lg bg-zinc-950 border border-zinc-800 overflow-hidden text-left transition hover:border-zinc-700 hover:shadow-lg focus:outline-none focus:ring-2 focus:ring-[#7C3AED]/50"
    >
      {/* Icon area */}
      <div className="relative aspect-[4/3] bg-zinc-900 overflow-hidden flex items-center justify-center">
        <svg className="size-16 text-zinc-700 group-hover:text-zinc-600 transition" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
          <path d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
        </svg>

        {/* Top badges */}
        <div className="absolute top-2 left-2 right-2 flex items-start justify-between gap-1">
          {pack.recurrence && pack.recurrence !== 'none' ? (
            <Badge variant="secondary" className="bg-zinc-900/80 text-zinc-300 text-[10px] px-1.5 py-0.5 backdrop-blur-sm capitalize">
              {t(`packs.${pack.recurrence}`)}
            </Badge>
          ) : <div />}

          <Badge
            variant={pack.monitored ? 'default' : 'outline'}
            className={pack.monitored ? 'bg-[#7C3AED]' : ''}
          >
            {pack.monitored ? t('packs.monitored') : t('packs.unmonitored')}
          </Badge>
        </div>
      </div>

      {/* Info */}
      <div className="p-3">
        <h3 className="text-sm font-medium text-zinc-100 truncate">{pack.name}</h3>

        {pack.description && (
          <p className="text-xs text-zinc-500 mt-0.5 truncate">{pack.description}</p>
        )}

        <div className="flex items-center gap-2 mt-2 text-xs text-zinc-500">
          <span>{t('packs.patterns', { count: pack.statistics?.patternCount ?? 0 })}</span>
          <span>&middot;</span>
          <span>{t('packs.grabs', { count: pack.statistics?.totalGrabs ?? 0 })}</span>
        </div>

        {lastGrab ? (
          <p className="text-xs text-zinc-600 mt-1">
            {t('packs.lastGrab', { date: lastGrab })}
          </p>
        ) : (
          <p className="text-xs text-zinc-600 mt-1">{t('packs.noGrabs')}</p>
        )}
      </div>
    </button>
  )
}
