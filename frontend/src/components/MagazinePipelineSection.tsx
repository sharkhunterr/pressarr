import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Save, FlaskConical, Loader2, ShieldAlert } from 'lucide-react'
import { toast } from 'sonner'

import {
  getSceneIndexers,
  saveSceneIndexers,
  testBookys,
  testTelechargerMagazines,
  testFlaresolverr,
} from '@/api/system'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Switch } from '@/components/ui/switch'

// Reusable "magazine pipeline" config block — Bookys + tm.org
// + FlareSolverr (bypass) + JDownloader 2 (folder-watch). The
// four resources are grouped because operators configure them
// as a unit: Bookys needs FlareSolverr to reach the site, JD2
// needs a folderwatch path the importer can poll.
//
// Mounted at the top of the Indexers settings page so it lives
// alongside the Prowlarr indexer list (per operator review —
// "the Indexers page is good, just put scene indexers there").

const PWD_PLACEHOLDER = '***'

export default function MagazinePipelineSection() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()

  // Local form state, hydrated once from the API and then
  // owned by the inputs.
  const [bookysEnabled, setBookysEnabled] = useState(false)
  const [bookysUrl, setBookysUrl] = useState('')
  const [bookysUsername, setBookysUsername] = useState('')
  const [bookysPassword, setBookysPassword] = useState('')
  const [tmEnabled, setTmEnabled] = useState(false)
  const [tmUrl, setTmUrl] = useState('')
  const [flareUrl, setFlareUrl] = useState('')
  const [flareTimeoutMs, setFlareTimeoutMs] = useState(60000)
  const [jdEnabled, setJdEnabled] = useState(false)
  const [jdFolderwatch, setJdFolderwatch] = useState('')
  const [jdOutputPath, setJdOutputPath] = useState('')
  const [initialised, setInitialised] = useState(false)
  // Per-tester loading flags so spinners don't block each
  // other when the operator hits multiple at once.
  const [testingBookys, setTestingBookys] = useState(false)
  const [testingTm, setTestingTm] = useState(false)
  const [testingFlare, setTestingFlare] = useState(false)

  const { isLoading } = useQuery({
    queryKey: ['sceneIndexersSettings'],
    queryFn: getSceneIndexers,
    select: (data) => {
      if (!initialised) {
        setBookysEnabled(data.bookysEnabled)
        setBookysUrl(data.bookysUrl)
        setBookysUsername(data.bookysUsername)
        // Always start with the masked placeholder so an
        // accidental save keeps the stored value intact.
        setBookysPassword(data.bookysPassword ?? '')
        setTmEnabled(data.telechargerMagazinesEnabled)
        setTmUrl(data.telechargerMagazinesUrl)
        setFlareUrl(data.flaresolverrUrl)
        setFlareTimeoutMs(data.flaresolverrTimeoutMs)
        setJdEnabled(data.jdownloaderEnabled)
        setJdFolderwatch(data.jdownloaderFolderwatch)
        setJdOutputPath(data.jdownloaderOutputPath)
        setInitialised(true)
      }
      return data
    },
  })

  const saveMutation = useMutation({
    mutationFn: () =>
      saveSceneIndexers({
        bookysEnabled,
        bookysUrl,
        bookysUsername,
        bookysPassword,
        telechargerMagazinesEnabled: tmEnabled,
        telechargerMagazinesUrl: tmUrl,
        flaresolverrUrl: flareUrl,
        flaresolverrTimeoutMs: flareTimeoutMs,
        jdownloaderEnabled: jdEnabled,
        jdownloaderFolderwatch: jdFolderwatch,
        jdownloaderOutputPath: jdOutputPath,
      }),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['sceneIndexersSettings'] })
      // Reset the password field to the new mask the server
      // sends back — prevents a second save from accidentally
      // wiping the just-saved value.
      setBookysPassword(data.bookysPassword)
      toast.success(t('sceneIndexers.saved') || 'Saved')
    },
    onError: () => toast.error(t('sceneIndexers.saveError') || 'Save failed'),
  })

  async function runTest(
    fn: () => Promise<{ isValid: boolean; message: string }>,
    setLoading: (v: boolean) => void,
    label: string,
  ) {
    setLoading(true)
    try {
      const r = await fn()
      if (r.isValid) {
        toast.success(`${label}: ${r.message}`)
      } else {
        toast.error(`${label}: ${r.message}`)
      }
    } catch (e) {
      toast.error(`${label}: ${(e as Error)?.message ?? 'failed'}`)
    } finally {
      setLoading(false)
    }
  }

  if (isLoading) {
    return (
      <div className="p-8 text-center text-zinc-400">
        <Loader2 className="mx-auto size-6 animate-spin" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-zinc-100">
          {t('sceneIndexers.heading') || 'Magazine pipeline (scene)'}
        </h2>
        <p className="mt-1 text-sm text-zinc-400">
          {t('sceneIndexers.description') ||
            'French magazine scene scrapers (Bookys, telecharger-magazines.org) + the bypass + download client they depend on. Releases feed the auto-grab scheduler.'}
        </p>
      </div>

      {/* ──────────────── Bookys ──────────────── */}
      <Card className="bg-zinc-900 border-zinc-800">
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-zinc-100">Bookys</CardTitle>
          <div className="flex items-center gap-3">
            <Switch
              checked={bookysEnabled}
              onCheckedChange={setBookysEnabled}
            />
            <Button
              variant="outline"
              size="sm"
              onClick={() =>
                runTest(testBookys, setTestingBookys, 'Bookys')
              }
              disabled={testingBookys || !bookysEnabled}
            >
              {testingBookys ? (
                <Loader2 className="size-3 animate-spin" />
              ) : (
                <FlaskConical className="size-3" />
              )}
              Test
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-xs text-zinc-400 flex items-start gap-1">
            <ShieldAlert className="size-3.5 mt-0.5 text-amber-400 flex-shrink-0" />
            <span>
              Bookys is behind Cloudflare. Configure FlareSolverr below
              before turning Bookys on — without it, every scrape will
              return zero releases.
            </span>
          </p>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div>
              <label className="text-xs text-zinc-400 mb-1 block">URL</label>
              <Input
                value={bookysUrl}
                onChange={(e) => setBookysUrl(e.target.value)}
                placeholder="https://www6.bookys-ebooks.com"
                className="bg-zinc-950 border-zinc-700 text-zinc-100"
              />
            </div>
            <div>
              <label className="text-xs text-zinc-400 mb-1 block">Username</label>
              <Input
                value={bookysUsername}
                onChange={(e) => setBookysUsername(e.target.value)}
                className="bg-zinc-950 border-zinc-700 text-zinc-100"
              />
            </div>
            <div className="sm:col-span-2">
              <label className="text-xs text-zinc-400 mb-1 block">
                Password{' '}
                <span className="text-zinc-500">
                  ({PWD_PLACEHOLDER} = keep current)
                </span>
              </label>
              <Input
                type="password"
                value={bookysPassword}
                onChange={(e) => setBookysPassword(e.target.value)}
                className="bg-zinc-950 border-zinc-700 text-zinc-100"
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* ──────────────── telecharger-magazines.org ──────────────── */}
      <Card className="bg-zinc-900 border-zinc-800">
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-zinc-100">
            telecharger-magazines.org
          </CardTitle>
          <div className="flex items-center gap-3">
            <Switch checked={tmEnabled} onCheckedChange={setTmEnabled} />
            <Button
              variant="outline"
              size="sm"
              onClick={() =>
                runTest(
                  testTelechargerMagazines,
                  setTestingTm,
                  'tm.org',
                )
              }
              disabled={testingTm || !tmEnabled}
            >
              {testingTm ? (
                <Loader2 className="size-3 animate-spin" />
              ) : (
                <FlaskConical className="size-3" />
              )}
              Test
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-xs text-zinc-400">
            No login required — the scraper only needs the base URL.
          </p>
          <div>
            <label className="text-xs text-zinc-400 mb-1 block">URL</label>
            <Input
              value={tmUrl}
              onChange={(e) => setTmUrl(e.target.value)}
              placeholder="https://www.telecharger-magazines.org"
              className="bg-zinc-950 border-zinc-700 text-zinc-100"
            />
          </div>
        </CardContent>
      </Card>

      {/* ──────────────── FlareSolverr ──────────────── */}
      <Card className="bg-zinc-900 border-zinc-800">
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-zinc-100">FlareSolverr</CardTitle>
          <Button
            variant="outline"
            size="sm"
            onClick={() =>
              runTest(testFlaresolverr, setTestingFlare, 'FlareSolverr')
            }
            disabled={testingFlare || !flareUrl}
          >
            {testingFlare ? (
              <Loader2 className="size-3 animate-spin" />
            ) : (
              <FlaskConical className="size-3" />
            )}
            Test
          </Button>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-xs text-zinc-400">
            Cloudflare-bypass sidecar. Shared with grabarr by default — both
            apps point at the same instance.
          </p>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div>
              <label className="text-xs text-zinc-400 mb-1 block">
                Endpoint URL
              </label>
              <Input
                value={flareUrl}
                onChange={(e) => setFlareUrl(e.target.value)}
                placeholder="http://flaresolverr:8191/v1"
                className="bg-zinc-950 border-zinc-700 text-zinc-100"
              />
            </div>
            <div>
              <label className="text-xs text-zinc-400 mb-1 block">
                Per-request timeout (ms)
              </label>
              <Input
                type="number"
                min={5000}
                max={300000}
                step={5000}
                value={flareTimeoutMs}
                onChange={(e) =>
                  setFlareTimeoutMs(Number(e.target.value) || 60000)
                }
                className="bg-zinc-950 border-zinc-700 text-zinc-100"
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* ──────────────── JDownloader 2 ──────────────── */}
      <Card className="bg-zinc-900 border-zinc-800">
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-zinc-100">JDownloader 2</CardTitle>
          <Switch checked={jdEnabled} onCheckedChange={setJdEnabled} />
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-xs text-zinc-400">
            Pressarr writes a <code>.crawljob</code> per grabbed release into{' '}
            <code>folderwatch</code>; JD2's Folder Watch extension picks it
            up. The importer polls <code>output_path</code> and moves
            completed files into the magazine library.
          </p>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div>
              <label className="text-xs text-zinc-400 mb-1 block">
                Folder watch path
              </label>
              <Input
                value={jdFolderwatch}
                onChange={(e) => setJdFolderwatch(e.target.value)}
                placeholder="/downloads/jd2/folderwatch"
                className="bg-zinc-950 border-zinc-700 text-zinc-100"
              />
            </div>
            <div>
              <label className="text-xs text-zinc-400 mb-1 block">
                Output path (completed downloads)
              </label>
              <Input
                value={jdOutputPath}
                onChange={(e) => setJdOutputPath(e.target.value)}
                placeholder="/downloads/jd2/complete"
                className="bg-zinc-950 border-zinc-700 text-zinc-100"
              />
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="flex justify-end">
        <Button
          onClick={() => saveMutation.mutate()}
          disabled={saveMutation.isPending}
        >
          {saveMutation.isPending ? (
            <Loader2 className="size-4 animate-spin" />
          ) : (
            <Save className="size-4" />
          )}
          Save
        </Button>
      </div>
    </div>
  )
}
