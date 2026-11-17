import * as React from "react"
import { Cast, Expand, Gauge, KeyRound, MonitorSmartphone, ScrollText, Speaker, Timer } from "lucide-react"

import { ExpanderRow, InfoBar, PageTitle, Row, Section } from "@/components/common"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import { useAirwin } from "@/hooks/use-airwin"
import { api } from "@/lib/api"
import type { Settings } from "@/lib/types"

export function ReceiverPage({ onOpenSettings }: { onOpenSettings: () => void }) {
  const { state, call, receiverLog } = useAirwin()
  const running = state?.receiver.running ?? false
  const [form, setForm] = React.useState<Partial<Settings> | null>(null)
  const logRef = React.useRef<HTMLPreElement>(null)
  const values = form ?? state?.settings ?? {}
  const missing = state && (!state.deps.uxplay || !state.deps.bonjour)

  React.useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight })
  }, [receiverLog])

  const update = <K extends keyof Settings>(key: K, value: Settings[K]) => {
    setForm({ ...values, [key]: value })
    void api.post("settings", { [key]: value }).catch(() => undefined)
  }

  const toggle = (on: boolean) => call(() => (on ? api.post("receiver/start", {}) : api.post("receiver/stop")))

  return (
    <>
      <PageTitle title="Recibir en este PC" />

      {missing && (
        <div className="mb-6">
          <InfoBar
            tone="warning"
            title="Faltan componentes"
            action={<Button size="sm" onClick={onOpenSettings}>Instalar</Button>}
          >
            Se necesitan Bonjour y UxPlay para que tus dispositivos Apple vean este PC.
          </InfoBar>
        </div>
      )}

      <Section>
        <Row
          icon={Cast}
          title="Receptor AirPlay"
          description="Permite que iPhone, iPad y Mac dupliquen su pantalla o envíen videos y música a este PC."
        >
          <span className="text-[13px] text-muted-foreground">{running ? "Activado" : "Desactivado"}</span>
          <Switch checked={running} onCheckedChange={toggle} disabled={!state?.deps.uxplay} />
        </Row>
        {running && (
          <InfoBar tone="info">
            En el iPhone abre el Centro de control, toca <b>Duplicar pantalla</b> y elige «{values.receiver_name}».
          </InfoBar>
        )}
      </Section>

      <Section title="Opciones">
        <Row icon={MonitorSmartphone} title="Nombre del PC" description="Así aparece en la lista de AirPlay.">
          <Input className="w-56" value={values.receiver_name ?? ""} onChange={(e) => update("receiver_name", e.target.value)} />
        </Row>
        <Row icon={Gauge} title="Resolución">
          <Select value={values.receiver_resolution} onValueChange={(v) => update("receiver_resolution", v)}>
            <SelectTrigger className="w-44">
              <SelectValue />
            </SelectTrigger>
            <SelectContent align="end">
              <SelectItem value="1280x720">1280 × 720</SelectItem>
              <SelectItem value="1920x1080">1920 × 1080</SelectItem>
              <SelectItem value="2560x1440">2560 × 1440</SelectItem>
              <SelectItem value="3840x2160">3840 × 2160</SelectItem>
            </SelectContent>
          </Select>
        </Row>
        <Row icon={Timer} title="Fotogramas por segundo">
          <Select value={String(values.receiver_fps ?? 60)} onValueChange={(v) => update("receiver_fps", Number(v))}>
            <SelectTrigger className="w-44">
              <SelectValue />
            </SelectTrigger>
            <SelectContent align="end">
              <SelectItem value="30">30 fps</SelectItem>
              <SelectItem value="60">60 fps</SelectItem>
            </SelectContent>
          </Select>
        </Row>
        <Row icon={Expand} title="Abrir en pantalla completa">
          <Switch checked={!!values.receiver_fullscreen} onCheckedChange={(v) => update("receiver_fullscreen", v)} />
        </Row>
        <Row icon={Speaker} title="Solo audio" description="El PC funciona como un altavoz AirPlay.">
          <Switch checked={!!values.receiver_audio_only} onCheckedChange={(v) => update("receiver_audio_only", v)} />
        </Row>
        <Row icon={KeyRound} title="Código de acceso" description="Vacío: sin código. 4 cifras: código fijo. *: uno nuevo cada vez.">
          <Input
            className="w-28 text-center font-mono tracking-widest"
            maxLength={4}
            placeholder="—"
            value={values.receiver_pin ?? ""}
            onChange={(e) => update("receiver_pin", e.target.value.replace(/[^\d*]/g, ""))}
          />
        </Row>
        <ExpanderRow icon={ScrollText} title="Actividad" description="Mensajes del receptor (UxPlay).">
          <pre
            ref={logRef}
            className="selectable h-48 overflow-auto rounded-[4px] border bg-console p-3 font-mono text-[12px] leading-5 text-foreground/80"
          >
            {receiverLog.length ? receiverLog.join("\n") : "Sin actividad."}
          </pre>
        </ExpanderRow>
      </Section>
      <p className="text-[12px] text-muted-foreground">Los cambios se aplican la próxima vez que se active el receptor.</p>
    </>
  )
}
