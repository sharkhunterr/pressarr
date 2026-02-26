import { useState, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Trash2, Pencil, Loader2 } from 'lucide-react'
import { toast } from 'sonner'

import {
  getNotifications,
  createNotification,
  updateNotification,
  deleteNotification,
  testNotification,
  type NotificationChannel,
} from '@/api/notifications'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Switch } from '@/components/ui/switch'
import {
  Dialog,
  DialogContent,
  DialogFooter,
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

const NOTIFICATION_TYPES = ['discord', 'gotify', 'telegram', 'webhook']

const EVENT_KEYS = ['onGrab', 'onDownload', 'onImport', 'onUpgrade', 'onError'] as const

interface FormState {
  name: string
  type: string
  enabled: boolean
  onGrab: boolean
  onDownload: boolean
  onImport: boolean
  onUpgrade: boolean
  onError: boolean
  settings: Record<string, string>
}

function emptyForm(): FormState {
  return {
    name: '',
    type: 'discord',
    enabled: true,
    onGrab: true,
    onDownload: true,
    onImport: true,
    onUpgrade: true,
    onError: true,
    settings: {},
  }
}

function channelToForm(ch: NotificationChannel): FormState {
  return {
    name: ch.name,
    type: ch.type,
    enabled: ch.enabled,
    onGrab: ch.onGrab,
    onDownload: ch.onDownload,
    onImport: ch.onImport,
    onUpgrade: ch.onUpgrade,
    onError: ch.onError,
    settings: { ...ch.settings },
  }
}

function typeIcon(type: string): string {
  switch (type) {
    case 'discord':
      return 'D'
    case 'gotify':
      return 'G'
    case 'telegram':
      return 'T'
    case 'webhook':
      return 'W'
    default:
      return '?'
  }
}

export default function Notifications() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()

  const [dialogOpen, setDialogOpen] = useState(false)
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [deletingChannel, setDeletingChannel] = useState<NotificationChannel | null>(null)
  const [form, setForm] = useState<FormState>(emptyForm())
  const [testing, setTesting] = useState(false)

  const { data: channels = [], isLoading } = useQuery({
    queryKey: ['notifications'],
    queryFn: getNotifications,
  })

  const invalidate = useCallback(
    () => queryClient.invalidateQueries({ queryKey: ['notifications'] }),
    [queryClient],
  )

  const createMutation = useMutation({
    mutationFn: (data: Partial<NotificationChannel>) => createNotification(data),
    onSuccess: () => {
      invalidate()
      setDialogOpen(false)
      toast.success(t('notifications.created'))
    },
    onError: () => toast.error(t('notifications.createError')),
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<NotificationChannel> }) =>
      updateNotification(id, data),
    onSuccess: () => {
      invalidate()
      setDialogOpen(false)
      toast.success(t('notifications.updated'))
    },
    onError: () => toast.error(t('notifications.updateError')),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteNotification(id),
    onSuccess: () => {
      invalidate()
      setDeleteDialogOpen(false)
      setDeletingChannel(null)
      toast.success(t('notifications.deleted'))
    },
    onError: () => toast.error(t('notifications.deleteError')),
  })

  function openCreate() {
    setEditingId(null)
    setForm(emptyForm())
    setDialogOpen(true)
  }

  function openEdit(channel: NotificationChannel) {
    setEditingId(channel.id)
    setForm(channelToForm(channel))
    setDialogOpen(true)
  }

  function openDelete(channel: NotificationChannel) {
    setDeletingChannel(channel)
    setDeleteDialogOpen(true)
  }

  function updateSetting(key: string, value: string) {
    setForm((prev) => ({
      ...prev,
      settings: { ...prev.settings, [key]: value },
    }))
  }

  function handleSave() {
    const payload: Partial<NotificationChannel> = {
      name: form.name,
      type: form.type,
      enabled: form.enabled,
      onGrab: form.onGrab,
      onDownload: form.onDownload,
      onImport: form.onImport,
      onUpgrade: form.onUpgrade,
      onError: form.onError,
      settings: form.settings,
    }
    if (editingId !== null) {
      updateMutation.mutate({ id: editingId, data: payload })
    } else {
      createMutation.mutate(payload)
    }
  }

  async function handleTest() {
    setTesting(true)
    try {
      const result = await testNotification({
        name: form.name,
        type: form.type,
        enabled: form.enabled,
        settings: form.settings,
      })
      if (result.isValid) {
        toast.success(t('notifications.testSuccess'))
      } else {
        toast.error(result.message || t('notifications.testFailed'))
      }
    } catch {
      toast.error(t('notifications.testFailed'))
    } finally {
      setTesting(false)
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
          {t('notifications.title')}
        </h1>
        <Button onClick={openCreate}>
          <Plus className="size-4" />
          {t('common.add')}
        </Button>
      </div>

      {/* Channels list */}
      <div className="grid gap-4">
        {channels.map((channel) => (
          <Card key={channel.id} className="bg-zinc-950 border-zinc-800">
            <CardHeader className="flex-row items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="size-8 rounded bg-zinc-800 flex items-center justify-center text-sm font-bold text-[#E85D04]">
                  {typeIcon(channel.type)}
                </div>
                <CardTitle className="text-zinc-100">{channel.name}</CardTitle>
                <Badge variant={channel.enabled ? 'default' : 'outline'}>
                  {channel.enabled ? t('notifications.enabled') : t('notifications.disabled')}
                </Badge>
              </div>
              <div className="flex gap-2">
                <Button variant="ghost" size="icon-sm" onClick={() => openEdit(channel)}>
                  <Pencil className="size-4" />
                </Button>
                <Button variant="ghost" size="icon-sm" onClick={() => openDelete(channel)}>
                  <Trash2 className="size-4 text-destructive" />
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-2">
                {EVENT_KEYS.map((key) => (
                  <Badge
                    key={key}
                    variant={channel[key] ? 'secondary' : 'outline'}
                    className={!channel[key] ? 'opacity-40' : ''}
                  >
                    {t(`notifications.${key}`)}
                  </Badge>
                ))}
              </div>
            </CardContent>
          </Card>
        ))}

        {channels.length === 0 && (
          <p className="text-zinc-500 text-center py-8">
            {t('notifications.noChannels')}
          </p>
        )}
      </div>

      {/* Create / Edit Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="sm:max-w-lg bg-zinc-950 border-zinc-800 max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="text-zinc-100">
              {editingId !== null
                ? t('notifications.editTitle')
                : t('notifications.createTitle')}
            </DialogTitle>
          </DialogHeader>

          <div className="grid gap-4 py-2">
            {/* Name */}
            <div className="grid gap-1.5">
              <label className="text-sm font-medium text-zinc-300">
                {t('notifications.name')}
              </label>
              <Input
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder={t('notifications.namePlaceholder')}
                className="bg-zinc-900 border-zinc-700 text-zinc-100"
              />
            </div>

            {/* Type */}
            <div className="grid gap-1.5">
              <label className="text-sm font-medium text-zinc-300">
                {t('notifications.type')}
              </label>
              <Select
                value={form.type}
                onValueChange={(v) => setForm({ ...form, type: v, settings: {} })}
                disabled={editingId !== null}
              >
                <SelectTrigger className="bg-zinc-900 border-zinc-700 text-zinc-100 w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {NOTIFICATION_TYPES.map((type) => (
                    <SelectItem key={type} value={type}>
                      {t(`notifications.type_${type}`, type)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Enabled toggle */}
            <div className="flex items-center justify-between">
              <label className="text-sm font-medium text-zinc-300">
                {t('notifications.enabled')}
              </label>
              <Switch
                checked={form.enabled}
                onCheckedChange={(checked) => setForm({ ...form, enabled: checked === true })}
              />
            </div>

            {/* Type-specific settings */}
            {form.type === 'discord' && (
              <div className="grid gap-1.5">
                <label className="text-sm font-medium text-zinc-300">
                  {t('notifications.webhookUrl')}
                </label>
                <Input
                  value={form.settings.webhookUrl ?? ''}
                  onChange={(e) => updateSetting('webhookUrl', e.target.value)}
                  placeholder="https://discord.com/api/webhooks/..."
                  className="bg-zinc-900 border-zinc-700 text-zinc-100"
                />
              </div>
            )}

            {form.type === 'gotify' && (
              <>
                <div className="grid gap-1.5">
                  <label className="text-sm font-medium text-zinc-300">
                    {t('notifications.serverUrl')}
                  </label>
                  <Input
                    value={form.settings.serverUrl ?? ''}
                    onChange={(e) => updateSetting('serverUrl', e.target.value)}
                    placeholder="https://gotify.example.com"
                    className="bg-zinc-900 border-zinc-700 text-zinc-100"
                  />
                </div>
                <div className="grid gap-1.5">
                  <label className="text-sm font-medium text-zinc-300">
                    {t('notifications.appToken')}
                  </label>
                  <Input
                    value={form.settings.appToken ?? ''}
                    onChange={(e) => updateSetting('appToken', e.target.value)}
                    placeholder={t('notifications.appTokenPlaceholder')}
                    className="bg-zinc-900 border-zinc-700 text-zinc-100"
                  />
                </div>
                <div className="grid gap-1.5">
                  <label className="text-sm font-medium text-zinc-300">
                    {t('notifications.priority')}
                  </label>
                  <Input
                    type="number"
                    value={form.settings.priority ?? '5'}
                    onChange={(e) => updateSetting('priority', e.target.value)}
                    className="bg-zinc-900 border-zinc-700 text-zinc-100"
                  />
                </div>
              </>
            )}

            {form.type === 'telegram' && (
              <>
                <div className="grid gap-1.5">
                  <label className="text-sm font-medium text-zinc-300">
                    {t('notifications.botToken')}
                  </label>
                  <Input
                    value={form.settings.botToken ?? ''}
                    onChange={(e) => updateSetting('botToken', e.target.value)}
                    placeholder={t('notifications.botTokenPlaceholder')}
                    className="bg-zinc-900 border-zinc-700 text-zinc-100"
                  />
                </div>
                <div className="grid gap-1.5">
                  <label className="text-sm font-medium text-zinc-300">
                    {t('notifications.chatId')}
                  </label>
                  <Input
                    value={form.settings.chatId ?? ''}
                    onChange={(e) => updateSetting('chatId', e.target.value)}
                    placeholder={t('notifications.chatIdPlaceholder')}
                    className="bg-zinc-900 border-zinc-700 text-zinc-100"
                  />
                </div>
              </>
            )}

            {form.type === 'webhook' && (
              <>
                <div className="grid gap-1.5">
                  <label className="text-sm font-medium text-zinc-300">
                    {t('notifications.webhookUrl')}
                  </label>
                  <Input
                    value={form.settings.url ?? ''}
                    onChange={(e) => updateSetting('url', e.target.value)}
                    placeholder="https://example.com/hook"
                    className="bg-zinc-900 border-zinc-700 text-zinc-100"
                  />
                </div>
                <div className="grid gap-1.5">
                  <label className="text-sm font-medium text-zinc-300">
                    {t('notifications.method')}
                  </label>
                  <Select
                    value={form.settings.method ?? 'POST'}
                    onValueChange={(v) => updateSetting('method', v)}
                  >
                    <SelectTrigger className="bg-zinc-900 border-zinc-700 text-zinc-100 w-full">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="POST">POST</SelectItem>
                      <SelectItem value="PUT">PUT</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="grid gap-1.5">
                  <label className="text-sm font-medium text-zinc-300">
                    {t('notifications.headers')}
                  </label>
                  <Input
                    value={form.settings.headers ?? ''}
                    onChange={(e) => updateSetting('headers', e.target.value)}
                    placeholder='{"Content-Type": "application/json"}'
                    className="bg-zinc-900 border-zinc-700 text-zinc-100"
                  />
                </div>
              </>
            )}

            {/* Event toggles */}
            <div className="grid gap-1.5">
              <label className="text-sm font-medium text-zinc-300 mb-1">
                {t('notifications.events')}
              </label>
              <div className="rounded-md border border-zinc-800 divide-y divide-zinc-800">
                {EVENT_KEYS.map((key) => (
                  <div key={key} className="flex items-center justify-between px-3 py-2">
                    <span className="text-sm text-zinc-300">
                      {t(`notifications.${key}`)}
                    </span>
                    <Switch
                      checked={form[key]}
                      onCheckedChange={(checked) =>
                        setForm({ ...form, [key]: checked === true })
                      }
                    />
                  </div>
                ))}
              </div>
            </div>
          </div>

          <DialogFooter className="gap-2">
            <Button
              variant="outline"
              onClick={handleTest}
              disabled={testing}
            >
              {testing && <Loader2 className="size-4 animate-spin" />}
              {t('common.test')}
            </Button>
            <div className="flex-1" />
            <Button variant="outline" onClick={() => setDialogOpen(false)}>
              {t('common.cancel')}
            </Button>
            <Button
              onClick={handleSave}
              disabled={
                !form.name.trim() ||
                createMutation.isPending ||
                updateMutation.isPending
              }
            >
              {t('common.save')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent className="sm:max-w-md bg-zinc-950 border-zinc-800">
          <DialogHeader>
            <DialogTitle className="text-zinc-100">
              {t('notifications.deleteTitle')}
            </DialogTitle>
          </DialogHeader>
          <p className="text-sm text-zinc-400">
            {t('notifications.deleteConfirm', { name: deletingChannel?.name })}
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteDialogOpen(false)}>
              {t('common.cancel')}
            </Button>
            <Button
              variant="destructive"
              disabled={deleteMutation.isPending}
              onClick={() => deletingChannel && deleteMutation.mutate(deletingChannel.id)}
            >
              {t('common.delete')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
