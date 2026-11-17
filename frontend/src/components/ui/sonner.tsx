import { Toaster as Sonner, type ToasterProps } from "sonner"

const Toaster = ({ ...props }: ToasterProps) => (
  <Sonner
    className="toaster group"
    toastOptions={{
      classNames: {
        toast:
          "!rounded-lg !border !border-border-strong !bg-popover !text-popover-foreground !shadow-xl !text-[13px] dark:!border-black/40",
        description: "!text-muted-foreground",
      },
    }}
    {...props}
  />
)

export { Toaster }
