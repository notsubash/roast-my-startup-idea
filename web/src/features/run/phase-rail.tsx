import { cn } from "@/lib/utils";
import type { RunPhase } from "@/lib/sse/types";

const STEPS: { id: RunPhase; label: string }[] = [
  { id: "roast", label: "Roast" },
  { id: "debate", label: "Debate" },
  { id: "synthesis", label: "Synthesis" },
];

function stepIndex(phase: RunPhase): number {
  if (phase === "roast") return 0;
  if (phase === "debate") return 1;
  if (phase === "synthesis") return 2;
  return -1;
}

export function PhaseRail({
  phase,
  className,
}: {
  phase: RunPhase;
  className?: string;
}) {
  const active = stepIndex(phase);

  return (
    <nav aria-label="Run progress" className={cn("flex flex-wrap gap-2", className)}>
      {STEPS.map((step, idx) => {
        const isActive = idx === active;
        const isDone = active > idx;
        return (
          <div
            key={step.id}
            className={cn(
              "flex items-center gap-2 border-2 px-3 py-1.5 font-sans text-xs font-semibold uppercase tracking-widest",
              isActive && "border-ink bg-heat text-ink shadow-hard",
              isDone && "border-ink bg-card text-ink",
              !isActive && !isDone && "border-rule-soft bg-paper-2 text-ink-subtle",
            )}
            aria-current={isActive ? "step" : undefined}
          >
            <span className="font-mono text-[10px] opacity-70">{idx + 1}</span>
            {step.label}
          </div>
        );
      })}
    </nav>
  );
}
