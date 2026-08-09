/**
 * SystemVersionCard — porté depuis romarr.
 *
 * Backend chain :
 *  - React Query 30 min staleTime + backend cache 1 h (in-process).
 *  - Bouton « Vérifier maintenant » → mutation force=true qui bypass
 *    les deux caches et met à jour la query key.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, ExternalLink, RefreshCw, Rocket } from 'lucide-react'
import { useTranslation } from 'react-i18next'

import { getVersionCheck, type VersionCheck } from '@/api/system'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'

const KEY = ['system', 'version-check'] as const

export function SystemVersionCard() {
  const { t } = useTranslation()
  const qc = useQueryClient()

  const v = useQuery<VersionCheck>({
    queryKey: KEY,
    queryFn: () => getVersionCheck(false),
    staleTime: 30 * 60_000,
  })

  const force = useMutation<VersionCheck, Error, void>({
    mutationFn: () => getVersionCheck(true),
    onSuccess: (data) => qc.setQueryData(KEY, data),
  })

  const data = v.data
  const isUpdateAvailable = data?.updateAvailable ?? false
  const hasError = data?.error
  const isBusy = v.isPending || force.isPending

  return (
    <Card className="bg-zinc-950 border-zinc-800">
      <CardHeader className="flex flex-row items-start justify-between gap-3 space-y-0">
        <div className="min-w-0">
          <CardTitle className="text-zinc-100 flex items-center gap-2">
            <Rocket className="size-5" />
            {t('system.versionCard.title', 'Version de Pressarr')}
          </CardTitle>
          <p className="mt-1 text-sm text-zinc-500">
            {t(
              'system.versionCard.subtitle',
              'Compare la version installée à la dernière release GitHub.'
            )}
          </p>
        </div>
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={() => force.mutate()}
          disabled={isBusy}
          className="shrink-0 border-zinc-700 text-zinc-200 hover:bg-zinc-800"
        >
          <RefreshCw
            className={`size-3 ${force.isPending ? 'animate-spin' : ''}`}
            aria-hidden="true"
          />
          {force.isPending
            ? t('system.versionCard.checking', 'Vérification…')
            : t('system.versionCard.checkNow', 'Vérifier')}
        </Button>
      </CardHeader>
      <CardContent>
        {v.isPending && (
          <p className="text-xs text-zinc-500">
            {t('system.versionCard.loading', 'Interrogation de GitHub…')}
          </p>
        )}
        {v.isError && (
          <p role="alert" className="text-xs text-red-400">
            {v.error.message}
          </p>
        )}
        {data && (
          <div className="flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center gap-1.5 rounded border border-zinc-700 bg-zinc-900/60 px-2 py-0.5 text-xs">
              <span className="text-zinc-500">
                {t('system.versionCard.installed', 'Installée')}
              </span>
              <span className="font-mono font-semibold text-zinc-100">
                v{data.current}
              </span>
            </span>

            {hasError ? (
              <span className="rounded border border-red-800/60 bg-red-950/40 px-2 py-0.5 text-xs text-red-300">
                {data.error}
              </span>
            ) : isUpdateAvailable ? (
              <a
                href={data.releaseUrl ?? '#'}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1.5 rounded border border-amber-700/60 bg-amber-950/40 px-2 py-0.5 text-xs text-amber-300 hover:bg-amber-950/60"
                title={t(
                  'system.versionCard.viewReleaseTooltip',
                  'Voir les notes de release sur GitHub'
                )}
              >
                <span className="font-mono text-amber-400 line-through decoration-amber-700">
                  v{data.current}
                </span>
                <span aria-hidden="true">→</span>
                <span className="font-mono font-semibold">v{data.latest}</span>
                <ExternalLink size={11} aria-hidden="true" />
              </a>
            ) : (
              <span className="inline-flex items-center gap-1 rounded border border-emerald-800/50 bg-emerald-950/30 px-2 py-0.5 text-xs text-emerald-300">
                <CheckCircle2 size={12} aria-hidden="true" />
                {t('system.versionCard.upToDate', 'À jour')}
              </span>
            )}

            {data.repo && (
              <a
                href={`https://github.com/${data.repo}`}
                target="_blank"
                rel="noreferrer"
                className="text-[10px] text-zinc-500 hover:text-zinc-300 hover:underline"
              >
                {data.repo}
              </a>
            )}
          </div>
        )}
        {data?.publishedAt && (
          <p className="mt-2 text-[10px] text-zinc-500">
            {t('system.versionCard.publishedAt', 'Release publiée le')} :{' '}
            {new Date(data.publishedAt).toLocaleString()}
          </p>
        )}
      </CardContent>
    </Card>
  )
}
