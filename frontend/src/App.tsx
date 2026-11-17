import * as React from "react"
import {
  Cast, Clapperboard, Gamepad2, MonitorUp, ScrollText, Settings, Speaker, Tv, type LucideIcon,
} from "lucide-react"

import { AppIcon, StatusDot, type Theme } from "@/components/common"
import { Toaster } from "@/components/ui/sonner"
import { UpdateBanner } from "@/components/update-banner"
import { TooltipProvider } from "@/components/ui/tooltip"
import { AirwinProvider, useAirwin, useScan } from "@/hooks/use-airwin"
import { cn } from "@/lib/utils"
import { AudioPage } from "@/pages/audio"
import { DevicesPage } from "@/pages/devices"
import { LogsPage } from "@/pages/logs"
import { ReceiverPage } from "@/pages/receiver"
import { RemotePage } from "@/pages/remote"
import { ScreenPage } from "@/pages/screen"
import { SettingsPage } from "@/pages/settings"
import { VideoPage } from "@/pages/video"

export type Page = "devices" | "audio" | "video" | "screen" | "remote" | "receiver" | "settings" | "logs"

const NAV: ({ id: Page; label: string; icon: LucideIcon } | "sep")[] = [
  { id: "devices", label: "Dispositivos", icon: Tv },
  { id: "audio", label: "Audio", icon: Speaker },
  { id: "video", label: "Video", icon: Clapperboard },
  { id: "screen", label: "Pantalla", icon: MonitorUp },
  { id: "remote", label: "Mando", icon: Gamepad2 },
  "sep",
  { id: "receiver", label: "Recibir en este PC", icon: Cast },
  "sep",
  { id: "logs", label: "Registro", icon: ScrollText },
  { id: "settings", label: "Configuración", icon: Settings },
]

function readLocal<T extends string>(key: string, fallback: T): T {
  try {
    return (localStorage.getItem(key) as T) || fallback
  } catch {
    return fallback
  }
}
function writeLocal(key: string, value: string) {
  try {
    localStorage.setItem(key, value)
  } catch {
    /* sin almacenamiento */
  }
}

function useTheme() {
  const [theme, setThemeState] = React.useState<Theme>(() => readLocal<Theme>("theme", "system"))
  React.useEffect(() => {
    const mq = window.matchMedia("(prefers-color-scheme: dark)")
    const apply = () =>
      document.documentElement.classList.toggle("dark", theme === "dark" || (theme === "system" && mq.matches))
    apply()
    mq.addEventListener("change", apply)
    return () => mq.removeEventListener("change", apply)
  }, [theme])
  const setTheme = (t: Theme) => {
    setThemeState(t)
    writeLocal("theme", t)
  }
  const resolved = theme === "system" ? (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light") : theme
  return [theme, setTheme, resolved] as const
}

function StatusBar() {
  const { state, connected } = useAirwin()
  const names = (ids: string[]) =>
    ids.map((id) => state?.devices.find((d) => d.id === id)?.name).filter(Boolean).join(", ")
  const audio = state?.audio.active ?? []
  const video = state?.video.active ?? []
  return (
    <footer className="flex h-7 shrink-0 items-center gap-5 border-t border-sidebar-border bg-sidebar px-4 text-[12px] text-muted-foreground">
      <span className="flex items-center gap-2">
        <StatusDot tone={connected ? "ok" : "warn"} />
        {!connected
          ? "Reconectando…"
          : state?.scanning
            ? "Buscando en la red…"
            : `${state?.devices.length ?? 0} ${state?.devices.length === 1 ? "dispositivo" : "dispositivos"}`}
      </span>
      {audio.length > 0 && <span className="truncate">Audio → {names(audio)}</span>}
      {video.length > 0 && <span className="truncate">Video → {names(video)}</span>}
      <span className="ml-auto flex items-center gap-2">
        <StatusDot tone={state?.receiver.running ? "live" : "off"} />
        Receptor {state?.receiver.running ? "activo" : "inactivo"}
      </span>
      {state?.update && ["available", "downloading", "ready"].includes(state.update.status) ? (
        <span className="text-primary">
          {state.update.status === "ready" ? "Actualización lista" : `v${state.update.latest} disponible`}
        </span>
      ) : (
        <span>v{state?.version}</span>
      )}
    </footer>
  )
}

function Shell() {
  const { state, connected } = useAirwin()
  const scan = useScan()
  const [page, setPageState] = React.useState<Page>(() => readLocal<Page>("page", "devices"))
  const [theme, setTheme, resolved] = useTheme()
  const scanned = React.useRef(false)

  const setPage = (p: Page) => {
    setPageState(p)
    writeLocal("page", p)
  }

  React.useEffect(() => {
    if (connected && !scanned.current) {
      scanned.current = true
      void scan()
    }
  }, [connected, scan])

  const live: Partial<Record<Page, boolean>> = {
    audio: (state?.audio.active.length ?? 0) > 0,
    video: (state?.video.active.length ?? 0) > (state?.video.screen.length ?? 0),
    screen: (state?.video.screen.length ?? 0) > 0,
    receiver: state?.receiver.running,
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex min-h-0 flex-1">
        <nav className="flex w-[260px] shrink-0 flex-col bg-sidebar px-2 pt-3 pb-3">
          <div className="mb-4 flex items-center gap-2.5 px-3 py-1.5">
            <AppIcon className="size-5" />
            <span className="text-[13px] font-semibold">{state?.app ?? "AirWin"}</span>
          </div>
          <div className="space-y-[2px]">
            {NAV.map((item, i) =>
              item === "sep" ? (
                <div key={i} className="mx-3 my-2 h-px bg-foreground/[0.08]" />
              ) : (
                <button
                  key={item.id}
                  onClick={() => setPage(item.id)}
                  className={cn(
                    "relative flex h-9 w-full items-center gap-3.5 rounded-[5px] px-3 text-[14px] transition-colors",
                    page === item.id ? "bg-foreground/[0.06]" : "hover:bg-foreground/[0.04] active:bg-foreground/[0.03]"
                  )}
                >
                  {page === item.id && (
                    <span className="absolute top-1/2 left-0 h-4 w-[3px] -translate-y-1/2 rounded-full bg-primary" />
                  )}
                  <item.icon className="size-[18px] shrink-0" strokeWidth={1.5} />
                  <span className="flex-1 text-left">{item.label}</span>
                  {live[item.id] && <StatusDot tone="live" />}
                </button>
              )
            )}
          </div>
        </nav>

        <main className="min-w-0 flex-1 overflow-y-auto">
          <div className="mx-auto max-w-[1000px] px-10 pt-6 pb-10">
            <UpdateBanner />
            {page === "devices" && <DevicesPage />}
            {page === "audio" && <AudioPage />}
            {page === "video" && <VideoPage />}
            {page === "screen" && <ScreenPage />}
            {page === "remote" && <RemotePage />}
            {page === "receiver" && <ReceiverPage onOpenSettings={() => setPage("settings")} />}
            {page === "settings" && <SettingsPage theme={theme} setTheme={setTheme} />}
            {page === "logs" && <LogsPage />}
          </div>
        </main>
      </div>
      <StatusBar />
      <Toaster position="bottom-right" offset={40} theme={resolved} />
    </div>
  )
}

export default function App() {
  return (
    <AirwinProvider>
      <TooltipProvider delayDuration={500}>
        <Shell />
      </TooltipProvider>
    </AirwinProvider>
  )
}
