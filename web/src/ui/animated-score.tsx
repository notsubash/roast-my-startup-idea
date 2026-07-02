"use client";

import { useAnimatedNumber } from "@/hooks/use-animated-number";
import { cn } from "@/lib/utils";

export function AnimatedScore({
  value,
  className,
  decimals = 1,
  suffix,
  animateFrom,
}: {
  value: number | null | undefined;
  className?: string;
  decimals?: number;
  suffix?: string;
  /** When set, animates from this value to `value` on mount/update. */
  animateFrom?: number | null;
}) {
  const animated = useAnimatedNumber(value ?? null, 250, animateFrom);

  if (animated == null) {
    return <span className={className}>—</span>;
  }

  return (
    <span className={cn("tabular-nums", className)}>
      {animated.toFixed(decimals)}
      {suffix}
    </span>
  );
}
