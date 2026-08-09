import { useState, useEffect, useCallback } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Toaster } from 'sonner'
import { useTranslation } from 'react-i18next'
import { PageLayout } from './components/layout/PageLayout'
import Library from './pages/Library'
import AddMagazine from './pages/AddMagazine'
import MagazineDetail from './pages/MagazineDetail'
import Calendar from './pages/Calendar'
import Queue from './pages/Queue'
import History from './pages/History'
import Blocklist from './pages/Blocklist'
import Logs from './pages/Logs'
import Packs from './pages/Packs'
import AddPack from './pages/AddPack'
import PackDetail from './pages/PackDetail'
import QualityProfiles from './pages/Settings/QualityProfiles'
import Indexers from './pages/Settings/Indexers'
import DownloadClients from './pages/Settings/DownloadClients'
import RootFolders from './pages/Settings/RootFolders'
import NamingTemplate from './pages/Settings/NamingTemplate'
import Metadata from './pages/Settings/Metadata'
import General from './pages/Settings/General'
import System from './pages/Settings/System'
import Notifications from './pages/Settings/Notifications'
import { PackDispatchWatcher } from './components/PackDispatchWatcher'
import {
  isApiKeyPromptVisible,
  onApiKeyPromptResult,
  setApiKey,
} from './api/client'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from './components/ui/dialog'
import { Button } from './components/ui/button'
import { Input } from './components/ui/input'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
    },
  },
})

function ApiKeyPrompt() {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  const [key, setKey] = useState('')

  const handlePromptEvent = useCallback(() => {
    if (isApiKeyPromptVisible()) {
      setOpen(true)
      setKey('')
    }
  }, [])

  useEffect(() => {
    window.addEventListener('pressarr:api-key-prompt', handlePromptEvent)
    return () => window.removeEventListener('pressarr:api-key-prompt', handlePromptEvent)
  }, [handlePromptEvent])

  function handleSubmit() {
    if (key.trim()) {
      setApiKey(key.trim())
      onApiKeyPromptResult(key.trim())
      setOpen(false)
    }
  }

  function handleCancel() {
    onApiKeyPromptResult(null)
    setOpen(false)
  }

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) handleCancel() }}>
      <DialogContent className="sm:max-w-md bg-zinc-950 border-zinc-800">
        <DialogHeader>
          <DialogTitle className="text-zinc-100">
            {t('auth.apiKeyRequired')}
          </DialogTitle>
        </DialogHeader>
        <p className="text-sm text-zinc-400">{t('auth.apiKeyDescription')}</p>
        <Input
          value={key}
          onChange={(e) => setKey(e.target.value)}
          placeholder={t('auth.apiKeyPlaceholder')}
          className="bg-zinc-900 border-zinc-700 text-zinc-100"
          onKeyDown={(e) => { if (e.key === 'Enter') handleSubmit() }}
        />
        <DialogFooter>
          <Button variant="outline" onClick={handleCancel}>
            {t('common.cancel')}
          </Button>
          <Button onClick={handleSubmit} disabled={!key.trim()}>
            {t('common.confirm')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <PageLayout>
          <Routes>
            <Route path="/" element={<Library />} />
            <Route path="/add" element={<AddMagazine />} />
            <Route path="/magazine/:id" element={<MagazineDetail />} />
            <Route path="/packs" element={<Packs />} />
            <Route path="/packs/add" element={<AddPack />} />
            <Route path="/pack/:id" element={<PackDetail />} />
            <Route path="/calendar" element={<Calendar />} />
            <Route path="/queue" element={<Queue />} />
            <Route path="/history" element={<History />} />
            <Route path="/blocklist" element={<Blocklist />} />
            <Route path="/logs" element={<Logs />} />
            <Route path="/settings/general" element={<General />} />
            <Route path="/settings/download-clients" element={<DownloadClients />} />
            <Route path="/settings/indexers" element={<Indexers />} />
            <Route path="/settings/notifications" element={<Notifications />} />
            <Route path="/settings/quality-profiles" element={<QualityProfiles />} />
            <Route path="/settings/naming" element={<NamingTemplate />} />
            <Route path="/settings/root-folders" element={<RootFolders />} />
            <Route path="/settings/metadata" element={<Metadata />} />
            <Route path="/settings/system" element={<System />} />
          </Routes>
        </PageLayout>
        <ApiKeyPrompt />
        {/* Écoute globalement le WS pack:dispatch_ready et ouvre le
            modal de review dès qu'un pack termine son download (avec
            auto_import=false). Sans ça le event partait dans le vide. */}
        <PackDispatchWatcher />
        <Toaster
          theme="dark"
          position="bottom-right"
          toastOptions={{
            style: {
              background: '#09090b',
              border: '1px solid #27272a',
              color: '#fafafa',
            },
          }}
        />
      </BrowserRouter>
    </QueryClientProvider>
  )
}

export default App
