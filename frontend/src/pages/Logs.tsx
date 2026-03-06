import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'

import { getLogs, type LogEntry } from '@/api/system'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { Switch } from '@/components/ui/switch'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

const LOG_LEVELS = ['DEBUG', 'INFO', 'WARNING', 'ERROR']

function levelColor(level: string) {
  switch (level) {
    case 'DEBUG':
      return 'bg-zinc-700 text-zinc-300'
    case 'INFO':
      return 'bg-blue-900/60 text-blue-300'
    case 'WARNING':
      return 'bg-yellow-900/60 text-yellow-300'
    case 'ERROR':
      return 'bg-red-900/60 text-red-300'
    default:
      return 'bg-zinc-700 text-zinc-300'
  }
}

export default function Logs() {
  const { t } = useTranslation()

  const [level, setLevel] = useState<string>('all')
  const [loggerFilter, setLoggerFilter] = useState('')
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [selected, setSelected] = useState<LogEntry | null>(null)

  const { data: logs = [], isLoading } = useQuery({
    queryKey: ['logs', level, loggerFilter],
    queryFn: () =>
      getLogs({
        limit: 500,
        level: level !== 'all' ? level : undefined,
        logger: loggerFilter || undefined,
      }),
    refetchInterval: autoRefresh ? 5000 : false,
  })

  if (isLoading) {
    return (
      <div className="p-4 lg:p-8">
        <Skeleton className="h-8 w-32 bg-zinc-800 mb-6" />
        <div className="space-y-1">
          {[1, 2, 3, 4, 5, 6, 7, 8].map((i) => (
            <Skeleton key={i} className="h-6 bg-zinc-800" />
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="p-4 lg:p-8 flex flex-col h-[calc(100vh-64px)]">
      <h1 className="text-2xl font-bold text-zinc-100 mb-4">{t('logs.title')}</h1>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3 mb-4">
        <Select value={level} onValueChange={setLevel}>
          <SelectTrigger className="w-full sm:w-40 bg-zinc-900 border-zinc-700 text-zinc-100">
            <SelectValue placeholder={t('logs.allLevels')} />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{t('logs.allLevels')}</SelectItem>
            {LOG_LEVELS.map((l) => (
              <SelectItem key={l} value={l}>{l}</SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Input
          value={loggerFilter}
          onChange={(e) => setLoggerFilter(e.target.value)}
          placeholder={t('logs.filterLogger')}
          className="w-full sm:w-56 bg-zinc-900 border-zinc-700 text-zinc-100 font-mono text-sm"
        />

        <div className="flex items-center gap-2 sm:ml-auto">
          <Switch checked={autoRefresh} onCheckedChange={setAutoRefresh} />
          <span className="text-sm text-zinc-400">{t('logs.autoRefresh')}</span>
        </div>
      </div>

      {/* Log entries */}
      {logs.length === 0 ? (
        <p className="text-zinc-500 text-center py-8">{t('logs.empty')}</p>
      ) : (
        <div className="flex-1 overflow-y-auto rounded-lg border border-zinc-800 bg-zinc-950">
          {/* Desktop: inline rows */}
          <div className="hidden sm:block p-2 space-y-0.5">
            {logs.map((entry: LogEntry, i: number) => (
              <div
                key={i}
                className="flex items-baseline gap-2 px-2 py-1 rounded hover:bg-zinc-900/50 font-mono text-xs cursor-pointer"
                onClick={() => setSelected(entry)}
              >
                <span className="text-zinc-500 shrink-0">{entry.timestamp}</span>
                <Badge className={`${levelColor(entry.level)} text-[10px] px-1.5 py-0 font-mono shrink-0`}>
                  {entry.level}
                </Badge>
                <span className="text-zinc-500 shrink-0 truncate max-w-48">{entry.logger}</span>
                <span className="text-zinc-200 truncate flex-1">{entry.message}</span>
              </div>
            ))}
          </div>

          {/* Mobile: compact cards */}
          <div className="sm:hidden divide-y divide-zinc-800/60">
            {logs.map((entry: LogEntry, i: number) => (
              <button
                key={i}
                type="button"
                className="w-full text-left px-3 py-2.5 hover:bg-zinc-900/50 active:bg-zinc-900"
                onClick={() => setSelected(entry)}
              >
                <div className="flex items-center gap-2 mb-1">
                  <Badge className={`${levelColor(entry.level)} text-[10px] px-1.5 py-0 font-mono shrink-0`}>
                    {entry.level}
                  </Badge>
                  <span className="text-[11px] text-zinc-500 font-mono">{entry.timestamp}</span>
                </div>
                <p className="text-xs text-zinc-200 line-clamp-2">{entry.message}</p>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Detail modal */}
      <Dialog open={!!selected} onOpenChange={(open) => { if (!open) setSelected(null) }}>
        <DialogContent className="sm:max-w-xl bg-zinc-950 border-zinc-800 max-h-[85vh] overflow-hidden flex flex-col">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-zinc-100">
              <Badge className={`${levelColor(selected?.level ?? '')} text-xs px-2 py-0.5 font-mono`}>
                {selected?.level}
              </Badge>
              <span className="text-sm font-normal text-zinc-400">{selected?.timestamp}</span>
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-3 overflow-y-auto">
            <div>
              <span className="text-xs text-zinc-500">Logger</span>
              <p className="text-sm text-zinc-300 font-mono">{selected?.logger}</p>
            </div>
            <div>
              <span className="text-xs text-zinc-500">Message</span>
              <pre className="mt-1 text-sm text-zinc-100 font-mono whitespace-pre-wrap break-all bg-zinc-900 rounded-md p-3 border border-zinc-800 max-h-96 overflow-y-auto">
                {selected?.message}
              </pre>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
