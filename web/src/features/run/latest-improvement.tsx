"use client";

import { useQuery } from "@tanstack/react-query";
import { TrendingUp } from "lucide-react";

import { ScoreDeltaBadge } from "@/features/appeal/score-delta-badge";
import { getRunPanel, runPanelQueryKey } from "@/lib/api/runs";
import {
  deriveLatestImprovementFromVersionDiff,
  type LatestImprovement,
} from "@/lib/lineage/latest-improvement";
import { computeVersionDiff } from "@/lib/lineage/version-diff";
import { parseVerdict } from "@/lib/lineage/lineage";
import type { Verdict } from "@/lib/sse/types";
import { cn } from "@/lib/utils";
import { AnimatedScore } from "@/ui/animated-score";

import { RUN_PAGE_COPY } from "./run-page-copy";

function LatestImprovementCard({
  improvement,
  className,
}: {
  improvement: LatestImprovement;
  className?: string;
}) {
  const showScore =
    improvement.scoreBefore != null && improvement.scoreAfter != null;

  return (
    <section
      className={cn(
        "animate-fade-rise border border-rule-soft bg-paper-2 px-4 py-3 sm:px-5 sm:py-4",
        className,
      )}
      aria-labelledby="latest-improvement-heading"
    >
      <div className="flex items-start gap-3">
        <TrendingUp className="mt-0.5 size-4 shrink-0 text-ink-muted" aria-hidden />
        <div className="min-w-0 flex-1">
          <h2
            id="latest-improvement-heading"
            className="font-sans text-xs font-semibold uppercase tracking-widest text-ink-muted"
          >
            {RUN_PAGE_COPY.latestImprovement}
          </h2>
          {showScore && (
            <p className="mt-2 flex flex-wrap items-center gap-2 font-sans text-sm text-ink">
              <AnimatedScore
                value={improvement.scoreBefore}
                className="font-mono font-semibold"
              />
              <span className="text-ink-subtle" aria-hidden>
                →
              </span>
              <AnimatedScore
                value={improvement.scoreAfter}
                animateFrom={improvement.scoreBefore}
                className="font-mono font-semibold"
              />
              <span className="font-sans text-xs text-ink-muted">panel score</span>
              {improvement.scoreDelta != null && improvement.scoreDelta !== 0 && (
                <ScoreDeltaBadge delta={improvement.scoreDelta} animate />
              )}
            </p>
          )}
          <p className="mt-1.5 font-sans text-sm leading-relaxed text-ink-muted">
            {improvement.summary}
          </p>
        </div>
      </div>
    </section>
  );
}

function VersionLatestImprovement({
  parentRunId,
  currentVerdicts,
  className,
}: {
  parentRunId: string;
  currentVerdicts: Verdict[];
  className?: string;
}) {
  const priorQuery = useQuery({
    queryKey: runPanelQueryKey(parentRunId),
    queryFn: () => getRunPanel(parentRunId),
    retry: 1,
  });

  if (priorQuery.isLoading || priorQuery.isError || !priorQuery.data) return null;

  const priorVerdicts = priorQuery.data.verdicts
    .map(parseVerdict)
    .filter((verdict): verdict is Verdict => verdict !== null);

  if (priorVerdicts.length === 0) return null;

  const diff = computeVersionDiff(priorVerdicts, currentVerdicts);
  if (!diff) return null;

  const improvement = deriveLatestImprovementFromVersionDiff(diff);
  if (!improvement) return null;

  return <LatestImprovementCard improvement={improvement} className={className} />;
}

/** Version-to-version progress teaser. Evidence progress lives in the appeal fold. */
export function LatestImprovement({
  completed,
  version,
  parentRunId,
  currentVerdicts,
  className,
}: {
  completed: boolean;
  version: number;
  parentRunId?: string | null;
  currentVerdicts: Verdict[];
  className?: string;
}) {
  if (!completed || currentVerdicts.length === 0) return null;
  if (!parentRunId || version <= 1) return null;

  return (
    <VersionLatestImprovement
      parentRunId={parentRunId}
      currentVerdicts={currentVerdicts}
      className={className}
    />
  );
}
