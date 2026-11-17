import * as React from "react"
import { Switch as SwitchPrimitive } from "radix-ui"

import { cn } from "@/lib/utils"

/** Interruptor estilo Windows 11. */
function Switch({ className, ...props }: React.ComponentProps<typeof SwitchPrimitive.Root>) {
  return (
    <SwitchPrimitive.Root
      data-slot="switch"
      className={cn(
        "peer group inline-flex h-5 w-10 shrink-0 items-center rounded-full border transition-colors outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:opacity-40",
        "data-[state=unchecked]:border-foreground/60 data-[state=unchecked]:bg-black/[0.02] data-[state=unchecked]:hover:bg-foreground/[0.06]",
        "data-[state=checked]:border-primary data-[state=checked]:bg-primary data-[state=checked]:hover:bg-primary-hover",
        className
      )}
      {...props}
    >
      <SwitchPrimitive.Thumb
        data-slot="switch-thumb"
        className={cn(
          "pointer-events-none block rounded-full transition-all duration-150",
          "data-[state=unchecked]:ml-[3px] data-[state=unchecked]:size-3 data-[state=unchecked]:bg-foreground/75 group-hover:data-[state=unchecked]:size-3.5 group-hover:data-[state=unchecked]:ml-[2px]",
          "data-[state=checked]:ml-[22px] data-[state=checked]:size-3.5 data-[state=checked]:bg-primary-foreground"
        )}
      />
    </SwitchPrimitive.Root>
  )
}

export { Switch }
