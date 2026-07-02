"use client";

import { useMemo, type CSSProperties } from "react";

import {
  computeConfidenceFromVerdicts,
  confidenceTier,
  type ConfidenceDimensionScore,
  type ConfidenceSnapshot,
} from "@/lib/confidence/confidence";
import type { Verdict } from "@/lib/sse/types";
import { cn } from "@/lib/utils";

import { VERSION_COPY } from "../run/run-page-copy";

function tierClass(tier: ReturnType<typeof confidenceTier>): string {
  switch (tier) {
    case "High":
      return "bg-pass";
    case "Medium":
      return "bg-conditional";
    default:
      return "bg-fail/70";
  }
}

function ConfidenceBar({
  item,
  compact = false,
  delayMs = 0,
}: {
  item: ConfidenceDimensionScore;
  compact?: boolean;
  delayMs?: number;
}) {
  const tier = item.tier;
  return (
    <div className={cn(compact ? "space-y-1" : "space-y-1.5")}>
      <div className="flex items-baseline justify-between gap-2">
        <span
          className={cn(
            "font-sans font-semibold text-ink",
            compact ? "text-[11px]" : "text-xs",
          )}
        >
          {item.label}
        </span>
        <span
          className={cn(
            "font-mono tabular-nums text-ink-muted",
            compact ? "text-[10px]" : "text-xs",
          )}
        >
          {item.value}
          <span className="sr-only"> out of 100, </span>
          <span aria-hidden> · {tier}</span>
        </span>
      </div>
      <div
        className={cn(
          "overflow-hidden border border-rule-soft bg-paper-2",
          compact ? "h-1.5" : "h-2",
        )}
        role="progressbar"
        aria-valuenow={item.value}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`${item.label} confidence: ${item.value} out of 100, ${tier}`}
      >
        <div
          className={cn(
            "h-full motion-reduce:!w-[var(--fill-pct)] motion-reduce:animate-none",
            "animate-progress-fill transition-[width] duration-200 motion-reduce:transition-none",
            tierClass(tier),
          )}
          style={
            {
              "--fill-pct": `${item.value}%`,
              animationDelay: `${delayMs}ms`,
            } as CSSProperties
          }
        />
      </div>
      {!compact && item.driver && (
        <p className="font-sans text-xs leading-relaxed text-ink-muted">
          {item.driver}
        </p>
      )}
    </div>
  );
}

export function ConfidenceBars({
  verdicts,
  snapshot: providedSnapshot,
  className,
  compact = false,
  title = VERSION_COPY.confidenceTitle,
}: {
  verdicts?: Verdict[];
  snapshot?: ConfidenceSnapshot | null;
  className?: string;
  compact?: boolean;
  title?: string;
}) {
  const snapshot = useMemo(() => {
    if (providedSnapshot) return providedSnapshot;
    if (!verdicts?.length) return null;
    return computeConfidenceFromVerdicts(verdicts);
  }, [providedSnapshot, verdicts]);

  if (!snapshot) return null;

  return (
    <section
      className={cn(compact ? "space-y-2" : "space-y-4", className)}
      aria-label={title}
    >
      {!compact && (
        <h3 className="font-sans text-sm font-semibold text-ink">{title}</h3>
      )}
      <div className={cn(compact ? "grid gap-2 sm:grid-cols-2" : "grid gap-4 sm:grid-cols-2")}>
        {snapshot.dimensions.map((item, index) => (
          <ConfidenceBar key={item.dimension} item={item} compact={compact} delayMs={index * 60} />
        ))}
      </div>
    </section>
  );
}
