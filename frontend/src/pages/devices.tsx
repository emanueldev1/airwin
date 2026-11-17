import * as React from "react"
import { Copy, Link2, MoreHorizontal, RefreshCw, Trash2 } from "lucide-react"
import { toast } from "sonner"

import { DeviceIcon, PageTitle, Row, Section, StatusDot } from "@/components/common"
import { PairDialog } from "@/components/pair-dialog"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { useAirwin, useScan } from "@/hooks/use-airwin"
import { api } from "@/lib/api"
import type { Device } from "@/lib/types"
import { cn } from "@/lib/utils"

const FEATURES: [string, string][] = [
  ["RAOP", "Audio"],
  ["AirPlay", "Video"],
  ["Companion", "Mando"],
  ["MRP", "Mando"],
]

function features(d: Device) {
  return [...new Set(FEATURES.filter(([p]) => d.protocols.includes(p)).map(([, l]) => l))].join(", ")
}

export function DevicesPage() {
  const { state, call } = useAirwin()
  const scan = useScan()
  const [pairing, setPairing] = React.useState<Device | null>(null)
  const devices = state?.devices ?? []
  const scanning = state?.scanning ?? false

  const groups = [
    { title: "Apple TV y Mac", items: devices.filter((d) => d.kind === "Apple TV" || d.kind === "Mac" || d.kind === "TV con AirPlay") },
    { title: "Altavoces", items: devices.filter((d) => d.kind === "HomePod" || d.kind === "Altavoz AirPlay") },
  ].filter((g) => g.items.length)

  return (
    <>
      <PageTitle
        title="Dispositivos"
        actions={
          <Button onClick={() => scan()} disabled={scanning}>
            <RefreshCw className={cn(scanning && "animate-spin")} />
            {scanning ? "Buscando…" : "Actualizar"}
          </Button>
        }
      />

      {devices.length === 0 && (
        <Section>
          <Row
            icon={RefreshCw}
            title={scanning ? "Buscando dispositivos en la red…" : "No se encontró ningún dispositivo"}
            description={
              scanning
                ? "Puede tardar unos segundos."
                : "El PC y los dispositivos deben estar en la misma red. Revisa que el firewall permita AirWin en redes privadas."
            }
          >
            {!scanning && <Button onClick={() => scan()}>Reintentar</Button>}
          </Row>
        </Section>
      )}

      {groups.map((g) => (
        <Section key={g.title} title={g.title}>
          {g.items.map((d) => {
            const pending = d.needsPairing.length > 0
            return (
              <Row
                key={d.id}
                iconNode={<DeviceIcon kind={d.kind} className="size-6 shrink-0 text-foreground/85" />}
                title={d.name}
                description={
                  <>
                    {d.model} · <span className="selectable">{d.address}</span> · {features(d)}
                  </>
                }
              >
                <span className="flex items-center gap-2 text-[12px] text-muted-foreground">
                  <StatusDot tone={pending ? "warn" : "ok"} />
                  {pending ? "Sin emparejar" : d.paired.length ? "Emparejado" : "Disponible"}
                </span>
                {d.pairable.length > 0 && (
                  <Button variant={pending ? "default" : "secondary"} onClick={() => setPairing(d)}>
                    <Link2 /> Emparejar
                  </Button>
                )}
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button variant="ghost" size="icon" aria-label="Más opciones">
                      <MoreHorizontal />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    <DropdownMenuItem
                      onSelect={() => {
                        void navigator.clipboard?.writeText(d.address)
                        toast("Dirección copiada")
                      }}
                    >
                      <Copy /> Copiar dirección IP
                    </DropdownMenuItem>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem
                      variant="destructive"
                      disabled={!d.paired.length}
                      onSelect={() => call(() => api.post("forget", { id: d.id }), "Credenciales eliminadas")}
                    >
                      <Trash2 /> Olvidar emparejamiento
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </Row>
            )
          })}
        </Section>
      ))}
      <PairDialog device={pairing} onClose={() => setPairing(null)} />
    </>
  )
}
