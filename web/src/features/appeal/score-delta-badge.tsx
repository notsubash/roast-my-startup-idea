import { cn } from "@/lib/utils";

export function ScoreDeltaBadge({ delta }: { delta: number }) {
  if (delta === 0) {
    return (
      <span
        className="font-sans text-xs font-medium text-ink-muted"
        aria-label="Score unchanged"
      >
        unchanged
      </span>
    );
  }

  const positive = delta > 0;
  return (
    <span
      className={cn(
        "inline-flex items-center border border-ink px-1.5 py-0.5 font-mono text-xs font-bold leading-none",
        positive ? "bg-pass/15 text-pass" : "bg-fail/15 text-fail",
      )}
      aria-label={`Score ${positive ? "increased" : "decreased"} by ${Math.abs(delta)}`}
    >
      {positive ? "+" : ""}
      {delta}
    </span>
  );
}
