import { useState, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Pencil, Trash2, FlaskConical, Loader2, Download } from 'lucide-react'
import { toast } from 'sonner'

import {
  getClients,
  createClient,
  updateClient,
  deleteClient,
  testClient,
  type DownloadClient,
} from '@/api/downloads'
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

const CLIENT_TYPES = [
  { value: 'deluge', label: 'Deluge', protocol: 'torrent' },
  { value: 'qbittorrent', label: 'qBittorrent', protocol: 'torrent' },
  { value: 'transmission', label: 'Transmission', protocol: 'torrent' },
  { value: 'sabnzbd', label: 'SABnzbd', protocol: 'usenet' },
  { value: 'nzbget', label: 'NZBGet', protocol: 'usenet' },
]

const DEFAULT_PORTS: Record<string, number> = {
  deluge: 8112,
  qbittorrent: 8080,
  transmission: 9091,
  sabnzbd: 8080,
  nzbget: 6789,
}

interface ClientFormState {
  name: string
  clientType: string
  protocol: string
  host: string
  port: number
  useSsl: boolean
  username: string
  password: string
  category: string
  isDefault: boolean
  priority: number
}

function emptyForm(): ClientFormState {
  return {
    name: '',
    clientType: 'qbittorrent',
    protocol: 'torrent',
    host: 'localhost',
    port: 8080,
    useSsl: false,
    username: '',
    password: '',
    category: 'pressarr',
    isDefault: false,
    priority: 1,
  }
}

function clientToForm(c: DownloadClient): ClientFormState {
  return {
    name: c.name,
    clientType: c.clientType,
    protocol: c.protocol,
    host: c.host,
    port: c.port,
    useSsl: c.useSsl,
    username: c.username ?? '',
    password: c.password ?? '',
    category: c.category,
    isDefault: c.isDefault,
    priority: c.priority,
  }
}

function usesApiKey(clientType: string): boolean {
  return clientType === 'sabnzbd'
}

