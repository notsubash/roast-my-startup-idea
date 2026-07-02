import { cn } from "@/lib/utils";

function Skeleton({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      className={cn("animate-pulse rounded-ui border border-rule-soft bg-paper-2", className)}
      {...props}
    />
  );
}

export { Skeleton };
