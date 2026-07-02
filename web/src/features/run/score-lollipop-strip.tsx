import { JUDGE_META } from "@/lib/sse/judges";
import { JUDGE_ORDER } from "@/lib/sse/types";
import type { JudgeView } from "@/lib/sse/types";
import { cn } from "@/lib/utils";

import { VERDICT_SEGMENT } from "./verdict-stats";

const JUDGE_DOT_CLASS: Record<(typeof JUDGE_ORDER)[number], string> = {
  vc: "bg-judge-vc",
  engineer: "bg-judge-engineer",
  pm: "bg-judge-pm",
  customer: "bg-judge-customer",
  competitor: "bg-judge-competitor",
};

export function ScoreLollipopStrip({
  judges,
  className,
}: {
  judges: Record<(typeof JUDGE_ORDER)[number], JudgeView>;
  className?: string;
}) {
  return (
    <div className={cn("border border-rule-soft bg-card p-4", className)}>
      <div className="mb-4 flex justify-between font-mono text-[10px] text-ink-subtle">
        {[0, 2, 4, 6, 8, 10].map((tick) => (
          <span key={tick}>{tick}</span>
        ))}
      </div>

      <ol className="space-y-4" aria-label="Judge score report card">
        {JUDGE_ORDER.map((id) => {
          const meta = JUDGE_META[id];
          const verdict = judges[id].verdict;
          const score = verdict?.score ?? null;
          const label = verdict?.verdict;
          const pct = score !== null ? (score / 10) * 100 : null;

          return (
            <li key={id} className="grid grid-cols-[7rem_1fr_auto] items-center gap-3 sm:grid-cols-[8rem_1fr_auto]">
              <span className={cn("font-sans text-xs font-bold", meta.accentClass.split(" ")[0])}>
                {meta.name.replace(/^The /, "")}
              </span>

              <div
                className="relative h-3 border border-rule-soft bg-paper-2"
                role="img"
                aria-label={
                  score !== null
                    ? `${meta.name} scored ${score} out of 10${label ? `, ${label}` : ""}`
                    : `${meta.name}, awaiting verdict`
                }
              >
                <div className="absolute inset-y-0 left-0 w-px bg-rule-soft" style={{ left: "20%" }} aria-hidden />
                <div className="absolute inset-y-0 left-0 w-px bg-rule-soft" style={{ left: "40%" }} aria-hidden />
                <div className="absolute inset-y-0 left-0 w-px bg-rule-soft" style={{ left: "60%" }} aria-hidden />
                <div className="absolute inset-y-0 left-0 w-px bg-rule-soft" style={{ left: "80%" }} aria-hidden />

                {pct !== null && (
                  <>
                    <div
                      className="absolute inset-y-0 left-0 bg-heat/15"
                      style={{ width: `${pct}%` }}
                      aria-hidden
                    />
                    <div
                      className={cn(
                        "absolute top-1/2 size-4 -translate-x-1/2 -translate-y-1/2 border border-rule-soft",
                        JUDGE_DOT_CLASS[id],
                      )}
                      style={{ left: `${pct}%` }}
                      aria-hidden
                    />
                  </>
                )}
              </div>

              <div className="flex min-w-[4.5rem] flex-col items-end gap-0.5">
                <span className="font-mono text-sm font-bold tabular-nums text-ink">
                  {score !== null ? `${score}/10` : "—"}
                </span>
                {label && (
                  <span
                    className={cn(
                      "font-sans text-[10px] font-bold uppercase tracking-wide",
                      VERDICT_SEGMENT[label].textClass,
                    )}
                  >
                    {label}
                  </span>
                )}
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
