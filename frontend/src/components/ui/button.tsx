import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { Slot } from "radix-ui"

import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "inline-flex shrink-0 items-center justify-center gap-2 rounded-[4px] text-[13px] font-normal whitespace-nowrap transition-colors outline-none select-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 focus-visible:ring-offset-background disabled:pointer-events-none disabled:opacity-45 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
  {
    variants: {
      variant: {
        default:
          "border border-black/10 bg-primary text-primary-foreground hover:bg-primary-hover active:opacity-90 disabled:border-transparent disabled:bg-foreground/[0.16] disabled:text-foreground/45 disabled:opacity-100 dark:border-white/10",
        destructive: "border border-black/10 bg-destructive text-white hover:bg-destructive/90 dark:text-black",
        outline:
          "border border-border-strong bg-secondary text-secondary-foreground shadow-[0_1px_0_rgba(0,0,0,0.04)] hover:bg-card-hover active:bg-muted dark:border-white/[0.07] dark:border-t-white/[0.09]",
        secondary:
          "border border-border-strong bg-secondary text-secondary-foreground hover:bg-card-hover active:bg-muted dark:border-white/[0.07] dark:border-t-white/[0.09]",
        ghost: "hover:bg-foreground/[0.06] active:bg-foreground/[0.04]",
        link: "text-primary underline-offset-4 hover:underline",
      },
      size: {
        default: "h-8 px-3",
        sm: "h-7 gap-1.5 px-2.5 text-[12px]",
        lg: "h-9 px-5",
        icon: "size-8",
        "icon-sm": "size-7",
        "icon-lg": "size-10",
      },
    },
    defaultVariants: { variant: "secondary", size: "default" },
  }
)

function Button({
  className,
  variant,
  size,
  asChild = false,
  ...props
}: React.ComponentProps<"button"> &
  VariantProps<typeof buttonVariants> & { asChild?: boolean }) {
  const Comp = asChild ? Slot.Root : "button"
  return <Comp data-slot="button" className={cn(buttonVariants({ variant, size, className }))} {...props} />
}

export { Button, buttonVariants }
