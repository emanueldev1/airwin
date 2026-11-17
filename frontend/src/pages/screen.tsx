import * as React from "react"
import { Cpu, Gauge, Loader2, MonitorPlay, Timer, Volume2 } from "lucide-react"

import { DevicePicker, InfoBar, PageTitle, Row, Section, useDeviceChoice } from "@/components/common"
import { Button } from "@/components/ui/button"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import { useAirwin } from "@/hooks/use-airwin"
import { api } from "@/lib/api"
import type { Monitor } from "@/lib/types"
import { cn } from "@/lib/utils"

export function ScreenPage() {
  const { state, call } = useAirwin()
  const targets = (state?.devices ?? []).filter((d) => d.canVideo)
  const [target, setTarget] = useDeviceChoice(targets, "screen-target")
  const [monitors, setMonitors] = React.useState<Monitor[]>([])
  const [monitor, setMonitor] = React.useState(0)
  const [audio, setAudio] = React.useState(true)
  const [busy, setBusy] = React.useState(false)
  const s = state?.settings
  const casting = !!target && !!state?.video.screen.includes(target)

  React.useEffect(() => {
    api.get<Monitor[]>("monitors").then(setMonitors).catch(() => undefined)
  }, [])

  const setSetting = (key: string, value: unknown) => call(() => api.post("settings", { [key]: value }))

  const start = async () => {
    if (!target || !monitors[monitor]) return
    setBusy(true)
    await call(() => api.post("screen/start", { id: target, rect: monitors[monitor].rect, audio }))
    setBusy(false)
  }

  // Disposición de monitores a escala, como en Configuración > Pantalla.
  const b = monitors.reduce(
    (a, m) => ({
      x0: Math.min(a.x0, m.rect[0]),
      y0: Math.min(a.y0, m.rect[1]),
      x1: Math.max(a.x1, m.rect[0] + m.rect[2]),
      y1: Math.max(a.y1, m.rect[1] + m.rect[3]),
    }),
    { x0: Infinity, y0: Infinity, x1: -Infinity, y1: -Infinity }
  )
  const scale = monitors.length ? Math.min(360 / (b.x1 - b.x0), 130 / (b.y1 - b.y0)) : 1

  return (
    <>
      <PageTitle
        title="Pantalla"
        actions={
          casting ? (
            <Button onClick={() => call(() => api.post("video/stop", { id: target }))}>Dejar de proyectar</Button>
          ) : (
            <Button variant="default" disabled={!target || busy || !monitors.length || !state?.deps.ffmpeg} onClick={start}>
              {busy && <Loader2 className="animate-spin" />}
              {busy ? "Iniciando…" : "Proyectar"}
            </Button>
          )
        }
      />

      <div className="mb-6 flex h-48 items-center justify-center rounded-lg border bg-card dark:border-black/20">
        <div className="relative" style={{ width: (b.x1 - b.x0) * scale || 0, height: (b.y1 - b.y0) * scale || 0 }}>
          {monitors.map((m, i) => (
            <button
              key={i}
              onClick={() => setMonitor(i)}
              className={cn(
                "absolute grid place-items-center rounded-[4px] border text-[22px] font-semibold transition-colors",
                i === monitor
                  ? "border-2 border-primary bg-primary/15 text-foreground"
                  : "border-border-strong bg-muted text-muted-foreground hover:bg-foreground/[0.08]"
              )}
              style={{
                left: (m.rect[0] - b.x0) * scale + 2,
                top: (m.rect[1] - b.y0) * scale + 2,
                width: m.rect[2] * scale - 4,
                height: m.rect[3] * scale - 4,
              }}
            >
              {i + 1}
            </button>
          ))}
        </div>
      </div>

      {casting && (
        <div className="mb-6">
          <InfoBar tone="success" title="Proyectando">
            Pantalla {monitor + 1} en {targets.find((d) => d.id === target)?.name}
          </InfoBar>
        </div>
      )}
      {!state?.deps.ffmpeg && (
        <div className="mb-6">
          <InfoBar tone="warning" title="Falta FFmpeg">
            Instálalo desde Configuración para poder proyectar.
          </InfoBar>
        </div>
      )}

      <Section>
        <Row icon={MonitorPlay} title="Proyectar en">
          <DevicePicker devices={targets} value={target} onChange={setTarget} />
        </Row>
        <Row icon={Gauge} title="Calidad" description="Una calidad mayor necesita una red más rápida.">
          <Select value={s?.cast_bitrate} onValueChange={(v) => setSetting("cast_bitrate", v)}>
            <SelectTrigger className="w-44">
              <SelectValue />
            </SelectTrigger>
            <SelectContent align="end">
              <SelectItem value="3M">Baja (3 Mbps)</SelectItem>
              <SelectItem value="6M">Media (6 Mbps)</SelectItem>
              <SelectItem value="10M">Alta (10 Mbps)</SelectItem>
              <SelectItem value="16M">Máxima (16 Mbps)</SelectItem>
            </SelectContent>
          </Select>
        </Row>
        <Row icon={Timer} title="Fotogramas por segundo">
          <Select value={String(s?.cast_fps ?? 30)} onValueChange={(v) => setSetting("cast_fps", Number(v))}>
            <SelectTrigger className="w-44">
              <SelectValue />
            </SelectTrigger>
            <SelectContent align="end">
              {[24, 30, 60].map((f) => (
                <SelectItem key={f} value={String(f)}>
                  {f} fps
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Row>
        <Row icon={Cpu} title="Codificador" description="Usar la tarjeta gráfica reduce el consumo de CPU.">
          <Select value={s?.cast_encoder} onValueChange={(v) => setSetting("cast_encoder", v)}>
            <SelectTrigger className="w-44">
              <SelectValue />
            </SelectTrigger>
            <SelectContent align="end">
              {Object.entries(state?.encoders ?? {}).map(([k, label]) => (
                <SelectItem key={k} value={k}>
                  {label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Row>
        <Row icon={Volume2} title="Incluir el sonido del PC">
          <span className="text-[13px] text-muted-foreground">{audio ? "Activado" : "Desactivado"}</span>
          <Switch checked={audio} onCheckedChange={setAudio} />
        </Row>
      </Section>

      <p className="text-[12px] leading-5 text-muted-foreground">
        La imagen llega al Apple TV con 3 a 8 segundos de retraso: sirve para presentaciones, fotos o videos, no para
        juegos. Apple reserva la duplicación en tiempo real a sus propios dispositivos.
      </p>
    </>
  )
}
