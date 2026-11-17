import * as React from "react"
import { ExternalLink } from "lucide-react"

import { InfoBar } from "@/components/common"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { useAirwin } from "@/hooks/use-airwin"
import { api } from "@/lib/api"

export function useUpdateActions() {
  const { call } = useAirwin()
  return {
    check: () => call(() => api.post("update/check")),
    download: () => call(() => api.post("update/download")),
    install: () => call(() => api.post("update/install")),
  }
}

export function ReleaseNotesDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const { state } = useAirwin()
  const u = state?.update
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Novedades de AirWin {u?.latest}</DialogTitle>
          <DialogDescription>Tienes instalada la versión {u?.current}.</DialogDescription>
        </DialogHeader>
        <pre className="selectable max-h-72 overflow-auto rounded-[4px] border bg-console p-3 font-sans text-[13px] leading-5 whitespace-pre-wrap">
          {u?.notes?.trim() || "Mejoras y correcciones."}
        </pre>
        <DialogFooter>
          <Button asChild>
            <a href={u?.url} target="_blank" rel="noreferrer">
              Ver en GitHub <ExternalLink className="size-3.5" />
            </a>
          </Button>
          <Button variant="default" onClick={() => onOpenChange(false)}>
            Cerrar
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

/** Aviso global en la parte superior cuando hay una versión nueva. */
export function UpdateBanner() {
  const { state } = useAirwin()
  const { download, install } = useUpdateActions()
  const [notes, setNotes] = React.useState(false)
  const [dismissed, setDismissed] = React.useState<string | null>(null)
  const u = state?.update
  if (!u || !["available", "downloading", "ready", "installing"].includes(u.status) || dismissed === `${u.latest}${u.status}`)
    return null

  const notesBtn = (
    <Button size="sm" variant="ghost" onClick={() => setNotes(true)}>
      Novedades
    </Button>
  )

  return (
    <div className="mb-6">
      {u.status === "ready" && (
        <InfoBar
          tone="success"
          title="Actualización lista"
          action={
            <div className="flex gap-2">
              {notesBtn}
              <Button size="sm" variant="default" onClick={() => install()}>
                Reiniciar y actualizar
              </Button>
            </div>
          }
        >
          AirWin {u.latest} se instalará en unos segundos y volverá a abrirse.
        </InfoBar>
      )}
      {u.status === "installing" && <InfoBar tone="info" title="Instalando…">AirWin se cerrará y volverá a abrirse.</InfoBar>}
      {u.status === "downloading" && (
        <InfoBar tone="info" title={`Descargando AirWin ${u.latest}`}>
          <span className="inline-flex w-64 items-center gap-3 align-middle">
            <span className="h-1 flex-1 overflow-hidden rounded-full bg-foreground/15">
              <span className="block h-full bg-primary transition-[width]" style={{ width: `${u.progress * 100}%` }} />
            </span>
            <span className="tabular-nums">{Math.round(u.progress * 100)} %</span>
          </span>
        </InfoBar>
      )}
      {u.status === "available" && (
        <InfoBar
          tone="info"
          title={`AirWin ${u.latest} disponible`}
          action={
            <div className="flex gap-2">
              {notesBtn}
              {u.can_install ? (
                <Button size="sm" variant="default" onClick={() => download()}>
                  Descargar
                </Button>
              ) : (
                <Button size="sm" variant="default" asChild>
                  <a href={u.url} target="_blank" rel="noreferrer">
                    Descargar
                  </a>
                </Button>
              )}
              <Button size="sm" variant="ghost" onClick={() => setDismissed(`${u.latest}${u.status}`)}>
                Más tarde
              </Button>
            </div>
          }
        >
          {u.error ? `No se pudo descargar: ${u.error}` : `Tienes la ${u.current}.`}
        </InfoBar>
      )}
      <ReleaseNotesDialog open={notes} onOpenChange={setNotes} />
    </div>
  )
}
