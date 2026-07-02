"use client";

import { useQuery } from "@tanstack/react-query";

import { getRunPanel, runPanelQueryKey } from "@/lib/api/runs";
import { computeVersionDiff } from "@/lib/lineage/version-diff";
import {
  concernAddressedStatus,
  fixStatusLabel,
  parseVerdict,
  recommendedFixStatus,
} from "@/lib/lineage/lineage";
import { JUDGE_META } from "@/lib/sse/judges";
import { JUDGE_ORDER } from "@/lib/sse/types";
import type { Verdict } from "@/lib/sse/types";
import { cn } from "@/lib/utils";
import { Skeleton } from "@/ui/skeleton";

import { ScoreDeltaBadge } from "../appeal/score-delta-badge";
import { AnimatedScore } from "@/ui/animated-score";
import { ConfidenceBars } from "./confidence-bars";
import { VERSION_COPY } from "../run/run-page-copy";

function DiffList({
  title,
  items,
  variant,
}: {
  title: string;
  items: { judge: string; text: string }[];
  variant: "removed" | "added" | "evidence";
}) {
  if (items.length === 0) return null;

  const marker =
    variant === "removed" ? "−" : variant === "added" ? "+" : "•";
  const srPrefix =
    variant === "removed" ? "Removed" : variant === "added" ? "Added" : "Evidence";

  return (
    <div>
      <h3 className="font-sans text-xs font-semibold uppercase tracking-widest text-ink-muted">
        {title}
      </h3>
      <ul className="mt-2 space-y-2">
        {items.map((item) => (
          <li
            key={`${variant}-${item.judge}`}
            className="border-l-2 border-rule-soft pl-3 font-sans text-sm leading-relaxed text-ink"
          >
            <span className="sr-only">{srPrefix}: </span>
            <span className="font-mono text-xs text-ink-subtle" aria-hidden>
              {marker}{" "}
            </span>
            <span className="font-semibold text-ink-muted">
              {JUDGE_META[item.judge as keyof typeof JUDGE_META]?.lensTag ?? item.judge}:
            </span>{" "}
            {item.text}
          </li>
        ))}
      </ul>
    </div>
  );
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
    queryKey: runPanelQueryKey(parentRunId),
    queryFn: () => getRunPanel(parentRunId),
    retry: 1,
  });

  if (priorQuery.isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-4 w-2/3" />
        <Skeleton className="h-24 w-full" />
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
    .filter((verdict): verdict is Verdict => verdict !== null);

  if (priorVerdicts.length === 0) {
    return (
      <p className="font-sans text-sm text-ink-muted">
        Prior version has no verdict data to compare.
      </p>
    );
  }

  const diff = computeVersionDiff(priorVerdicts, currentVerdicts);
  if (!diff) {
    return (
      <p className="font-sans text-sm text-ink-muted">
        Could not compute a version diff for this run.
      </p>
    );
  }

  const chainNote =
    version > 2 ? ` (${version} versions in this chain)` : "";

  const hasDiffItems =
    diff.removed.length > 0 ||
    diff.added.length > 0 ||
    diff.changed.length > 0 ||
    diff.evidenceAdded.length > 0;

  return (
    <>
      <p className="max-w-prose font-sans text-sm text-ink-muted">
        {VERSION_COPY.comparisonLead(version, chainNote)}
      </p>

      <div className="mt-6 rounded-md border border-rule-soft bg-paper-2 px-5 py-4">
        <div className="flex flex-wrap items-baseline gap-3">
          <span className="font-sans text-xs font-semibold uppercase tracking-widest text-ink-muted">
            Panel score
          </span>
          <span className="font-mono text-2xl font-bold tabular-nums text-ink">
            <AnimatedScore
              value={diff.scoreAfter}
              decimals={1}
              suffix="/10"
              animateFrom={diff.scoreBefore}
            />
          </span>
          {diff.scoreDelta !== 0 ? (
            <ScoreDeltaBadge delta={diff.scoreDelta} animate />
          ) : (
            <span className="font-sans text-xs text-ink-muted">unchanged</span>
          )}
          <span className="font-sans text-sm text-ink-subtle">
            was <AnimatedScore value={diff.scoreBefore} decimals={1} suffix="/10" className="font-mono" />
          </span>
        </div>
        <p className="mt-3 font-sans text-sm text-ink-muted">
          <span className="font-semibold text-ink">{VERSION_COPY.scoreDeltaReason}:</span>{" "}
          {diff.reasonSummary}
        </p>
      </div>

      {hasDiffItems ? (
        <div className="mt-8 grid gap-6 lg:grid-cols-2">
          <DiffList title={VERSION_COPY.removed} items={diff.removed} variant="removed" />
          <DiffList title={VERSION_COPY.added} items={diff.added} variant="added" />
          {diff.changed.length > 0 && (
            <div className="lg:col-span-2">
              <h3 className="font-sans text-xs font-semibold uppercase tracking-widest text-ink-muted">
                {VERSION_COPY.changed}
              </h3>
              <ul className="mt-2 space-y-3">
                {diff.changed.map((item) => (
                  <li
                    key={`changed-${item.judge}`}
                    className="border-l-2 border-conditional pl-3 font-sans text-sm leading-relaxed text-ink"
                  >
                    <span className="font-semibold text-ink-muted">
                      {JUDGE_META[item.judge].lensTag}:
                    </span>{" "}
                    <span className="text-ink-subtle line-through">{item.before}</span>
                    <span className="mx-1 text-ink-muted" aria-hidden>
                      →
                    </span>
                    <span>{item.after}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          <DiffList
            title={VERSION_COPY.evidenceAdded}
            items={diff.evidenceAdded}
            variant="evidence"
          />
        </div>
      ) : (
        <p className="mt-6 font-sans text-sm text-ink-muted">
          Judge concerns are unchanged between versions — only scores moved.
        </p>
      )}

      <ConfidenceBars verdicts={currentVerdicts} className="mt-8" />

      <details className="group mt-8 border-t border-rule-soft pt-6">
        <summary className="cursor-pointer font-sans text-sm font-semibold text-ink-muted hover:text-ink">
          Per-judge score breakdown
        </summary>
        <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          {JUDGE_ORDER.map((judgeId) => {
            const current = currentVerdicts.find((verdict) => verdict.judge === judgeId);
            const prior = priorVerdicts.find((verdict) => verdict.judge === judgeId);
            if (!current || !prior) return null;
            const delta = current.score - prior.score;
            const status = concernAddressedStatus(prior, current);
            const fixStatus = recommendedFixStatus(prior, current);

            return (
              <div
                key={judgeId}
                className="border border-rule-soft bg-card p-4 shadow-soft"
              >
                <p className="font-sans text-xs font-semibold uppercase tracking-widest text-ink-muted">
                  {JUDGE_META[judgeId].lensTag}
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
                {prior.recommended_fix?.trim() && (
                  <p className="mt-3 font-sans text-xs leading-relaxed text-ink-muted">
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
      </details>
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
          {VERSION_COPY.noPriorVersion}
        </p>
        <ConfidenceBars verdicts={currentVerdicts} className="mt-6" />
      </section>
    );
  }

  if (parentRunId && version > 1) {
    return (
      <section className="mt-10" aria-labelledby="version-comparison-heading">
        <h2 id="version-comparison-heading" className="font-sans text-2xl font-semibold text-ink">
          {VERSION_COPY.comparisonTitle}
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

  return (
    <section className="mt-10" aria-label="Confidence">
      <ConfidenceBars verdicts={currentVerdicts} />
    </section>
  );
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
