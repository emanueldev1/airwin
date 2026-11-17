import * as React from "react"
import { Loader2 } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { useAirwin } from "@/hooks/use-airwin"
import { api } from "@/lib/api"
import type { Device } from "@/lib/types"

type Step =
  | { kind: "choose" }
  | { kind: "starting"; protocol: string }
  | { kind: "pin"; session: string; showPin: string | null }
  | { kind: "finishing" }

export function PairDialog({ device, onClose }: { device: Device | null; onClose: () => void }) {
  const { call } = useAirwin()
  const [step, setStep] = React.useState<Step>({ kind: "choose" })
  const [pin, setPin] = React.useState("")

  React.useEffect(() => {
    if (device) {
      setStep({ kind: "choose" })
      setPin("")
    }
  }, [device])

  const close = () => {
    if (step.kind === "pin") void api.post("pair/cancel", { session: step.session }).catch(() => undefined)
    onClose()
  }

  const begin = async (protocol: string) => {
    if (!device) return
    setStep({ kind: "starting", protocol })
    const r = await call(() =>
      api.post<{ session: string; deviceProvidesPin: boolean; pin: string | null }>("pair/begin", {
        id: device.id,
        protocol,
      })
    )
    if (!r) return setStep({ kind: "choose" })
    setStep({ kind: "pin", session: r.session, showPin: r.deviceProvidesPin ? null : r.pin })
  }

  const finish = async () => {
    if (step.kind !== "pin") return
    const session = step.session
    setStep({ kind: "finishing" })
    const ok = await call(() => api.post("pair/finish", { session, pin }), "Emparejado correctamente")
    if (ok) onClose()
    else setStep({ kind: "choose" })
  }

  return (
    <Dialog open={!!device} onOpenChange={(o) => !o && close()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Emparejar con {device?.name}</DialogTitle>
          <DialogDescription>Solo hace falta una vez. Las credenciales se guardan en este PC.</DialogDescription>
        </DialogHeader>

        {step.kind === "choose" && (
          <div className="grid gap-2">
            {device?.pairable.map((p) => {
              const needed = device.needsPairing.includes(p.id)
              const done = device.paired.includes(p.id)
              return (
                <button
                  key={p.id}
                  onClick={() => begin(p.id)}
                  className="flex items-center justify-between rounded-[4px] border border-border-strong bg-secondary px-3 py-2.5 text-left text-[13px] transition-colors hover:bg-card-hover dark:border-white/[0.07]"
                >
                  <span>{p.label}</span>
                  <span className="text-xs text-muted-foreground">
                    {done ? "Emparejado" : needed ? "Necesario" : "Opcional"}
                  </span>
                </button>
              )
            })}
            <p className="pt-1 text-[12px] text-muted-foreground">
              Para un Apple TV empareja <b>AirPlay</b> (videos y pantalla) y <b>Companion</b> (mando a distancia).
            </p>
          </div>
        )}

        {(step.kind === "starting" || step.kind === "finishing") && (
          <div className="flex items-center justify-center gap-3 py-8 text-[13px] text-muted-foreground">
            <Loader2 className="size-5 animate-spin" />
            {step.kind === "starting" ? "Conectando con el dispositivo…" : "Verificando…"}
          </div>
        )}

        {step.kind === "pin" && (
          <div className="space-y-4">
            {step.showPin ? (
              <div className="space-y-3 text-center">
                <p className="text-[13px] text-muted-foreground">Introduce este código en el dispositivo:</p>
                <div className="font-display text-4xl font-semibold tracking-[0.4em]">{step.showPin}</div>
              </div>
            ) : (
              <div className="space-y-3">
                <p className="text-[13px] text-muted-foreground">
                  Escribe el código de 4 cifras que aparece en {device?.name}.
                </p>
                <div>
                  <Input
                    autoFocus
                    inputMode="numeric"
                    maxLength={8}
                    value={pin}
                    onChange={(e) => setPin(e.target.value.replace(/\D/g, ""))}
                    onKeyDown={(e) => e.key === "Enter" && pin && finish()}
                    className="h-10 text-center text-xl tracking-[0.5em]"
                    placeholder="0000"
                  />
                </div>
              </div>
            )}
            <DialogFooter>
              <Button onClick={close}>
                Cancelar
              </Button>
              <Button variant="default" onClick={finish} disabled={!step.showPin && pin.length < 4}>
                {step.showPin ? "Ya lo he introducido" : "Emparejar"}
              </Button>
            </DialogFooter>
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}
