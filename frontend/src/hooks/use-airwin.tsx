import * as React from "react"
import { toast } from "sonner"

import { api, eventsUrl } from "@/lib/api"
import type { AppState, LogLine } from "@/lib/types"

interface Store {
  state: AppState | null
  connected: boolean
  logs: LogLine[]
  receiverLog: string[]
  level: number
  /** Ejecuta una llamada a la API mostrando errores como notificación. */
  call: <T>(fn: () => Promise<T>, success?: string) => Promise<T | undefined>
  clearLogs: () => void
}

const Ctx = React.createContext<Store | null>(null)
const MAX_LINES = 600

export function AirwinProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = React.useState<AppState | null>(null)
  const [connected, setConnected] = React.useState(false)
  const [logs, setLogs] = React.useState<LogLine[]>([])
  const [receiverLog, setReceiverLog] = React.useState<string[]>([])
  const [level, setLevel] = React.useState(0)

  React.useEffect(() => {
    let es: EventSource | null = null
    let retry: ReturnType<typeof setTimeout> | undefined
    const connect = () => {
      es = new EventSource(eventsUrl())
      es.onopen = () => setConnected(true)
      es.onerror = () => {
        setConnected(false)
        es?.close()
        retry = setTimeout(connect, 1500)
      }
      es.onmessage = (msg) => {
        const ev = JSON.parse(msg.data)
        switch (ev.type) {
          case "state":
            setState(ev.data)
            break
          case "log":
            setLogs((l) => [...l.slice(-MAX_LINES), ev])
            if (ev.level === "error") toast.error(ev.message)
            break
          case "receiver":
            setReceiverLog((l) => [...l.slice(-MAX_LINES), ev.line])
            break
          case "level":
            setLevel(ev.value)
            break
          case "toast":
            if (ev.kind === "error") toast.error(ev.message)
            else if (ev.kind === "success") toast.success(ev.message)
            else toast(ev.message)
            break
        }
      }
    }
    connect()
    return () => {
      clearTimeout(retry)
      es?.close()
    }
  }, [])

  const call = React.useCallback(async <T,>(fn: () => Promise<T>, success?: string) => {
    try {
      const r = await fn()
      if (success) toast.success(success)
      return r
    } catch (e) {
      toast.error(e instanceof Error ? e.message : String(e))
      return undefined
    }
  }, [])

  const value = React.useMemo<Store>(
    () => ({ state, connected, logs, receiverLog, level, call, clearLogs: () => setLogs([]) }),
    [state, connected, logs, receiverLog, level, call]
  )
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useAirwin() {
  const ctx = React.useContext(Ctx)
  if (!ctx) throw new Error("useAirwin fuera de AirwinProvider")
  return ctx
}

export function useScan() {
  const { call } = useAirwin()
  return React.useCallback(() => call(() => api.post("scan")), [call])
}
