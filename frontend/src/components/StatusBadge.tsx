const STATUS_STYLES: Record<string, { bg: string; text: string }> = {
  available: { bg: 'bg-green-600', text: 'text-green-100' },
  wanted: { bg: 'bg-orange-600', text: 'text-orange-100' },
  missing: { bg: 'bg-red-600', text: 'text-red-100' },
  downloading: { bg: 'bg-blue-600', text: 'text-blue-100' },
  snatched: { bg: 'bg-purple-600', text: 'text-purple-100' },
  upcoming: { bg: 'bg-zinc-600', text: 'text-zinc-100' },
  skipped: { bg: 'bg-zinc-600', text: 'text-zinc-100' },
}

interface StatusBadgeProps {
  status: string
  className?: string
}

export function StatusBadge({ status, className = '' }: StatusBadgeProps) {
  const style = STATUS_STYLES[status] || STATUS_STYLES.missing
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${style.bg} ${style.text} ${className}`}>
      {status}
    </span>
  )
}
