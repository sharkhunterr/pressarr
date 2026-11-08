import { useTranslation } from 'react-i18next'
import { FlaskConical } from 'lucide-react'

// Marks a feature that ships but is not settled yet (Bookys, AI).
export function ExperimentalBadge({ className = '' }: { className?: string }) {
  const { t } = useTranslation()
  return (
    <span
      className={`inline-flex items-center gap-1 rounded border border-amber-500/40 bg-amber-500/10 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-300 ${className}`}
    >
      <FlaskConical className="size-3" />
      {t('experimental.badge')}
    </span>
  )
}

// The banner under a feature's title: why it is experimental.
export function ExperimentalNotice({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex items-start gap-2 rounded-md border border-amber-500/30 bg-amber-500/5 px-3 py-2 text-xs text-amber-200">
      <FlaskConical className="mt-0.5 size-3.5 shrink-0 text-amber-400" />
      <span>{children}</span>
    </div>
  )
}
