import * as React from "react"
import {
  AppWindow, ChevronDown, ChevronLeft, ChevronRight, ChevronUp, House, Keyboard, LayoutGrid, Minus, Music, Pause,
  Play, Plus, Power, SkipBack, SkipForward, Undo2,
} from "lucide-react"

import { DevicePicker, Kbd, PageTitle, Row, Section, useDeviceChoice } from "@/components/common"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { useAirwin } from "@/hooks/use-airwin"
import { api } from "@/lib/api"
import type { NowPlaying } from "@/lib/types"
import { cn } from "@/lib/utils"

const KEYMAP: Record<string, string> = {
  ArrowUp: "up",
  ArrowDown: "down",
  ArrowLeft: "left",
  ArrowRight: "right",
  Enter: "select",
  Escape: "menu",
  Backspace: "menu",
  " ": "play_pause",
  h: "home",
  "+": "volume_up",
  "-": "volume_down",
}

function fmt(sec: number | null | undefined) {
  if (sec == null) return "0:00"
  const s = Math.max(0, Math.floor(sec))
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`
}

export function RemotePage() {
  const { state, call } = useAirwin()
  const targets = (state?.devices ?? []).filter((d) => d.canRemote || d.canAudio)
  const [target, setTarget] = useDeviceChoice(targets, "remote-target")
  const [np, setNp] = React.useState<NowPlaying | null>(null)
  const [apps, setApps] = React.useState<{ name: string; id: string }[] | null>(null)
  const [app, setApp] = React.useState<string>("")
  const [text, setText] = React.useState("")
  const [pressed, setPressed] = React.useState<string | null>(null)

  const send = React.useCallback(
    (action: string) => {
      if (!target) return
      setPressed(action)
      window.setTimeout(() => setPressed(null), 140)
      void call(() => api.post("remote", { id: target, action }))
    },
    [target, call]
  )

  React.useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement
      if (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.closest("[role=dialog],[role=listbox],[role=menu]")) return
      const action = KEYMAP[e.key]
      if (action) {
        e.preventDefault()
        send(action)
      }
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [send])

  React.useEffect(() => {
    if (!target) return
    let alive = true
    const poll = () =>
      api
        .get<NowPlaying>(`nowplaying?id=${encodeURIComponent(target)}`)
        .then((r) => alive && setNp(r))
        .catch(() => alive && setNp(null))
    void poll()
    const t = window.setInterval(poll, 2500)
    return () => {
      alive = false
      window.clearInterval(t)
    }
  }, [target])

  const loadApps = async () => {
    if (!target || apps) return
    const r = await call(() => api.get<{ name: string; id: string }[]>(`apps?id=${encodeURIComponent(target)}`))
    if (r) setApps(r)
  }

  const progress = np?.position != null && np?.total ? (np.position / np.total) * 100 : 0

  const Arrow = ({ action, icon: Icon, className }: { action: string; icon: typeof ChevronUp; className: string }) => (
    <button
      aria-label={action}
      onClick={() => send(action)}
      className={cn(
        "absolute grid size-12 place-items-center rounded-full text-foreground/70 transition-colors hover:bg-foreground/[0.06] hover:text-foreground",
        pressed === action && "bg-foreground/[0.08] text-foreground",
        className
      )}
    >
      <Icon className="size-5" strokeWidth={1.75} />
    </button>
  )

  const Key = ({ action, icon: Icon, label }: { action: string; icon: typeof Undo2; label: string }) => (
    <button onClick={() => send(action)} className="group flex flex-col items-center gap-1.5">
      <span
        className={cn(
          "grid size-11 place-items-center rounded-full border border-border-strong bg-secondary transition-colors group-hover:bg-card-hover dark:border-white/[0.07]",
          pressed === action && "bg-muted"
        )}
      >
        <Icon className="size-[18px]" strokeWidth={1.5} />
      </span>
      <span className="text-[11px] text-muted-foreground">{label}</span>
    </button>
  )

  return (
    <>
      <PageTitle title="Mando" actions={<DevicePicker devices={targets} value={target} onChange={setTarget} />} />

      <div className="grid gap-6 lg:grid-cols-[280px_1fr]">
        <div className="flex flex-col items-center gap-6 self-start rounded-lg border bg-card px-6 py-7 dark:border-black/20">
          <div className="relative size-44 rounded-full border border-border-strong bg-background/60 dark:border-white/[0.06] dark:bg-black/15">
            <Arrow action="up" icon={ChevronUp} className="top-1 left-1/2 -translate-x-1/2" />
            <Arrow action="down" icon={ChevronDown} className="bottom-1 left-1/2 -translate-x-1/2" />
            <Arrow action="left" icon={ChevronLeft} className="top-1/2 left-1 -translate-y-1/2" />
            <Arrow action="right" icon={ChevronRight} className="top-1/2 right-1 -translate-y-1/2" />
            <button
              aria-label="Seleccionar"
              onClick={() => send("select")}
              className={cn(
                "absolute top-1/2 left-1/2 grid size-[76px] -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full border border-border-strong bg-secondary text-[12px] font-semibold text-foreground/80 transition-colors hover:bg-card-hover dark:border-white/[0.08]",
                pressed === "select" && "bg-muted"
              )}
            >
              OK
            </button>
          </div>
          <div className="grid grid-cols-4 gap-x-3 gap-y-4">
            <Key action="menu" icon={Undo2} label="Atrás" />
            <Key action="home" icon={House} label="Inicio" />
            <Key action="play_pause" icon={Play} label="Play" />
            <Key action="top_menu" icon={LayoutGrid} label="Control" />
            <Key action="volume_down" icon={Minus} label="Vol −" />
            <Key action="volume_up" icon={Plus} label="Vol +" />
            <Key action="turn_on" icon={Power} label="Encender" />
            <Key action="turn_off" icon={Power} label="Apagar" />
          </div>
          <p className="text-center text-[11px] leading-5 text-muted-foreground">
            También con el teclado: flechas, <Kbd>Enter</Kbd>, <Kbd>Esc</Kbd> y <Kbd>Espacio</Kbd>
          </p>
        </div>

        <div>
          <Section title="Ahora suena">
            <div className="rounded-lg border bg-card p-4 dark:border-black/20">
              <div className="flex items-center gap-4">
                <div className="grid size-14 shrink-0 place-items-center rounded-[6px] bg-muted">
                  <Music className="size-6 text-muted-foreground" strokeWidth={1.5} />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="truncate text-[14px] font-semibold">{np?.title ?? "Sin reproducción"}</div>
                  <div className="truncate text-[12px] text-muted-foreground">
                    {[np?.artist, np?.album].filter(Boolean).join(" — ") || np?.app || "—"}
                  </div>
                </div>
                <div className="flex items-center gap-1">
                  <Button variant="ghost" size="icon" aria-label="Anterior" onClick={() => send("previous")}>
                    <SkipBack className="size-4 fill-current" />
                  </Button>
                  <Button variant="secondary" size="icon-lg" className="rounded-full" aria-label="Reproducir o pausar" onClick={() => send("play_pause")}>
                    {np?.state === "Playing" ? <Pause className="size-4 fill-current" /> : <Play className="size-4 fill-current" />}
                  </Button>
                  <Button variant="ghost" size="icon" aria-label="Siguiente" onClick={() => send("next")}>
                    <SkipForward className="size-4 fill-current" />
                  </Button>
                </div>
              </div>
              <div className="mt-4 flex items-center gap-3 text-[11px] text-muted-foreground tabular-nums">
                <span className="w-9">{fmt(np?.position)}</span>
                <div className="h-1 flex-1 overflow-hidden rounded-full bg-foreground/15">
                  <div className="h-full bg-primary transition-[width]" style={{ width: `${progress}%` }} />
                </div>
                <span className="w-9 text-right">{fmt(np?.total)}</span>
              </div>
            </div>
          </Section>

          <Section title="Acciones">
            <Row icon={Keyboard} title="Escribir en la TV" description="Rellena buscadores y contraseñas desde el teclado del PC.">
              <Input
                className="w-56"
                value={text}
                placeholder="Texto"
                onChange={(e) => setText(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && target && call(() => api.post("keyboard", { id: target, text }))}
              />
              <Button disabled={!target || !text} onClick={() => call(() => api.post("keyboard", { id: target, text }))}>
                Enviar
              </Button>
            </Row>
            <Row icon={AppWindow} title="Abrir una app">
              <Select value={app} onValueChange={setApp} onOpenChange={(o) => o && loadApps()}>
                <SelectTrigger className="w-56">
                  <SelectValue placeholder={apps ? "Elegir app" : "Cargar apps…"} />
                </SelectTrigger>
                <SelectContent align="end">
                  {(apps ?? []).map((a) => (
                    <SelectItem key={a.id} value={a.id}>
                      {a.name}
                    </SelectItem>
                  ))}
                  {!apps && <div className="px-2.5 py-2 text-[12px] text-muted-foreground">Cargando…</div>}
                </SelectContent>
              </Select>
              <Button disabled={!app} onClick={() => call(() => api.post("apps/launch", { id: target, app }))}>
                Abrir
              </Button>
            </Row>
          </Section>
          <p className="text-[12px] text-muted-foreground">
            En Apple TV con tvOS 15 o posterior, empareja el servicio Companion desde Dispositivos para usar el mando.
          </p>
        </div>
      </div>
    </>
  )
}
