import * as React from "react"
import {
  Bug, Clapperboard, CloudDownload, ExternalLink, FolderOpen, Loader2, Network, Palette, Radar, RefreshCw, Router,
} from "lucide-react"

import { AppIcon, PageTitle, Row, Section, StatusDot, type Theme } from "@/components/common"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import { ReleaseNotesDialog, useUpdateActions } from "@/components/update-banner"
import { useAirwin } from "@/hooks/use-airwin"
import { api } from "@/lib/api"
import type { Settings } from "@/lib/types"

const REPO = "https://github.com/emanueldev1/airwin"

const DEPS = [
  { key: "bonjour", icon: Radar, name: "Bonjour", desc: "Servicio de Apple que hace visible el PC en la red. Necesario para recibir." },
  { key: "uxplay", icon: Router, name: "UxPlay", desc: "Receptor AirPlay: duplicación de pantalla, video y audio.", pathKey: "uxplay_path" },
  { key: "ffmpeg", icon: Clapperboard, name: "FFmpeg", desc: "Proyección de pantalla y conversión de video.", pathKey: "ffmpeg_path" },
] as const

export function SettingsPage({ theme, setTheme }: { theme: Theme; setTheme: (t: Theme) => void }) {
  const { state, call } = useAirwin()
  const [paths, setPaths] = React.useState<Partial<Settings> | null>(null)
  const values = paths ?? state?.settings ?? {}
  const u = state?.update
  const { check, download, install } = useUpdateActions()
  const [notes, setNotes] = React.useState(false)
  const setFlag = (key: keyof Settings, v: boolean) => call(() => api.post("settings", { [key]: v }))

  const updateText = () => {
    if (!u) return ""
    switch (u.status) {
      case "checking":
        return "Buscando actualizaciones…"
      case "uptodate":
        return `Tienes la versión más reciente (${u.current}).`
      case "available":
        return u.error ? `Versión ${u.latest} disponible. ${u.error}` : `Versión ${u.latest} disponible.`
      case "downloading":
        return `Descargando la versión ${u.latest}… ${Math.round(u.progress * 100)} %`
      case "ready":
        return `La versión ${u.latest} está lista para instalarse.`
      case "installing":
        return "Instalando…"
      case "error":
        return u.error ?? "No se pudo comprobar."
      default:
        return `Versión instalada: ${u.current}`
    }
  }

  const savePath = (key: keyof Settings, value: string) => call(() => api.post("settings", { [key]: value }))
  const browse = async (key: keyof Settings) => {
    const r = await call(() => api.post<{ path: string | null }>("pick", { kind: "exe" }))
    if (r?.path) {
      setPaths({ ...values, [key]: r.path })
      await savePath(key, r.path)
    }
  }

  return (
    <>
      <PageTitle title="Configuración" />

      <Section title="General">
        <Row icon={Palette} title="Tema de la aplicación">
          <Select value={theme} onValueChange={(v) => setTheme(v as Theme)}>
            <SelectTrigger className="w-44">
              <SelectValue />
            </SelectTrigger>
            <SelectContent align="end">
              <SelectItem value="light">Claro</SelectItem>
              <SelectItem value="dark">Oscuro</SelectItem>
              <SelectItem value="system">Usar el de Windows</SelectItem>
            </SelectContent>
          </Select>
        </Row>
        <Row icon={Network} title="Puerto del servidor multimedia" description="El Apple TV descarga videos y la pantalla desde este puerto.">
          <Input
            type="number"
            className="w-28"
            defaultValue={state?.settings.media_port}
            key={state?.settings.media_port}
            onBlur={(e) => call(() => api.post("settings", { media_port: Number(e.target.value) }))}
          />
        </Row>
      </Section>

      <Section title="Actualizaciones">
        <Row
          icon={u?.status === "available" || u?.status === "ready" ? CloudDownload : RefreshCw}
          title={updateText()}
          description={
            u?.checked_at
              ? `Última comprobación: ${new Date(u.checked_at * 1000).toLocaleString()}`
              : u?.can_install === false
                ? "Esta copia no está instalada: las versiones nuevas se descargan desde GitHub."
                : undefined
          }
        >
          {(u?.status === "available" || u?.status === "ready") && (
            <Button variant="ghost" onClick={() => setNotes(true)}>
              Novedades
            </Button>
          )}
          {u?.status === "ready" ? (
            <Button variant="default" onClick={() => install()}>
              Reiniciar y actualizar
            </Button>
          ) : u?.status === "available" ? (
            u.can_install ? (
              <Button variant="default" onClick={() => download()}>
                Descargar
              </Button>
            ) : (
              <Button variant="default" asChild>
                <a href={u.url} target="_blank" rel="noreferrer">
                  Descargar <ExternalLink className="size-3.5" />
                </a>
              </Button>
            )
          ) : (
            <Button disabled={u?.status === "checking" || u?.status === "downloading"} onClick={() => check()}>
              {u?.status === "checking" && <Loader2 className="animate-spin" />}
              Buscar actualizaciones
            </Button>
          )}
        </Row>
        <Row icon={RefreshCw} title="Buscar actualizaciones automáticamente" description="Al abrir la app y cada 6 horas.">
          <Switch
            checked={state?.settings.update_auto_check ?? true}
            onCheckedChange={(v) => setFlag("update_auto_check", v)}
          />
        </Row>
        <Row
          icon={CloudDownload}
          title="Descargar en segundo plano"
          description="Cuando esté lista, solo tendrás que reiniciar la app para actualizarla."
        >
          <Switch
            checked={state?.settings.update_auto_download ?? true}
            onCheckedChange={(v) => setFlag("update_auto_download", v)}
          />
        </Row>
        <ReleaseNotesDialog open={notes} onOpenChange={setNotes} />
      </Section>

      <Section title="Componentes">
        {DEPS.map((d) => {
          const found = state?.deps[d.key]
          const installing = state?.installing.includes(d.key)
          const pathKey = "pathKey" in d ? d.pathKey : undefined
          return (
            <Row
              key={d.key}
              icon={d.icon}
              title={d.name}
              description={found ? <span className="selectable">{found}</span> : d.desc}
            >
              <span className="flex items-center gap-2 text-[12px] text-muted-foreground">
                <StatusDot tone={found ? "ok" : "warn"} />
                {found ? "Instalado" : "No instalado"}
              </span>
              {pathKey && state?.canPickFiles && (
                <Button variant="ghost" size="icon" title="Elegir ubicación" onClick={() => browse(pathKey)}>
                  <FolderOpen />
                </Button>
              )}
              {pathKey && !state?.canPickFiles && (
                <Input
                  className="w-48 font-mono text-[12px]"
                  placeholder="Ruta personalizada"
                  value={(values[pathKey] as string) ?? ""}
                  onChange={(e) => setPaths({ ...values, [pathKey]: e.target.value })}
                  onBlur={(e) => savePath(pathKey, e.target.value)}
                />
              )}
              {!found && (
                <Button
                  variant="default"
                  disabled={installing || state?.platform !== "win32"}
                  onClick={() => call(() => api.post("deps/install", { name: d.key }))}
                >
                  {installing && <Loader2 className="animate-spin" />}
                  {installing ? "Instalando…" : "Instalar"}
                </Button>
              )}
            </Row>
          )
        })}
      </Section>

      <Section title="Acerca de">
        <Row
          iconNode={<AppIcon className="size-6" />}
          title={`${state?.app ?? "AirWin"} ${state?.version ?? ""}`}
          description="Software libre con licencia MIT. Basado en pyatv, UxPlay y FFmpeg. No está afiliado a Apple Inc."
        >
          <Button asChild>
            <a href={REPO} target="_blank" rel="noreferrer">
              Código fuente <ExternalLink className="size-3.5" />
            </a>
          </Button>
        </Row>
        <Row icon={Bug} title="Informar de un problema" description="Adjunta el contenido de Registro para que sea más fácil ayudarte.">
          <Button asChild>
            <a href={`${REPO}/issues/new`} target="_blank" rel="noreferrer">
              Abrir incidencia <ExternalLink className="size-3.5" />
            </a>
          </Button>
        </Row>
      </Section>
    </>
  )
}
