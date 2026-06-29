"use client";

import {
  assessAppealCoaching,
  type AppealHintQuality,
} from "@/lib/appeal/coaching";
import { JUDGE_META } from "@/lib/sse/judges";
import type { JudgeId, Verdict } from "@/lib/sse/types";
import { cn } from "@/lib/utils";
import { Label } from "@/ui/label";

const VERDICT_TONE: Record<Verdict["verdict"], string> = {
  PASS: "text-pass",
  FAIL: "text-fail",
  CONDITIONAL: "text-warn",
};

const QUALITY_NOTE: Record<Exclude<AppealHintQuality, "precise">, string> = {
  derived: "Inferred from this judge's concern",
  generic: "Generic ask — treat as directional",
  duplicate: "Same bar as another judge",
};

export function AppealCoaching({
  baselineVerdicts,
  targetJudges,
  onTargetChange,
  disabled,
}: {
  baselineVerdicts: Verdict[];
  targetJudges: JudgeId[];
  onTargetChange: (judges: JudgeId[]) => void;
  disabled?: boolean;
}) {
  const coaching = assessAppealCoaching(baselineVerdicts);
  const targets = new Set(targetJudges);

  return (
    <div className="mt-6 space-y-3">
      <div>
        <h3 className="font-sans text-sm font-semibold text-ink">
          What each judge needs to hear
        </h3>
        <p className="mt-1 font-sans text-sm text-ink-muted">
          These are starting points from the panel, not a checklist to game. Check
          the judges you are directly addressing, and prioritize FAIL and
          CONDITIONAL first.
        </p>
      </div>

      {coaching.degraded && (
        <p
          className="border border-warn/40 bg-warn/5 px-4 py-3 font-sans text-sm text-ink-muted"
          role="status"
        >
          <span className="font-semibold text-ink">Limited coaching quality.</span>{" "}
          {coaching.reasons.join(" ")}
        </p>
      )}

      <ul className="space-y-3">
        {coaching.items.map((item) => {
          const meta = JUDGE_META[item.judge];
          const checked = targets.has(item.judge);
          const inputId = `appeal-target-${item.judge}`;
          const qualityNote =
            item.quality !== "precise" ? QUALITY_NOTE[item.quality] : null;

          return (
            <li
              key={item.judge}
              className={cn(
                "flex gap-3 border border-rule-soft bg-paper-2 p-4",
                item.quality !== "precise" && "opacity-90",
              )}
            >
              <input
                id={inputId}
                type="checkbox"
                checked={checked}
                disabled={disabled}
                onChange={(event) => {
                  const next = new Set(targetJudges);
                  if (event.target.checked) next.add(item.judge);
                  else next.delete(item.judge);
                  onTargetChange([...next]);
                }}
                className="mt-1 size-4 shrink-0 accent-ink"
                aria-describedby={`${inputId}-hint`}
              />
              <div className="min-w-0 flex-1">
                <Label
                  htmlFor={inputId}
                  className={cn(
                    "font-sans text-sm font-semibold",
                    meta.accentClass.split(" ")[0],
                  )}
                >
                  {meta.name}
                  <span
                    className={cn(
                      "ml-2 font-mono text-xs",
                      VERDICT_TONE[item.verdict],
                    )}
                  >
                    {item.verdict} · {item.score}/10
                  </span>
                </Label>
                <p id={`${inputId}-hint`} className="mt-1 font-sans text-sm text-ink-muted">
                  {item.hint}
                </p>
                {qualityNote && (
                  <p className="mt-1 font-sans text-xs text-ink-subtle">{qualityNote}</p>
                )}
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
