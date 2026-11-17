import * as React from "react"
import { Film, Link as LinkIcon, Loader2, MonitorPlay, RefreshCcw, Square } from "lucide-react"

import { DevicePicker, InfoBar, PageTitle, Row, Section } from "@/components/common"
import { useDeviceChoice } from "@/components/common"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Switch } from "@/components/ui/switch"
import { useAirwin } from "@/hooks/use-airwin"
import { api } from "@/lib/api"

export function VideoPage() {
  const { state, call } = useAirwin()
  const targets = (state?.devices ?? []).filter((d) => d.canVideo)
  const [target, setTarget] = useDeviceChoice(targets, "video-target")
  const [convert, setConvert] = React.useState(false)
  const [url, setUrl] = React.useState("")
  const [path, setPath] = React.useState("")
  const [busy, setBusy] = React.useState<"file" | "url" | null>(null)
  const device = targets.find((d) => d.id === target)
  const playing = !!target && !!state?.video.active.includes(target) && !state.video.screen.includes(target)

  const playFile = async () => {
    if (!target) return
    let file = path
    if (state?.canPickFiles) {
      const r = await call(() => api.post<{ path: string | null }>("pick", { kind: "video" }))
      if (!r?.path) return
      file = r.path
      setPath(file)
    }
    if (!file) return
    setBusy("file")
    await call(() => api.post("video/file", { id: target, path: file, convert }))
    setBusy(null)
  }

  const playUrl = async () => {
    if (!target || !url) return
    setBusy("url")
    await call(() => api.post("video/url", { id: target, url }))
    setBusy(null)
  }

  return (
    <>
      <PageTitle title="Video" />

      {playing && (
        <div className="mb-6">
          <InfoBar
            tone="success"
            title="Reproduciendo"
            action={
              <Button size="sm" onClick={() => call(() => api.post("video/stop", { id: target }))}>
                <Square className="size-3 fill-current" /> Detener
              </Button>
            }
          >
            en {device?.name}
            {path ? ` · ${path.split(/[\\/]/).pop()}` : ""}
          </InfoBar>
        </div>
      )}

      <Section>
        <Row icon={MonitorPlay} title="Reproducir en" description="Apple TV, Mac o televisor compatible con AirPlay.">
          <DevicePicker devices={targets} value={target} onChange={setTarget} />
        </Row>
      </Section>

      <Section title="Contenido">
        <Row
          icon={Film}
          title="Archivo de este PC"
          description={path ? <span className="selectable">{path}</span> : "MP4, MOV y M4V se envían tal cual. MKV, AVI y WEBM se convierten al vuelo."}
        >
          {!state?.canPickFiles && (
            <Input className="w-64" placeholder="C:\Videos\pelicula.mp4" value={path} onChange={(e) => setPath(e.target.value)} />
          )}
          <Button variant="default" disabled={!target || !!busy || (!state?.canPickFiles && !path)} onClick={playFile}>
            {busy === "file" && <Loader2 className="animate-spin" />}
            {busy === "file" ? "Preparando…" : state?.canPickFiles ? "Elegir archivo…" : "Reproducir"}
          </Button>
        </Row>
        <Row
          icon={RefreshCcw}
          title="Convertir siempre"
          description="Útil para subtítulos incrustados o códecs que el Apple TV no admite. Requiere FFmpeg."
        >
          <span className="text-[13px] text-muted-foreground">{convert ? "Activado" : "Desactivado"}</span>
          <Switch checked={convert} onCheckedChange={setConvert} />
        </Row>
        <Row icon={LinkIcon} title="Dirección URL" description="Enlace directo a un .mp4, .mov o lista HLS (.m3u8).">
          <Input
            className="w-72"
            placeholder="https://"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && playUrl()}
          />
          <Button disabled={!target || !url || !!busy} onClick={playUrl}>
            {busy === "url" && <Loader2 className="animate-spin" />} Reproducir
          </Button>
        </Row>
      </Section>
    </>
  )
}
