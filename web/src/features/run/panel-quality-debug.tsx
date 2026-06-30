"use client";

import { AlertTriangle, CheckCircle2 } from "lucide-react";

import {
  assessLensUniqueness,
  lensQualitySummary,
  type LensUniquenessAssessment,
} from "@/lib/lens/lens-quality";
import type { Verdict } from "@/lib/sse/types";
import { cn } from "@/lib/utils";

export function PanelQualityDebugBadge({
  panelQuality,
  verdicts,
  className,
}: {
  panelQuality: LensUniquenessAssessment | null;
  verdicts: Verdict[];
  className?: string;
}) {
  // ponytail: panelQuality is frozen at run_completed; after appeal, verdicts may differ.
  const quality =
    panelQuality ??
    (verdicts.length >= 5 ? assessLensUniqueness(verdicts) : null);
  if (!quality || quality.lensLegacy) return null;

  const passed = quality.lensUniquenessPassed;
  const reasons = lensQualitySummary(quality);

  return (
    <aside
      className={cn(
        "mt-4 max-w-prose rounded-md border px-4 py-3 font-sans text-sm",
        passed
          ? "border-pass/40 bg-pass/5 text-ink-muted"
          : "border-amber-300 bg-amber-50 text-amber-950",
        className,
      )}
      aria-label="Maintainer lens quality debug"
    >
      <div className="flex items-start gap-2">
        {passed ? (
          <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-pass" aria-hidden />
        ) : (
          <AlertTriangle className="mt-0.5 size-4 shrink-0 text-amber-700" aria-hidden />
        )}
        <div>
          <p className="font-semibold text-ink">
            Lens quality (maintainer debug)
            <span className="ml-2 font-mono text-xs font-normal text-ink-subtle">
              {passed ? "pass" : "fail"}
            </span>
          </p>
          {reasons.length > 0 ? (
            <ul className="mt-2 list-disc space-y-1 pl-4 text-xs leading-relaxed">
              {reasons.map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>
          ) : (
            <p className="mt-1 text-xs">All five lenses have distinct proof bars.</p>
          )}
          <p className="mt-2 font-mono text-[10px] text-ink-subtle">
            generic_rate={quality.genericEvidenceRate}
          </p>
        </div>
      </div>
    </aside>
  );
}
