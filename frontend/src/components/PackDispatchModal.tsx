import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Loader2, CheckCircle2, XCircle, AlertTriangle } from 'lucide-react'
import { toast } from 'sonner'

import {
  executePackDispatch,
  type PackDispatchFile,
  type PackDispatchPreview,
} from '@/api/packs'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'

interface PackDispatchModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  preview: PackDispatchPreview
  onComplete?: () => void
}

export function PackDispatchModal({ open, onOpenChange, preview, onComplete }: PackDispatchModalProps) {
  const { t } = useTranslation()
  const [skipped, setSkipped] = useState<Set<string>>(new Set())
  const [importing, setImporting] = useState(false)

  function toggleSkip(filename: string) {
    setSkipped((prev) => {
      const next = new Set(prev)
      if (next.has(filename)) {
        next.delete(filename)
      } else {
        next.add(filename)
      }
      return next
    })
  }

  async function handleImport() {
    setImporting(true)
    try {
      const assignments = preview.files.map((f: PackDispatchFile) => ({
        filename: f.filename,
        magazineId: f.matchedMagazineId,
        skip: skipped.has(f.filename) || f.excluded || !f.matchedMagazineId,
      }))

      await executePackDispatch(preview.packId, preview.downloadId, assignments)
      toast.success(t('packs.importSuccess'))
      onOpenChange(false)
      onComplete?.()
    } catch {
      toast.error(t('packs.importError'))
    } finally {
      setImporting(false)
    }
  }

  function fileStatus(f: PackDispatchFile): { label: string; variant: 'default' | 'secondary' | 'destructive' | 'outline' } {
    if (f.excluded) return { label: t('packs.statusExcluded'), variant: 'destructive' }
    if (f.matchedMagazineId) return { label: t('packs.statusMatched'), variant: 'default' }
    return { label: t('packs.statusUnmatched'), variant: 'outline' }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-4xl bg-zinc-950 border-zinc-800 max-h-[80vh] flex flex-col overflow-hidden">
        <DialogHeader>
          <DialogTitle className="text-zinc-100">{t('packs.dispatchTitle')}</DialogTitle>
          <DialogDescription className="text-zinc-400">
            {preview.torrentName} &mdash; {t('packs.dispatchDesc')}
          </DialogDescription>
        </DialogHeader>

        {/* Summary */}
        <div className="flex gap-4 text-sm">
          <span className="text-zinc-400">{t('packs.totalFiles')}: <span className="text-zinc-100 font-medium">{preview.totalFiles}</span></span>
          <span className="text-green-400">{t('packs.matchedFiles')}: {preview.matchedFiles}</span>
          <span className="text-red-400">{t('packs.excludedFiles')}: {preview.excludedFiles}</span>
          <span className="text-yellow-400">{t('packs.unmatchedFiles')}: {preview.unmatchedFiles}</span>
        </div>

        {/* File table */}
        <div className="flex-1 overflow-y-auto">
          <Table>
            <TableHeader>
              <TableRow className="border-zinc-800 hover:bg-transparent">
                <TableHead className="text-zinc-400">{t('packs.filename')}</TableHead>
                <TableHead className="text-zinc-400">{t('packs.parsedTitle')}</TableHead>
                <TableHead className="text-zinc-400">{t('packs.matchedMagazine')}</TableHead>
                <TableHead className="text-zinc-400 w-16">{t('packs.matchScore')}</TableHead>
                <TableHead className="text-zinc-400 w-24">{t('packs.status')}</TableHead>
                <TableHead className="text-zinc-400 w-16">{t('packs.skip')}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {preview.files.map((f: PackDispatchFile) => {
                const status = fileStatus(f)
                const isSkipped = skipped.has(f.filename)

                return (
                  <TableRow key={f.filename} className={`border-zinc-800 ${isSkipped ? 'opacity-50' : ''}`}>
                    <TableCell className="text-zinc-100 text-sm">
                      <span className="line-clamp-1">{f.filename}</span>
                    </TableCell>
                    <TableCell className="text-zinc-400 text-sm">
                      {f.parsedTitle || '-'}
                    </TableCell>
                    <TableCell className="text-zinc-300 text-sm">
                      {f.matchedMagazineTitle || '-'}
                    </TableCell>
                    <TableCell className="text-sm">
                      {f.matchScore > 0 ? (
                        <span className={f.matchScore >= 80 ? 'text-green-400' : f.matchScore >= 60 ? 'text-yellow-400' : 'text-red-400'}>
                          {Math.round(f.matchScore)}%
                        </span>
                      ) : '-'}
                    </TableCell>
                    <TableCell>
                      <Badge variant={status.variant} className={status.variant === 'default' ? 'bg-green-700' : ''}>
                        {f.excluded ? (
                          <XCircle className="size-3 mr-1" />
                        ) : f.matchedMagazineId ? (
                          <CheckCircle2 className="size-3 mr-1" />
                        ) : (
                          <AlertTriangle className="size-3 mr-1" />
                        )}
                        {status.label}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <input
                        type="checkbox"
                        checked={isSkipped}
                        onChange={() => toggleSkip(f.filename)}
                        className="rounded border-zinc-600"
                      />
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={importing}>
            {t('common.cancel')}
          </Button>
          <Button onClick={handleImport} disabled={importing}>
            {importing && <Loader2 className="size-4 animate-spin" />}
            {importing ? t('packs.importing') : t('packs.importAll')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
