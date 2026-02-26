import { useState, useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Save, Loader2, Copy } from 'lucide-react'
import { toast } from 'sonner'

import { getNamingTemplate, saveNamingTemplate } from '@/api/system'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'

const VARIABLES = [
  { token: '{magazine_title}', example: 'National Geographic' },
  { token: '{number}', example: '42' },
  { token: '{volume}', example: '12' },
  { token: '{year}', example: '2025' },
  { token: '{month}', example: '03' },
  { token: '{quality}', example: 'TruePDF' },
  { token: '{format}', example: 'pdf' },
  { token: '{group}', example: 'TeamRelease' },
  { token: '{language}', example: 'en' },
]

const SAMPLE_DATA: Record<string, string> = {
  '{magazine_title}': 'National Geographic',
  '{number}': '42',
  '{volume}': '12',
  '{year}': '2025',
  '{month}': '03',
  '{quality}': 'TruePDF',
  '{format}': 'pdf',
  '{group}': 'TeamRelease',
  '{language}': 'en',
  // French aliases
  '{titre_magazine}': 'National Geographic',
  '{titre}': 'National Geographic',
  '{numero}': '42',
  '{annee}': '2025',
  '{mois}': '03',
  '{qualite}': 'TruePDF',
  '{groupe}': 'TeamRelease',
  '{langue}': 'en',
}

function applyTemplate(template: string): string {
  let result = template
  for (const [token, value] of Object.entries(SAMPLE_DATA)) {
    result = result.split(token).join(value)
  }
  return result
}

export default function NamingTemplate() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()

  const [template, setTemplate] = useState('')
  const [initialized, setInitialized] = useState(false)

  const { isLoading } = useQuery({
    queryKey: ['namingTemplate'],
    queryFn: getNamingTemplate,
    select: (data) => {
      if (!initialized) {
        setTemplate(data.template)
        setInitialized(true)
      }
      return data
    },
  })

  const saveMutation = useMutation({
    mutationFn: () => saveNamingTemplate({ template }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['namingTemplate'] })
      toast.success(t('naming.saved'))
    },
    onError: () => toast.error(t('naming.saveError')),
  })

  const preview = useMemo(() => applyTemplate(template), [template])

  function insertVariable(token: string) {
    setTemplate((prev) => prev + token)
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
          {t('naming.title')}
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
        {/* Template Input */}
        <Card className="bg-zinc-950 border-zinc-800">
          <CardHeader>
            <CardTitle className="text-zinc-100">{t('naming.template')}</CardTitle>
          </CardHeader>
          <CardContent>
            <Input
              value={template}
              onChange={(e) => setTemplate(e.target.value)}
              placeholder={t('naming.templatePlaceholder')}
              className="bg-zinc-900 border-zinc-700 text-zinc-100 font-mono"
            />
          </CardContent>
        </Card>

        {/* Live Preview */}
        <Card className="bg-zinc-950 border-zinc-800">
          <CardHeader>
            <CardTitle className="text-zinc-100">{t('naming.preview')}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="bg-zinc-900 border border-zinc-700 rounded-md px-3 py-2 text-sm font-mono text-[#E85D04]">
              {preview || t('naming.previewEmpty')}
            </div>
          </CardContent>
        </Card>

        {/* Variable Reference */}
        <Card className="bg-zinc-950 border-zinc-800">
          <CardHeader>
            <CardTitle className="text-zinc-100">{t('naming.variables')}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid gap-2">
              {VARIABLES.map((v) => (
                <div
                  key={v.token}
                  className="flex items-center justify-between py-1.5 px-2 rounded-md hover:bg-zinc-900 transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <Badge variant="outline" className="font-mono text-xs">
                      {v.token}
                    </Badge>
                    <span className="text-sm text-zinc-400">
                      {t('naming.example')}: <span className="text-zinc-300">{v.example}</span>
                    </span>
                  </div>
                  <Button
                    variant="ghost"
                    size="xs"
                    onClick={() => insertVariable(v.token)}
                    title={t('naming.insert')}
                  >
                    <Copy className="size-3" />
                  </Button>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
