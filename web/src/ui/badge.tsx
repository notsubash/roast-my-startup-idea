import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded-ui border px-2 py-0.5 font-sans text-xs font-semibold uppercase tracking-wide",
  {
    variants: {
      variant: {
        default: "border-rule-soft bg-paper-2 text-ink",
        pass: "border-pass/30 bg-pass/10 text-pass",
        fail: "border-fail/30 bg-fail/10 text-fail",
        conditional: "border-conditional/30 bg-conditional/10 text-conditional",
        heat: "border-cta/30 bg-cta/10 text-cta",
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
