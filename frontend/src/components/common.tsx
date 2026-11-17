import * as React from "react"
import { ChevronDown, CircleAlert, Info, Laptop, Speaker, Tv, TvMinimal, type LucideIcon } from "lucide-react"

import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { cn } from "@/lib/utils"
import type { Device, DeviceKind } from "@/lib/types"

export const KIND_ICON: Record<DeviceKind, LucideIcon> = {
  "Apple TV": Tv,
  HomePod: Speaker,
  Mac: Laptop,
  "TV con AirPlay": TvMinimal,
  "Altavoz AirPlay": Speaker,
}

export function DeviceIcon({ kind, className }: { kind: DeviceKind; className?: string }) {
  const Icon = KIND_ICON[kind] ?? Speaker
  return <Icon className={className} strokeWidth={1.5} />
}

/** Título de página como en Configuración de Windows. */
export function PageTitle({ title, actions }: { title: string; actions?: React.ReactNode }) {
  return (
    <div className="mb-6 flex min-h-10 items-center justify-between gap-4">
      <h1 className="font-display text-[28px] leading-9 font-semibold tracking-[-0.01em]">{title}</h1>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  )
}

export function Section({ title, children, className }: { title?: string; children: React.ReactNode; className?: string }) {
  return (
    <section className={cn("mb-6", className)}>
      {title && <h2 className="mb-2 text-[14px] font-semibold">{title}</h2>}
      <div className="space-y-[3px]">{children}</div>
    </section>
  )
}

/** Fila de ajustes (SettingsCard de Fluent): icono, título, descripción y control a la derecha. */
export function Row({
  icon: Icon,
  iconNode,
  title,
  description,
  children,
  className,
  onClick,
  as: As = "div",
}: {
  icon?: LucideIcon
  iconNode?: React.ReactNode
  title: React.ReactNode
  description?: React.ReactNode
  children?: React.ReactNode
  className?: string
  onClick?: () => void
  as?: "div" | "label"
}) {
  return (
    <As
      onClick={onClick}
      className={cn(
        "flex min-h-[68px] items-center gap-4 rounded-lg border bg-card px-4 py-3 dark:border-black/20",
        (onClick || As === "label") && "cursor-default transition-colors hover:bg-card-hover",
        className
      )}
    >
      {iconNode ?? (Icon && <Icon className="size-5 shrink-0 text-foreground/85" strokeWidth={1.5} />)}
      <div className="min-w-0 flex-1">
        <div className="truncate text-[14px] leading-5">{title}</div>
        {description && <div className="text-[12px] leading-4 text-muted-foreground">{description}</div>}
      </div>
      {children && <div className="flex shrink-0 items-center gap-3">{children}</div>}
    </As>
  )
}

/** Fila desplegable (SettingsExpander). */
export function ExpanderRow({
  icon,
  title,
  description,
  children,
  defaultOpen = false,
}: {
  icon?: LucideIcon
  title: React.ReactNode
  description?: React.ReactNode
  children: React.ReactNode
  defaultOpen?: boolean
}) {
  const [open, setOpen] = React.useState(defaultOpen)
  return (
    <div className="overflow-hidden rounded-lg border bg-card dark:border-black/20">
      <button className="flex w-full text-left" onClick={() => setOpen((o) => !o)}>
        <Row icon={icon} title={title} description={description} className="flex-1 rounded-none border-0 hover:bg-card-hover">
          <ChevronDown className={cn("size-4 text-muted-foreground transition-transform", open && "rotate-180")} />
        </Row>
      </button>
      {open && <div className="border-t px-4 py-3 dark:border-black/30">{children}</div>}
    </div>
  )
}

/** InfoBar de Fluent. */
export function InfoBar({
  tone = "info",
  title,
  children,
  action,
}: {
  tone?: "info" | "warning" | "success"
  title?: string
  children?: React.ReactNode
  action?: React.ReactNode
}) {
  const Icon = tone === "info" ? Info : CircleAlert
  return (
    <div
      className={cn(
        "flex min-h-12 items-center gap-3 rounded-lg border px-4 py-2.5 text-[13px] dark:border-black/20",
        tone === "info" && "bg-card",
        tone === "warning" && "border-[#f7e7b7] bg-[#fff4ce] dark:bg-[#433519]",
        tone === "success" && "border-[#cfe9cf] bg-[#dff6dd] dark:bg-[#393d1b]"
      )}
    >
      <span
        className={cn(
          "grid size-4 shrink-0 place-items-center rounded-full",
          tone === "info" && "bg-primary text-primary-foreground",
          tone === "warning" && "bg-warning text-white dark:text-black",
          tone === "success" && "bg-success text-white dark:text-black"
        )}
      >
        <Icon className="size-4" strokeWidth={2} />
      </span>
      <div className="min-w-0 flex-1">
        {title && <span className="mr-2 font-semibold">{title}</span>}
        <span className="text-foreground/85">{children}</span>
      </div>
      {action}
    </div>
  )
}

export function DevicePicker({
  devices,
  value,
  onChange,
  placeholder = "Elegir dispositivo",
  className,
}: {
  devices: Device[]
  value: string | undefined
  onChange: (id: string) => void
  placeholder?: string
  className?: string
}) {
  return (
    <Select value={value ?? ""} onValueChange={onChange} disabled={devices.length === 0}>
      <SelectTrigger className={cn("w-60", className)}>
        <SelectValue placeholder={devices.length ? placeholder : "Ninguno disponible"} />
      </SelectTrigger>
      <SelectContent>
        {devices.map((d) => (
          <SelectItem key={d.id} value={d.id}>
            <DeviceIcon kind={d.kind} />
            {d.name}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}

/** Recuerda el dispositivo elegido y usa otro si el guardado desaparece. */
export function useDeviceChoice(devices: Device[], storageKey: string) {
  const [value, setValue] = React.useState<string | undefined>(() => {
    try {
      return localStorage.getItem(storageKey) ?? undefined
    } catch {
      return undefined
    }
  })
  const valid = devices.some((d) => d.id === value) ? value : devices[0]?.id
  const set = React.useCallback(
    (id: string) => {
      setValue(id)
      try {
        localStorage.setItem(storageKey, id)
      } catch {
        /* sin almacenamiento */
      }
    },
    [storageKey]
  )
  return [valid, set] as const
}

export function StatusDot({ tone }: { tone: "ok" | "warn" | "off" | "live" }) {
  return (
    <span
      className={cn(
        "inline-block size-2 shrink-0 rounded-full",
        tone === "ok" && "bg-success",
        tone === "warn" && "bg-warning",
        tone === "off" && "bg-muted-foreground/50",
        tone === "live" && "bg-primary"
      )}
    />
  )
}

export function Kbd({ children }: { children: React.ReactNode }) {
  return (
    <kbd className="rounded-[3px] border border-border-strong bg-card px-1 py-px font-sans text-[11px] text-foreground/80">
      {children}
    </kbd>
  )
}

export type Theme = "dark" | "light" | "system"

export function AppIcon({ className }: { className?: string }) {
  return <img src="./favicon.svg" alt="" className={cn("size-4", className)} draggable={false} />
}
