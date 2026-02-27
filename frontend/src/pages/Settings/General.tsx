import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Save, Loader2, AlertTriangle } from 'lucide-react'
import { toast } from 'sonner'

import { getGeneralSettings, saveGeneralSettings } from '@/api/system'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Switch } from '@/components/ui/switch'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

const LOG_LEVELS = ['debug', 'info', 'warning', 'error']
const IMPORT_MODES = ['copy', 'move', 'copy_delete'] as const

export default function General() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()

  const [port, setPort] = useState(8787)
  const [logLevel, setLogLevel] = useState('info')
  const [authEnabled, setAuthEnabled] = useState(false)
  const [taskInterval, setTaskInterval] = useState(60)
  const [importMode, setImportMode] = useState('copy')
  const [initialized, setInitialized] = useState(false)

  const { isLoading } = useQuery({
    queryKey: ['generalSettings'],
    queryFn: getGeneralSettings,
    select: (data) => {
      if (!initialized) {
        setPort(data.port ?? 8787)
        setLogLevel(data.logLevel ?? 'info')
        setAuthEnabled(data.authEnabled ?? false)
        setTaskInterval(data.scheduledTaskInterval ?? 60)
        setImportMode(data.importMode ?? 'copy')
        setInitialized(true)
      }
      return data
    },
  })

  const saveMutation = useMutation({
    mutationFn: () =>
      saveGeneralSettings({
        port,
        logLevel,
        authEnabled,
        scheduledTaskInterval: taskInterval,
        importMode,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['generalSettings'] })
      toast.success(t('general.saved'))
    },
    onError: () => toast.error(t('general.saveError')),
  })

  if (isLoading) {
    return (
      <div className="p-4 lg:p-8 text-zinc-400">
        {t('common.loading')}
      </div>
    )
  }

  return (
    <div className="p-4 lg:p-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-zinc-100">
          {t('general.title')}
        </h1>
        <Button onClick={() => saveMutation.mutate()} disabled={saveMutation.isPending}>
          {saveMutation.isPending ? (
            <Loader2 className="size-4 animate-spin" />
          ) : (
            <Save className="size-4" />
          )}
          {t('common.save')}
        </Button>
      </div>

      <div className="grid gap-6">
        {/* Host Settings */}
        <Card className="bg-zinc-950 border-zinc-800">
          <CardHeader>
            <CardTitle className="text-zinc-100">{t('general.hostSettings')}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-1.5">
              <label className="text-sm font-medium text-zinc-300">
                {t('general.port')}
              </label>
              <Input
                type="number"
                value={port}
                onChange={(e) => setPort(parseInt(e.target.value) || 8787)}
                className="bg-zinc-900 border-zinc-700 text-zinc-100 max-w-32"
              />
              <p className="flex items-center gap-1.5 text-xs text-yellow-500">
                <AlertTriangle className="size-3" />
                {t('general.portWarning')}
              </p>
            </div>
          </CardContent>
        </Card>

        {/* Logging */}
        <Card className="bg-zinc-950 border-zinc-800">
          <CardHeader>
            <CardTitle className="text-zinc-100">{t('general.logging')}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid gap-1.5">
              <label className="text-sm font-medium text-zinc-300">
                {t('general.logLevel')}
              </label>
              <Select value={logLevel} onValueChange={setLogLevel}>
                <SelectTrigger className="bg-zinc-900 border-zinc-700 text-zinc-100 max-w-48">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {LOG_LEVELS.map((level) => (
                    <SelectItem key={level} value={level}>
                      {t(`general.logLevel_${level}`)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </CardContent>
        </Card>

        {/* Security */}
        <Card className="bg-zinc-950 border-zinc-800">
          <CardHeader>
            <CardTitle className="text-zinc-100">{t('general.security')}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-between">
              <div>
                <label className="text-sm font-medium text-zinc-300">
                  {t('general.authEnabled')}
                </label>
                <p className="text-xs text-zinc-500 mt-0.5">
                  {t('general.authDescription')}
                </p>
              </div>
              <Switch
                checked={authEnabled}
                onCheckedChange={(checked) => setAuthEnabled(checked === true)}
              />
            </div>
          </CardContent>
        </Card>

        {/* Scheduled Tasks */}
        <Card className="bg-zinc-950 border-zinc-800">
          <CardHeader>
            <CardTitle className="text-zinc-100">{t('general.scheduledTasks')}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid gap-1.5">
              <label className="text-sm font-medium text-zinc-300">
                {t('general.taskInterval')}
              </label>
              <div className="flex items-center gap-2">
                <Input
                  type="number"
                  value={taskInterval}
                  onChange={(e) => setTaskInterval(parseInt(e.target.value) || 60)}
                  min={1}
                  className="bg-zinc-900 border-zinc-700 text-zinc-100 max-w-24"
                />
                <span className="text-sm text-zinc-400">{t('general.minutes')}</span>
              </div>
              <p className="text-xs text-zinc-500">
                {t('general.taskIntervalDescription')}
              </p>
            </div>
          </CardContent>
        </Card>

        {/* Import Mode */}
        <Card className="bg-zinc-950 border-zinc-800">
          <CardHeader>
            <CardTitle className="text-zinc-100">{t('general.importMode')}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid gap-1.5">
              <label className="text-sm font-medium text-zinc-300">
                {t('general.importModeLabel')}
              </label>
              <Select value={importMode} onValueChange={setImportMode}>
                <SelectTrigger className="bg-zinc-900 border-zinc-700 text-zinc-100 max-w-64">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {IMPORT_MODES.map((mode) => (
                    <SelectItem key={mode} value={mode}>
                      {t(`general.importMode_${mode}`)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-zinc-500">
                {t('general.importModeDescription')}
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
