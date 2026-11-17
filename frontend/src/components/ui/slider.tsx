import * as React from "react"
import { Slider as SliderPrimitive } from "radix-ui"

import { cn } from "@/lib/utils"

/** Deslizador estilo Windows 11: pista fina y pulgar con punto de acento. */
function Slider({ className, defaultValue, value, min = 0, max = 100, ...props }: React.ComponentProps<typeof SliderPrimitive.Root>) {
  const _values = React.useMemo(
    () => (Array.isArray(value) ? value : Array.isArray(defaultValue) ? defaultValue : [min]),
    [value, defaultValue, min]
  )
  return (
    <SliderPrimitive.Root
      data-slot="slider"
      defaultValue={defaultValue}
      value={value}
      min={min}
      max={max}
      className={cn("relative flex h-5 w-full touch-none items-center select-none data-[disabled]:opacity-40", className)}
      {...props}
    >
      <SliderPrimitive.Track className="relative h-1 grow overflow-hidden rounded-full bg-foreground/45">
        <SliderPrimitive.Range className="absolute h-full bg-primary" />
      </SliderPrimitive.Track>
      {_values.map((_, i) => (
        <SliderPrimitive.Thumb
          key={i}
          className="group grid size-5 place-items-center rounded-full border border-border-strong bg-card shadow-[0_1px_2px_rgba(0,0,0,0.2)] outline-none focus-visible:ring-2 focus-visible:ring-ring dark:border-white/10 dark:bg-[#454545]"
        >
          <span className="size-2.5 rounded-full bg-primary transition-all group-hover:size-3 group-active:size-2" />
        </SliderPrimitive.Thumb>
      ))}
    </SliderPrimitive.Root>
  )
}

export { Slider }
