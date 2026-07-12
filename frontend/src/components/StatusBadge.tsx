import { useTranslation } from 'react-i18next'

const STATUS_STYLES: Record<string, string> = {
  available: 'bg-green-600',
  wanted: 'bg-red-500',
  missing: 'bg-orange-400',
  downloading: 'bg-blue-500',
  snatched: 'bg-purple-500',
  upcoming: 'bg-zinc-500',
  skipped: 'bg-zinc-400',
  delayed: 'bg-yellow-500',
  completed: 'bg-green-600',
  paused: 'bg-zinc-400',
  failed: 'bg-red-500',
}

interface StatusBadgeProps {
  status: string
  className?: string
  tKey?: string
}

export function StatusBadge({ status, className = '', tKey }: StatusBadgeProps) {
  const { t } = useTranslation()
  const bg = STATUS_STYLES[status] || STATUS_STYLES.missing
  const label = tKey ? t(tKey, status) : t(`status.${status}`, status)
  return (
    <span className={`inline-flex items-center justify-center rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap text-black ${bg} ${className}`}>
      {label}
    </span>
  )
}
