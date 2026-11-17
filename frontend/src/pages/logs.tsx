import * as React from "react"
import { Copy, Trash2 } from "lucide-react"
import { toast } from "sonner"

import { PageTitle } from "@/components/common"
import { Button } from "@/components/ui/button"
import { useAirwin } from "@/hooks/use-airwin"
import { cn } from "@/lib/utils"

export function LogsPage() {
  const { logs, clearLogs } = useAirwin()
  const ref = React.useRef<HTMLDivElement>(null)
  React.useEffect(() => {
    ref.current?.scrollTo({ top: ref.current.scrollHeight })
  }, [logs])

  const copy = () => {
    const text = logs.map((l) => `${new Date(l.time * 1000).toLocaleTimeString()} ${l.level.toUpperCase()} ${l.message}`).join("\n")
    void navigator.clipboard?.writeText(text)
    toast("Registro copiado al portapapeles")
  }

  return (
    <>
      <PageTitle
        title="Registro"
        actions={
          <>
            <Button onClick={copy} disabled={!logs.length}>
              <Copy /> Copiar
            </Button>
            <Button onClick={clearLogs} disabled={!logs.length}>
              <Trash2 /> Borrar
            </Button>
          </>
        }
      />
      <div
        ref={ref}
        className="selectable h-[calc(100vh-10.5rem)] overflow-auto rounded-lg border bg-console px-4 py-3 font-mono text-[12px] leading-[1.7] dark:border-black/20"
      >
        {logs.length === 0 && <div className="text-muted-foreground">No hay mensajes.</div>}
        {logs.map((l, i) => (
          <div key={i} className="flex gap-4">
            <span className="shrink-0 text-muted-foreground tabular-nums">{new Date(l.time * 1000).toLocaleTimeString()}</span>
            <span
              className={cn(
                "min-w-0 break-words whitespace-pre-wrap",
                l.level === "error" && "text-destructive",
                l.level === "warning" && "text-warning"
              )}
            >
              {l.message}
            </span>
          </div>
        ))}
      </div>
    </>
  )
}
