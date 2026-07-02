import { AlertTriangle, CheckCircle, HelpCircle } from "lucide-react";

import { cn } from "@/lib/utils";
import { JUDGE_ORDER } from "@/lib/sse/types";
import type { JudgeView } from "@/lib/sse/types";

import {
  VERDICT_SEGMENT,
  verdictTally,
  verdictTallySummary,
} from "./verdict-stats";

const VERDICT_ICONS = {
  PASS: CheckCircle,
  CONDITIONAL: HelpCircle,
  FAIL: AlertTriangle,
} as const;

export function VerdictTallyBar({
  judges,
  className,
}: {
  judges: Record<(typeof JUDGE_ORDER)[number], JudgeView>;
  className?: string;
}) {
  const tally = verdictTally(judges);
  const revealed = tally.pass + tally.conditional + tally.fail;

  if (revealed === 0) {
    return (
      <p className={cn("font-sans text-sm text-ink-subtle", className)}>
        The split appears once judges start delivering verdicts.
      </p>
    );
  }

  const segments = (
    [
      { key: "PASS" as const, count: tally.pass },
      { key: "CONDITIONAL" as const, count: tally.conditional },
      { key: "FAIL" as const, count: tally.fail },
    ] as const
  ).filter((s) => s.count > 0);

  return (
    <div className={cn("space-y-3", className)}>
      <div
        className="flex h-8 overflow-hidden border border-rule-soft bg-paper-2"
        role="img"
        aria-label={`Verdict split: ${verdictTallySummary(tally)}`}
      >
        {segments.map(({ key, count }) => {
          const cfg = VERDICT_SEGMENT[key];
          const Icon = VERDICT_ICONS[key];
          return (
            <div
              key={key}
              className={cn(
                "flex min-w-[3rem] items-center justify-center gap-1 px-2 font-sans text-xs font-bold uppercase tracking-wide text-ink",
                cfg.barClass,
              )}
              style={{ flexGrow: count, flexBasis: 0 }}
            >
              <Icon className="size-3.5 shrink-0" aria-hidden />
              <span>{count}</span>
              <span className="hidden sm:inline">{cfg.label}</span>
            </div>
          );
        })}
        {tally.pending > 0 && (
          <div
            className="flex min-w-[2rem] items-center justify-center bg-paper px-2 font-mono text-xs text-ink-subtle"
            style={{ flexGrow: tally.pending, flexBasis: 0 }}
            aria-hidden
          />
        )}
      </div>

      <ul className="flex flex-wrap gap-x-4 gap-y-1 font-sans text-xs text-ink-muted">
        {segments.map(({ key, count }) => {
          const cfg = VERDICT_SEGMENT[key];
          const Icon = VERDICT_ICONS[key];
          return (
            <li key={key} className="inline-flex items-center gap-1.5">
              <Icon className={cn("size-3.5", cfg.textClass)} aria-hidden />
              <span className={cfg.textClass}>{cfg.label}</span>
              <span className="font-mono tabular-nums text-ink">{count}</span>
            </li>
          );
        })}
        {tally.pending > 0 && (
          <li className="font-mono tabular-nums text-ink-subtle">{tally.pending} pending</li>
        )}
      </ul>
    </div>
  );
}
