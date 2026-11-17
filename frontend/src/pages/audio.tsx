import * as React from "react"
import { FileAudio, Mic2, Play, Square, Volume2 } from "lucide-react"

import { DeviceIcon, PageTitle, Row, Section } from "@/components/common"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Slider } from "@/components/ui/slider"
import { useAirwin } from "@/hooks/use-airwin"
import { api } from "@/lib/api"

const DEFAULT_SOURCE = "__default__"

function DeviceVolume({ id }: { id: string }) {
  const { call } = useAirwin()
  const [value, setValue] = React.useState<number | null>(null)
  React.useEffect(() => {
    api
      .get<{ level: number }>(`volume?id=${encodeURIComponent(id)}`)
      .then((r) => setValue(Math.round(r.level)))
      .catch(() => setValue(50))
  }, [id])
  if (value === null) return <div className="w-44" />
  return (
    <div className="flex w-44 items-center gap-2.5">
      <Volume2 className="size-4 shrink-0 text-muted-foreground" strokeWidth={1.5} />
      <Slider
        value={[value]}
        max={100}
        onValueChange={([v]) => setValue(v)}
        onValueCommit={([v]) => call(() => api.post("volume", { ids: [id], level: v }))}
      />
      <span className="w-7 text-right text-[12px] text-muted-foreground tabular-nums">{value}</span>
    </div>
  )
}

export function AudioPage() {
  const { state, call, level } = useAirwin()
  const speakers = (state?.devices ?? []).filter((d) => d.canAudio)
  const active = new Set(state?.audio.active ?? [])
  const [selected, setSelected] = React.useState<Set<string>>(new Set())
  const [outputs, setOutputs] = React.useState<string[]>([])
  const [busy, setBusy] = React.useState(false)
  const [manualPath, setManualPath] = React.useState("")

  React.useEffect(() => {
    api.get<string[]>("audio/outputs").then(setOutputs).catch(() => setOutputs([]))
  }, [])

  const toggle = (id: string) =>
    setSelected((s) => {
      const n = new Set(s)
      if (n.has(id)) n.delete(id)
      else n.add(id)
      return n
    })

  const ids = [...selected].filter((id) => speakers.some((d) => d.id === id))

  const start = async (file?: string) => {
    setBusy(true)
    await call(() => api.post("audio/start", { ids, file }))
    setBusy(false)
  }

  const pickFile = async () => {
    if (!state?.canPickFiles) return manualPath && start(manualPath)
    const r = await call(() => api.post<{ path: string | null }>("pick", { kind: "audio" }))
    if (r?.path) await start(r.path)
  }

  return (
    <>
      <PageTitle
        title="Audio"
        actions={
          active.size > 0 && (
            <Button variant="secondary" onClick={() => call(() => api.post("audio/stop"))}>
              <Square className="size-3.5 fill-current" /> Detener todo
            </Button>
          )
        }
      />

      <Section title="Reproducir en">
        {speakers.length === 0 && (
          <Row icon={Volume2} title="No hay altavoces AirPlay" description="Actualiza la lista en Dispositivos." />
        )}
        {speakers.map((d) => {
          const on = active.has(d.id)
          return (
            <Row
              key={d.id}
              as="label"
              iconNode={
                <div className="flex items-center gap-4">
                  <Checkbox checked={selected.has(d.id)} onCheckedChange={() => toggle(d.id)} />
                  <DeviceIcon kind={d.kind} className="size-6 text-foreground/85" />
                </div>
              }
              title={d.name}
              description={on ? <span className="text-primary">Reproduciendo</span> : d.model}
            >
              {on && (
                <>
                  <DeviceVolume id={d.id} />
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label="Detener"
                    onClick={(e) => {
                      e.preventDefault()
                      void call(() => api.post("audio/stop", { id: d.id }))
                    }}
                  >
                    <Square className="size-3.5 fill-current" />
                  </Button>
                </>
              )}
            </Row>
          )
        })}
      </Section>

      <Section title="Fuente">
        <Row
          icon={Mic2}
          title="Sonido del sistema"
          description="Todo lo que suena en Windows: navegador, Spotify, reproductores…"
        >
          <div className="h-1 w-16 overflow-hidden rounded-full bg-foreground/15" title="Nivel">
            <div className="h-full bg-primary transition-[width] duration-100" style={{ width: `${Math.min(100, level * 100)}%` }} />
          </div>
          <Select
            value={state?.audio.source ?? DEFAULT_SOURCE}
            onValueChange={(v) => call(() => api.post("audio/source", { name: v === DEFAULT_SOURCE ? null : v }))}
          >
            <SelectTrigger className="w-56">
              <SelectValue />
            </SelectTrigger>
            <SelectContent align="end">
              <SelectItem value={DEFAULT_SOURCE}>Salida predeterminada</SelectItem>
              {outputs.map((o) => (
                <SelectItem key={o} value={o}>
                  {o}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button variant="default" disabled={!ids.length || busy} onClick={() => start()}>
            <Play className="size-3.5 fill-current" /> Transmitir
          </Button>
        </Row>
        <Row icon={FileAudio} title="Archivo de música" description="MP3, M4A, FLAC, WAV, OGG u Opus.">
          {!state?.canPickFiles && (
            <Input className="w-64" placeholder="Ruta del archivo" value={manualPath} onChange={(e) => setManualPath(e.target.value)} />
          )}
          <Button disabled={!ids.length || busy || (!state?.canPickFiles && !manualPath)} onClick={pickFile}>
            Elegir archivo…
          </Button>
        </Row>
      </Section>

      <p className="text-[12px] text-muted-foreground">
        AirPlay añade unos 2 segundos de búfer. Con varios altavoces a la vez puede haber una pequeña diferencia entre ellos.
      </p>
    </>
  )
}
