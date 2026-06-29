"use client";

import { useQuery } from "@tanstack/react-query";

import { getRunPanel } from "@/lib/api/runs";
import {
  concernAddressedStatus,
  fixStatusLabel,
  parseVerdict,
  recommendedFixStatus,
} from "@/lib/lineage/lineage";
import { JUDGE_ORDER } from "@/lib/sse/types";
import type { Verdict } from "@/lib/sse/types";
import { cn } from "@/lib/utils";
import { Skeleton } from "@/ui/skeleton";

import { ScoreDeltaBadge } from "../appeal/score-delta-badge";

function avgScore(verdicts: Verdict[]): number {
  return verdicts.reduce((sum, v) => sum + v.score, 0) / verdicts.length;
}

function VersionComparisonContent({
  version,
  parentRunId,
  currentVerdicts,
}: {
  version: number;
  parentRunId: string;
  currentVerdicts: Verdict[];
}) {
  const priorQuery = useQuery({
    queryKey: ["run", parentRunId, "panel"],
    queryFn: () => getRunPanel(parentRunId),
    retry: 1,
  });

  if (priorQuery.isLoading) {
    return (
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        {JUDGE_ORDER.map((id) => (
          <Skeleton key={id} className="h-32 w-full" />
        ))}
      </div>
    );
  }

  if (priorQuery.isError || !priorQuery.data) {
    return (
      <p className="font-sans text-sm text-ink-muted">
        Prior version unavailable — the parent run may have been removed or is not finished yet.
      </p>
    );
  }

  const priorVerdicts = priorQuery.data.verdicts
    .map(parseVerdict)
    .filter((v): v is Verdict => v !== null);

  if (priorVerdicts.length === 0) {
    return (
      <p className="font-sans text-sm text-ink-muted">
        Prior version has no verdict data to compare.
      </p>
    );
  }

  const priorAvg = avgScore(priorVerdicts);
  const currentAvg = avgScore(currentVerdicts);
  const avgDelta = currentAvg - priorAvg;
  const chainNote = version > 2 ? ` · ${version} versions in this chain` : "";

  return (
    <>
      <p className="max-w-prose font-sans text-sm text-ink-muted">
        Comparing v{version} to the prior version (consecutive versions of the same pitch
        {chainNote}).
      </p>

      <div className="mt-6 flex flex-wrap items-baseline gap-3">
        <span className="font-sans text-xs font-semibold uppercase tracking-widest text-ink-muted">
          Average score
        </span>
        <span className="font-mono text-2xl font-bold tabular-nums text-ink">
          {currentAvg.toFixed(1)}/10
        </span>
        {avgDelta !== 0 ? (
          <span
            className={cn(
              "font-mono text-sm font-bold tabular-nums",
              avgDelta > 0 ? "text-pass" : "text-fail",
            )}
          >
            {avgDelta > 0 ? "+" : ""}
            {avgDelta.toFixed(1)}
          </span>
        ) : (
          <span className="font-sans text-xs text-ink-muted">unchanged</span>
        )}
        <span className="font-sans text-sm text-ink-subtle">was {priorAvg.toFixed(1)}/10</span>
      </div>

      <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        {JUDGE_ORDER.map((judgeId) => {
          const current = currentVerdicts.find((v) => v.judge === judgeId);
          const prior = priorVerdicts.find((v) => v.judge === judgeId);
          if (!current || !prior) return null;
          const delta = current.score - prior.score;
          const status = concernAddressedStatus(prior, current);
          const fixStatus = recommendedFixStatus(prior, current);

          return (
            <div
              key={judgeId}
              className="border-2 border-rule-soft bg-card p-4 shadow-soft"
            >
              <p className="font-sans text-xs font-semibold uppercase tracking-widest text-ink-muted">
                {judgeId}
              </p>
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <span className="font-mono text-xl font-bold tabular-nums text-ink">
                  {current.score}/10
                </span>
                <ScoreDeltaBadge delta={delta} />
              </div>
              <p className="mt-1 font-sans text-xs text-ink-subtle">
                was {prior.score}/10 · {status}
              </p>
              <p className="mt-3 font-sans text-xs leading-relaxed text-ink-muted">
                <span className="font-semibold text-ink">Prior concern:</span>{" "}
                {prior.key_concern}
              </p>
              {prior.recommended_fix?.trim() && (
                <p className="mt-2 font-sans text-xs leading-relaxed text-ink-muted">
                  <span className="font-semibold text-ink">
                    Prior fix ({fixStatusLabel(fixStatus ?? "Concern shifted")}):
                  </span>{" "}
                  {prior.recommended_fix.trim()}
                </p>
              )}
            </div>
          );
        })}
      </div>
    </>
  );
}

export function VersionComparison({
  version,
  parentRunId,
  currentVerdicts,
  completed,
}: {
  version: number;
  parentRunId?: string | null;
  currentVerdicts: Verdict[];
  completed: boolean;
}) {
  if (!completed || currentVerdicts.length === 0) return null;

  if (!parentRunId && version === 1) {
    return (
      <section
        className="mt-10 rounded-md border border-rule-soft bg-paper-2 px-5 py-4"
        aria-label="Version comparison"
      >
        <p className="max-w-prose font-sans text-sm text-ink-muted">
          No prior version to compare yet. Use{" "}
          <span className="font-semibold text-ink">Refine this idea</span> after you update the
          pitch to see per-judge score deltas.
        </p>
      </section>
    );
  }

  if (parentRunId && version > 1) {
    return (
      <section className="mt-10" aria-labelledby="version-comparison-heading">
        <h2 id="version-comparison-heading" className="font-serif text-2xl font-semibold text-ink">
          Version comparison
        </h2>
        <div className="mt-6">
          <VersionComparisonContent
            version={version}
            parentRunId={parentRunId}
            currentVerdicts={currentVerdicts}
          />
        </div>
      </section>
    );
  }

  return null;
}

export function VersionBadge({
  version,
  parentRunId,
  className,
}: {
  version: number;
  parentRunId?: string | null;
  className?: string;
}) {
  return (
    <span className={cn("font-mono text-xs text-ink-subtle", className)}>
      v{version}
      {parentRunId ? " · refines prior run" : ""}
    </span>
  );
}
