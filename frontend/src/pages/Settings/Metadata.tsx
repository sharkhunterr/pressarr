import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Save, FlaskConical, Loader2 } from 'lucide-react'
import { toast } from 'sonner'

import {
  getMetadataSettings,
  saveMetadataSettings,
  testGoogleBooks,
  testInternetArchive,
  testAnnasArchive,
} from '@/api/system'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Switch } from '@/components/ui/switch'

export default function Metadata() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()

  const [googleApiKey, setGoogleApiKey] = useState('')
  const [iaEnabled, setIaEnabled] = useState(false)
  const [aaEnabled, setAaEnabled] = useState(false)
  const [aaMirror, setAaMirror] = useState('annas-archive.li')
  const [initialized, setInitialized] = useState(false)
  const [testingGoogle, setTestingGoogle] = useState(false)
  const [testingIA, setTestingIA] = useState(false)
  const [testingAA, setTestingAA] = useState(false)

  const { isLoading } = useQuery({
    queryKey: ['metadataSettings'],
    queryFn: getMetadataSettings,
    select: (data) => {
      if (!initialized) {
        setGoogleApiKey(data.googleBooksApiKey ?? '')
        setIaEnabled(data.internetArchiveEnabled ?? false)
        setAaEnabled(data.annasArchiveEnabled ?? false)
        setAaMirror(data.annasArchiveMirror ?? 'annas-archive.li')
        setInitialized(true)
      }
      return data
    },
  })

  const saveMutation = useMutation({
    mutationFn: () =>
      saveMetadataSettings({
        googleBooksApiKey: googleApiKey,
        internetArchiveEnabled: iaEnabled,
        annasArchiveEnabled: aaEnabled,
        annasArchiveMirror: aaMirror,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['metadataSettings'] })
      toast.success(t('metadata.saved'))
    },
    onError: () => toast.error(t('metadata.saveError')),
  })

  async function handleTestGoogle() {
    if (!googleApiKey.trim()) {
      toast.error(t('metadata.googleKeyRequired'))
      return
    }
    setTestingGoogle(true)
    try {
      const result = await testGoogleBooks(googleApiKey)
      if (result.isValid) {
        toast.success(t('metadata.googleTestSuccess'))
      } else {
        toast.error(result.message || t('metadata.googleTestFailed'))
      }
    } catch {
      toast.error(t('metadata.googleTestFailed'))
    } finally {
      setTestingGoogle(false)
    }
  }

  async function handleTestIA() {
    setTestingIA(true)
    try {
      const result = await testInternetArchive()
      if (result.isValid) {
        toast.success(t('metadata.iaTestSuccess'))
      } else {
        toast.error(result.message || t('metadata.iaTestFailed'))
      }
    } catch {
      toast.error(t('metadata.iaTestFailed'))
    } finally {
      setTestingIA(false)
    }
  }

  async function handleTestAA() {
    if (!aaMirror.trim()) {
      toast.error(t('metadata.aaMirrorRequired'))
      return
    }
    setTestingAA(true)
    try {
      const result = await testAnnasArchive(aaMirror)
      if (result.isValid) {
        toast.success(t('metadata.aaTestSuccess'))
      } else {
        toast.error(result.message || t('metadata.aaTestFailed'))
      }
    } catch {
      toast.error(t('metadata.aaTestFailed'))
    } finally {
      setTestingAA(false)
    }
  }

  if (isLoading) {
    return (
      <div className="p-8 text-zinc-400">
        {t('common.loading')}
      </div>
    )
  }

  return (
    <div className="p-8 max-w-4xl">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-zinc-100">
          {t('metadata.title')}
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
        {/* Google Books */}
        <Card className="bg-zinc-950 border-zinc-800">
          <CardHeader>
            <CardTitle className="text-zinc-100">{t('metadata.googleBooks')}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-1.5">
              <label className="text-sm font-medium text-zinc-300">
                {t('metadata.apiKey')}
              </label>
              <Input
                value={googleApiKey}
                onChange={(e) => setGoogleApiKey(e.target.value)}
                type="password"
                placeholder={t('metadata.apiKeyPlaceholder')}
                className="bg-zinc-900 border-zinc-700 text-zinc-100"
              />
            </div>
            <Button
              variant="outline"
              onClick={handleTestGoogle}
              disabled={testingGoogle}
            >
              {testingGoogle ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <FlaskConical className="size-4" />
              )}
              {t('metadata.testGoogleBooks')}
            </Button>
          </CardContent>
        </Card>

        {/* Internet Archive */}
        <Card className="bg-zinc-950 border-zinc-800">
          <CardHeader>
            <CardTitle className="text-zinc-100">{t('metadata.internetArchive')}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between">
              <label className="text-sm font-medium text-zinc-300">
                {t('metadata.iaEnabled')}
              </label>
              <Switch
                checked={iaEnabled}
                onCheckedChange={(checked) => setIaEnabled(checked === true)}
              />
            </div>
            <Button
              variant="outline"
              onClick={handleTestIA}
              disabled={testingIA}
            >
              {testingIA ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <FlaskConical className="size-4" />
              )}
              {t('metadata.testInternetArchive')}
            </Button>
          </CardContent>
        </Card>

        {/* Anna's Archive */}
        <Card className="bg-zinc-950 border-zinc-800">
          <CardHeader>
            <CardTitle className="text-zinc-100">{t('metadata.annasArchive')}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between">
              <label className="text-sm font-medium text-zinc-300">
                {t('metadata.aaEnabled')}
              </label>
              <Switch
                checked={aaEnabled}
                onCheckedChange={(checked) => setAaEnabled(checked === true)}
              />
            </div>
            <div className="grid gap-1.5">
              <label className="text-sm font-medium text-zinc-300">
                {t('metadata.aaMirror')}
              </label>
              <Input
                value={aaMirror}
                onChange={(e) => setAaMirror(e.target.value)}
                placeholder="annas-archive.li"
                className="bg-zinc-900 border-zinc-700 text-zinc-100"
              />
            </div>
            <Button
              variant="outline"
              onClick={handleTestAA}
              disabled={testingAA}
            >
              {testingAA ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <FlaskConical className="size-4" />
              )}
              {t('metadata.testAnnasArchive')}
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
