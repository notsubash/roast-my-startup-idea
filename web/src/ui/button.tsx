import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex min-h-11 cursor-pointer items-center justify-center gap-2 border-2 border-ink font-sans text-sm font-semibold transition-[transform,box-shadow] duration-150 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-heat disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default:
          "bg-heat text-ink shadow-hard hover:translate-x-px hover:translate-y-px hover:shadow-none",
        secondary:
          "bg-card text-ink shadow-hard hover:translate-x-px hover:translate-y-px hover:shadow-none",
        outline: "bg-card text-ink shadow-hard",
        ghost: "border-transparent bg-transparent shadow-none hover:bg-paper-2",
        destructive: "bg-fail text-card shadow-hard",
      },
      size: {
        default: "rounded-ui px-4 py-2",
        sm: "min-h-9 rounded-ui px-3 py-1.5 text-xs",
        lg: "rounded-ui px-6 py-3 text-base",
        icon: "size-11 rounded-ui p-0",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  },
);

function Button({
  className,
  variant,
  size,
  asChild = false,
  ...props
}: React.ComponentProps<"button"> &
  VariantProps<typeof buttonVariants> & {
    asChild?: boolean;
  }) {
  const Comp = asChild ? Slot : "button";
  return (
    <Comp className={cn(buttonVariants({ variant, size, className }))} {...props} />
  );
}

export { Button, buttonVariants };
