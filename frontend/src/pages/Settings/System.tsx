import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import { Activity, Database, HardDrive, Clock, Server } from 'lucide-react'

import { getStatus, getHealth, getRootFolders } from '@/api/system'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { SystemVersionCard } from '@/components/SystemVersionCard'

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(1024))
  return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${units[i]}`
}

function formatUptime(seconds: number): string {
  const days = Math.floor(seconds / 86400)
  const hours = Math.floor((seconds % 86400) / 3600)
  const mins = Math.floor((seconds % 3600) / 60)
  const parts: string[] = []
  if (days > 0) parts.push(`${days}d`)
  if (hours > 0) parts.push(`${hours}h`)
  parts.push(`${mins}m`)
  return parts.join(' ')
}

function HealthDot({ ok }: { ok: boolean | undefined }) {
  if (ok === undefined) {
    return <span className="inline-block size-2.5 rounded-full bg-zinc-600" />
  }
  return (
    <span
      className={`inline-block size-2.5 rounded-full ${ok ? 'bg-green-500' : 'bg-red-500'}`}
    />
  )
}

function StatCard({
  label,
  value,
  icon: Icon,
}: {
  label: string
  value: string | number
  icon: React.ComponentType<{ className?: string }>
}) {
  return (
    <Card className="bg-zinc-950 border-zinc-800">
      <CardContent className="flex items-center gap-4 py-4">
        <div className="flex items-center justify-center size-10 rounded-lg bg-zinc-900">
          <Icon className="size-5 text-[#7C3AED]" />
        </div>
        <div>
          <p className="text-2xl font-bold text-zinc-100">{value}</p>
          <p className="text-xs text-zinc-400">{label}</p>
        </div>
      </CardContent>
    </Card>
  )
}

export default function System() {
  const { t } = useTranslation()

  const { data: status, isLoading: statusLoading } = useQuery({
    queryKey: ['systemStatus'],
    queryFn: getStatus,
    refetchInterval: 30_000,
  })

  const { data: health, isLoading: healthLoading } = useQuery({
    queryKey: ['systemHealth'],
    queryFn: getHealth,
    refetchInterval: 30_000,
  })

  const { data: rootFolders = [] } = useQuery({
    queryKey: ['rootFolders'],
    queryFn: getRootFolders,
  })

  const loading = statusLoading || healthLoading

  return (
    <div className="p-4 lg:p-8">
      <h1 className="text-2xl font-bold text-zinc-100 mb-6">
        {t('system.title')}
      </h1>

      {loading ? (
        <div className="grid gap-4">
          <Skeleton className="h-24 bg-zinc-800" />
          <Skeleton className="h-24 bg-zinc-800" />
          <Skeleton className="h-24 bg-zinc-800" />
        </div>
      ) : (
        <div className="grid gap-6">
          {/* Update checker (GitHub release vs installed) — placé en
              premier pour être la première info scannée par l'oeil. */}
          <SystemVersionCard />

          {/* Version & Uptime */}
          <Card className="bg-zinc-950 border-zinc-800">
            <CardHeader>
              <CardTitle className="text-zinc-100 flex items-center gap-2">
                <Server className="size-5" />
                {t('system.serverInfo')}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-sm text-zinc-400">{t('system.version')}</p>
                  <p className="text-lg font-medium text-zinc-100">
                    {status?.version ?? '-'}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-zinc-400">{t('system.uptime')}</p>
                  <p className="text-lg font-medium text-zinc-100 flex items-center gap-2">
                    <Clock className="size-4 text-zinc-400" />
                    {status ? formatUptime(status.uptimeSeconds) : '-'}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Health */}
          <Card className="bg-zinc-950 border-zinc-800">
            <CardHeader>
              <CardTitle className="text-zinc-100 flex items-center gap-2">
                <Activity className="size-5" />
                {t('system.health')}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid gap-3">
                <div className="flex items-center gap-3">
                  <HealthDot ok={health?.database} />
                  <span className="text-sm text-zinc-300">{t('system.database')}</span>
                </div>
                <div className="flex items-center gap-3">
                  <HealthDot ok={health?.indexer} />
                  <span className="text-sm text-zinc-300">{t('system.indexerHealth')}</span>
                </div>
                <div className="flex items-center gap-3">
                  <HealthDot ok={health?.downloadClient} />
                  <span className="text-sm text-zinc-300">{t('system.downloadClientHealth')}</span>
                </div>
                {health?.message && (
                  <p className="text-xs text-zinc-500 mt-1">{health.message}</p>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Global Stats */}
          <div>
            <h2 className="text-lg font-semibold text-zinc-100 mb-3 flex items-center gap-2">
              <Database className="size-5" />
              {t('system.stats')}
            </h2>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <StatCard
                label={t('system.magazines')}
                value={status?.magazineCount ?? 0}
                icon={Database}
              />
              <StatCard
                label={t('system.issues')}
                value={status?.issueCount ?? 0}
                icon={Database}
              />
              <StatCard
                label={t('system.available')}
                value={status?.availableCount ?? 0}
                icon={Activity}
              />
              <StatCard
                label={t('system.missing')}
                value={status?.missingCount ?? 0}
                icon={Activity}
              />
            </div>
          </div>

          {/* Disk Space */}
          {rootFolders.length > 0 && (
            <div>
              <h2 className="text-lg font-semibold text-zinc-100 mb-3 flex items-center gap-2">
                <HardDrive className="size-5" />
                {t('system.diskSpace')}
              </h2>
              <div className="grid gap-4">
                {rootFolders.map((folder) => {
                  const total = folder.totalSpace
                  const free = folder.freeSpace
                  const used = total - free
                  const usedPercent = total > 0 ? Math.round((used / total) * 100) : 0
                  const barColor =
                    usedPercent > 90
                      ? 'bg-red-500'
                      : usedPercent > 70
                        ? 'bg-yellow-500'
                        : 'bg-[#7C3AED]'

                  return (
                    <Card key={folder.id} className="bg-zinc-950 border-zinc-800">
                      <CardContent className="py-4">
                        <div className="flex justify-between mb-2">
                          <span className="text-sm font-mono text-zinc-300">
                            {folder.path}
                          </span>
                          <span className="text-sm text-zinc-400">
                            {formatBytes(free)} {t('system.freeOf')} {formatBytes(total)}
                          </span>
                        </div>
                        <div className="w-full h-2 bg-zinc-800 rounded-full overflow-hidden">
                          <div
                            className={`h-full rounded-full transition-all ${barColor}`}
                            style={{ width: `${usedPercent}%` }}
                          />
                        </div>
                        <p className="text-xs text-zinc-500 mt-1">
                          {usedPercent}% {t('system.used')}
                        </p>
                      </CardContent>
                    </Card>
                  )
                })}
              </div>
            </div>
          )}

          {/* Status disk space fallback when root folders aren't configured */}
          {rootFolders.length === 0 && status?.diskSpace && status.diskSpace.length > 0 && (
            <div>
              <h2 className="text-lg font-semibold text-zinc-100 mb-3 flex items-center gap-2">
                <HardDrive className="size-5" />
                {t('system.diskSpace')}
              </h2>
              <div className="grid gap-4">
                {status.diskSpace.map((disk, idx) => {
                  const usedPercent =
                    disk.totalSpace > 0
                      ? Math.round(((disk.totalSpace - disk.freeSpace) / disk.totalSpace) * 100)
                      : 0
                  const barColor =
                    usedPercent > 90
                      ? 'bg-red-500'
                      : usedPercent > 70
                        ? 'bg-yellow-500'
                        : 'bg-[#7C3AED]'

                  return (
                    <Card key={idx} className="bg-zinc-950 border-zinc-800">
                      <CardContent className="py-4">
                        <div className="flex justify-between mb-2">
                          <span className="text-sm font-mono text-zinc-300">
                            {disk.path}
                          </span>
                          <span className="text-sm text-zinc-400">
                            {formatBytes(disk.freeSpace)} {t('system.freeOf')}{' '}
                            {formatBytes(disk.totalSpace)}
                          </span>
                        </div>
                        <div className="w-full h-2 bg-zinc-800 rounded-full overflow-hidden">
                          <div
                            className={`h-full rounded-full transition-all ${barColor}`}
                            style={{ width: `${usedPercent}%` }}
                          />
                        </div>
                        <p className="text-xs text-zinc-500 mt-1">
                          {usedPercent}% {t('system.used')}
                        </p>
                      </CardContent>
                    </Card>
                  )
                })}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
