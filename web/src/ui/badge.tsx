import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center border-2 border-ink px-2 py-0.5 font-sans text-xs font-semibold uppercase tracking-wide",
  {
    variants: {
      variant: {
        default: "bg-paper-2 text-ink",
        pass: "bg-pass/10 text-pass",
        fail: "bg-fail/10 text-fail",
        conditional: "bg-conditional/10 text-conditional",
        heat: "bg-heat/10 text-heat-ink",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  },
);

function Badge({
  className,
  variant,
  ...props
}: React.ComponentProps<"span"> & VariantProps<typeof badgeVariants>) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { Badge, badgeVariants };