export default function DownloadClients() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()

  const [dialogOpen, setDialogOpen] = useState(false)
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [deletingClient, setDeletingClient] = useState<DownloadClient | null>(null)
  const [form, setForm] = useState<ClientFormState>(emptyForm())
  const [testing, setTesting] = useState(false)

  const { data: clients = [], isLoading } = useQuery({
    queryKey: ['downloadClients'],
    queryFn: getClients,
  })

  const invalidate = useCallback(
    () => queryClient.invalidateQueries({ queryKey: ['downloadClients'] }),
    [queryClient],
  )

  const createMutation = useMutation({
    mutationFn: (data: Partial<DownloadClient>) => createClient(data),
    onSuccess: () => {
      invalidate()
      setDialogOpen(false)
      toast.success(t('downloadClients.created'))
    },
    onError: () => toast.error(t('downloadClients.createError')),
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<DownloadClient> }) =>
      updateClient(id, data),
    onSuccess: () => {
      invalidate()
      setDialogOpen(false)
      toast.success(t('downloadClients.updated'))
    },
    onError: () => toast.error(t('downloadClients.updateError')),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteClient(id),
    onSuccess: () => {
      invalidate()
      setDeleteDialogOpen(false)
      setDeletingClient(null)
      toast.success(t('downloadClients.deleted'))
    },
    onError: () => toast.error(t('downloadClients.deleteError')),
  })

  function openCreate() {
    setEditingId(null)
    setForm(emptyForm())
    setDialogOpen(true)
  }

  function openEdit(client: DownloadClient) {
    setEditingId(client.id)
    setForm(clientToForm(client))
    setDialogOpen(true)
  }

  function openDelete(client: DownloadClient) {
    setDeletingClient(client)
    setDeleteDialogOpen(true)
  }

  function handleTypeChange(clientType: string) {
    const typeInfo = CLIENT_TYPES.find((ct) => ct.value === clientType)
    setForm({
      ...form,
      clientType,
      protocol: typeInfo?.protocol ?? 'torrent',
      port: DEFAULT_PORTS[clientType] ?? form.port,
    })
  }

  function handleSave() {
    const payload: Partial<DownloadClient> = {
      name: form.name,
      clientType: form.clientType,
      protocol: form.protocol,
      host: form.host,
      port: form.port,
      useSsl: form.useSsl,
      username: form.username || undefined,
      category: form.category,
      isDefault: form.isDefault,
      priority: form.priority,
    }
    // Only send password if user typed something (avoid overwriting with empty string on edit)
    if (form.password) {
      payload.password = form.password
    }
    if (editingId !== null) {
      updateMutation.mutate({ id: editingId, data: payload })
    } else {
      createMutation.mutate(payload)
    }
  }

  async function handleTest() {
    if (!form.host) {
      toast.error(t('downloadClients.testMissingFields'))
      return
    }
    setTesting(true)
    try {
      const testPayload: Partial<DownloadClient> = {
        clientType: form.clientType,
        host: form.host,
        port: form.port,
        useSsl: form.useSsl,
        username: form.username || undefined,
        password: form.password || undefined,
      }
      // For SABnzbd, send apiKey from username field
      if (usesApiKey(form.clientType)) {
        testPayload.apiKey = form.username || undefined
      }
      const result = await testClient(testPayload)
      if (result.isValid) {
        toast.success(t('downloadClients.testSuccess'))
      } else {
        toast.error(result.message || t('downloadClients.testFailed'))
      }
    } catch {
      toast.error(t('downloadClients.testFailed'))
    } finally {
      setTesting(false)
    }
  }

  function getTypeLabel(clientType: string): string {
    return CLIENT_TYPES.find((ct) => ct.value === clientType)?.label ?? clientType
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
          {t('downloadClients.title')}
        </h1>
        <Button onClick={openCreate}>
          <Plus className="size-4" />
          {t('common.add')}
        </Button>
      </div>

      <div className="grid gap-4">
        {clients.map((client) => (
          <Card key={client.id} className="bg-zinc-950 border-zinc-800">
            <CardHeader className="flex-row items-center justify-between">
              <div className="flex items-center gap-3">
                <Download className="size-5 text-zinc-400" />
                <CardTitle className="text-zinc-100">{client.name}</CardTitle>
                <Badge variant="secondary">{getTypeLabel(client.clientType)}</Badge>
                {client.isDefault && (
                  <Badge variant="default">{t('downloadClients.default')}</Badge>
                )}
              </div>
              <div className="flex gap-2">
                <Button variant="ghost" size="icon-sm" onClick={() => openEdit(client)}>
                  <Pencil className="size-4" />
                </Button>
                <Button variant="ghost" size="icon-sm" onClick={() => openDelete(client)}>
                  <Trash2 className="size-4 text-destructive" />
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              <div className="text-sm text-zinc-400 space-y-1">
                <p>
                  {t('downloadClients.host')}:{' '}
                  <span className="text-zinc-200">
                    {client.useSsl ? 'https' : 'http'}://{client.host}:{client.port}
                  </span>
                </p>
                <p>
                  {t('downloadClients.protocol')}:{' '}
                  <span className="text-zinc-200 capitalize">{client.protocol}</span>
                </p>
                {client.category && (
                  <p>
                    {t('downloadClients.category')}:{' '}
                    <span className="text-zinc-200">{client.category}</span>
                  </p>
                )}
              </div>
            </CardContent>
          </Card>
        ))}

        {clients.length === 0 && (
          <p className="text-zinc-500 text-center py-8">
            {t('downloadClients.noClients')}
          </p>
        )}
      </div>

      {/* Create / Edit Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="sm:max-w-lg bg-zinc-950 border-zinc-800">
          <DialogHeader>
            <DialogTitle className="text-zinc-100">
              {editingId !== null
                ? t('downloadClients.editTitle')
                : t('downloadClients.createTitle')}
            </DialogTitle>
          </DialogHeader>

          <div className="grid gap-4 py-2 max-h-[60vh] overflow-y-auto pr-1">
            <div className="grid gap-1.5">
              <label className="text-sm font-medium text-zinc-300">
                {t('downloadClients.name')}
              </label>
              <Input
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder={t('downloadClients.namePlaceholder')}
                className="bg-zinc-900 border-zinc-700 text-zinc-100"
              />
            </div>

            <div className="grid gap-1.5">
              <label className="text-sm font-medium text-zinc-300">
                {t('downloadClients.type')}
              </label>
              <Select value={form.clientType} onValueChange={handleTypeChange}>
                <SelectTrigger className="bg-zinc-900 border-zinc-700 text-zinc-100 w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {CLIENT_TYPES.map((ct) => (
                    <SelectItem key={ct.value} value={ct.value}>
                      {ct.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="grid gap-1.5">
                <label className="text-sm font-medium text-zinc-300">
                  {t('downloadClients.host')}
                </label>
                <Input
                  value={form.host}
                  onChange={(e) => setForm({ ...form, host: e.target.value })}
                  placeholder="localhost"
                  className="bg-zinc-900 border-zinc-700 text-zinc-100"
                />
              </div>
              <div className="grid gap-1.5">
                <label className="text-sm font-medium text-zinc-300">
                  {t('downloadClients.port')}
                </label>
                <Input
                  type="number"
                  value={form.port}
                  onChange={(e) => setForm({ ...form, port: parseInt(e.target.value) || 0 })}
                  className="bg-zinc-900 border-zinc-700 text-zinc-100"
                />
              </div>
            </div>

            <div className="flex items-center justify-between">
              <label className="text-sm font-medium text-zinc-300">
                {t('downloadClients.useSsl')}
              </label>
              <Switch
                checked={form.useSsl}
                onCheckedChange={(checked) => setForm({ ...form, useSsl: checked === true })}
              />
            </div>

            <div className="grid gap-1.5">
              <label className="text-sm font-medium text-zinc-300">
                {usesApiKey(form.clientType)
                  ? t('downloadClients.apiKeyLabel')
                  : t('downloadClients.username')}
              </label>
              <Input
                value={form.username}
                onChange={(e) => setForm({ ...form, username: e.target.value })}
                placeholder={
                  usesApiKey(form.clientType)
                    ? t('downloadClients.apiKeyPlaceholder')
                    : t('downloadClients.usernamePlaceholder')
                }
                className="bg-zinc-900 border-zinc-700 text-zinc-100"
              />
            </div>

            {!usesApiKey(form.clientType) && (
              <div className="grid gap-1.5">
                <label className="text-sm font-medium text-zinc-300">
                  {t('downloadClients.password')}
                </label>
                <Input
                  type="password"
                  value={form.password}
                  onChange={(e) => setForm({ ...form, password: e.target.value })}
                  placeholder={editingId !== null ? '••••••••' : ''}
                  className="bg-zinc-900 border-zinc-700 text-zinc-100"
                />
              </div>
            )}

            <div className="grid gap-1.5">
              <label className="text-sm font-medium text-zinc-300">
                {t('downloadClients.category')}
              </label>
              <Input
                value={form.category}
                onChange={(e) => setForm({ ...form, category: e.target.value })}
                placeholder="pressarr"
                className="bg-zinc-900 border-zinc-700 text-zinc-100"
              />
            </div>

            <div className="grid gap-1.5">
              <label className="text-sm font-medium text-zinc-300">
                {t('downloadClients.priority')}
              </label>
              <Input
                type="number"
                value={form.priority}
                onChange={(e) => setForm({ ...form, priority: parseInt(e.target.value) || 1 })}
                min={1}
                className="bg-zinc-900 border-zinc-700 text-zinc-100"
              />
            </div>

            <div className="flex items-center justify-between">
              <label className="text-sm font-medium text-zinc-300">
                {t('downloadClients.default')}
              </label>
              <Switch
                checked={form.isDefault}
                onCheckedChange={(checked) => setForm({ ...form, isDefault: checked === true })}
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={handleTest} disabled={testing}>
              {testing ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <FlaskConical className="size-4" />
              )}
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
                !form.host.trim() ||
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
              {t('downloadClients.deleteTitle')}
            </DialogTitle>
          </DialogHeader>
          <p className="text-sm text-zinc-400">
            {t('downloadClients.deleteConfirm', { name: deletingClient?.name })}
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteDialogOpen(false)}>
              {t('common.cancel')}
            </Button>
            <Button
              variant="destructive"
              disabled={deleteMutation.isPending}
              onClick={() => deletingClient && deleteMutation.mutate(deletingClient.id)}
            >
              {t('common.delete')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
