import * as React from "react";

import { cn } from "@/lib/utils";

function Skeleton({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      className={cn("animate-pulse border-2 border-rule-soft bg-paper-2", className)}
      {...props}
    />
  );
}

export { Skeleton };
