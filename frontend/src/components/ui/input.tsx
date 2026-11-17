import * as React from "react"

import { cn } from "@/lib/utils"

function Input({ className, type, ...props }: React.ComponentProps<"input">) {
  return (
    <input
      type={type}
      data-slot="input"
      className={cn(
        "h-8 w-full min-w-0 rounded-[4px] border border-border-strong border-b-input/70 bg-secondary px-2.5 text-[13px] transition-colors outline-none placeholder:text-muted-foreground/80 hover:bg-card-hover disabled:pointer-events-none disabled:opacity-50 dark:border-white/[0.07] dark:border-b-white/40",
        "focus:border-b-2 focus:border-b-primary focus:bg-background focus:pb-[1px] dark:focus:bg-[#1f1f1f]",
        className
      )}
      {...props}
    />
  )
}

export { Input }
