"use client";

import { AlertCircle } from "lucide-react";

import { JUDGE_META } from "@/lib/sse/judges";
import type { JudgeView } from "@/lib/sse/types";
import type { JudgeId } from "@/lib/sse/types";
import { cn } from "@/lib/utils";
import { Skeleton } from "@/ui/skeleton";

import { ScoreDeltaBadge } from "../appeal/score-delta-badge";

import { VerdictStamp } from "./verdict-stamp";

function JudgeLensTag({ meta }: { meta: (typeof JUDGE_META)[JudgeId] }) {
  return (
    <span
      className={cn(
        "mt-2 inline-block border px-2 py-0.5 font-sans text-[10px] font-semibold uppercase tracking-wide",
        meta.accentClass,
      )}
      title={meta.lensTag}
    >
      {meta.lensTag}
    </span>
  );
}

export { JudgeLensTag };

export function JudgeColumnSkeleton({ judgeId }: { judgeId?: JudgeId } = {}) {
  const meta = judgeId ? JUDGE_META[judgeId] : null;

  return (
    <article
      className="flex flex-col border-2 border-rule-soft bg-card p-4"
      aria-busy="true"
      aria-label={meta ? `${meta.name} — ${meta.lensTag} — loading` : "Judge verdict loading"}
    >
      {meta ? (
        <header>
          <h3 className={cn("font-sans text-sm font-bold", meta.accentClass.split(" ")[0])}>
            {meta.name}
          </h3>
          <p className="mt-1 font-sans text-xs text-ink-muted">{meta.role}</p>
          <JudgeLensTag meta={meta} />
        </header>
      ) : (
        <>
          <Skeleton className="h-4 w-24" />
          <Skeleton className="mt-2 h-3 w-full" />
        </>
      )}
      <Skeleton className="mt-6 h-16 w-full" />
      <Skeleton className="mt-4 h-20 w-full" />
      <Skeleton className="mt-3 h-12 w-full" />
      <Skeleton className="mt-4 h-10 w-28" />
    </article>
  );
}

export function JudgeColumn({
  judgeId,
  view,
  animateStamp = false,
  scoreDelta,
  scoreChangeReason,
  evidenceAskCollides = false,
}: {
  judgeId: JudgeId;
  view: JudgeView;
  animateStamp?: boolean;
  /** When set, shows a delta badge beside the score (appeal or post-debate re-vote). */
  scoreDelta?: number | null;
  /** One-line justification when a post-debate score moved. */
  scoreChangeReason?: string | null;
  /** Normalized evidence ask matches another judge on the panel. */
  evidenceAskCollides?: boolean;
}) {
  const meta = JUDGE_META[judgeId];

  if (view.status === "failed") {
    return (
      <article
        className="flex flex-col border-2 border-rule-soft bg-paper-2 p-4"
        aria-label={`${meta.name} — ${meta.lensTag} — unavailable`}
      >
        <header>
          <h3 className={cn("font-sans text-sm font-bold", meta.accentClass.split(" ")[0])}>
            {meta.name}
          </h3>
          <p className="mt-1 font-sans text-xs text-ink-muted">{meta.role}</p>
          <JudgeLensTag meta={meta} />
        </header>
        <div className="mt-6 flex items-center gap-2 font-sans text-sm text-ink-muted">
          <AlertCircle className="size-4 shrink-0" aria-hidden />
          Verdict unavailable — the run ended before this judge finished.
        </div>
      </article>
    );
  }

  if (view.status === "idle" || view.status === "thinking") {
    return (
      <article
        className="flex flex-col border-2 border-ink bg-card p-4 shadow-soft"
        aria-busy={view.status === "thinking"}
        aria-label={`${meta.name} — ${meta.lensTag}${view.status === "thinking" ? " — reading your pitch" : ""}`}
      >
        <header>
          <h3 className={cn("font-sans text-sm font-bold", meta.accentClass.split(" ")[0])}>
            {meta.name}
          </h3>
          <p className="mt-1 font-sans text-xs text-ink-muted">{meta.role}</p>
          <JudgeLensTag meta={meta} />
        </header>
        {view.status === "thinking" ? (
          <p className="mt-8 animate-pulse font-sans text-sm text-ink-muted">
            Reading your pitch…
          </p>
        ) : (
          <p className="mt-8 font-sans text-sm text-ink-subtle">Waiting for the panel…</p>
        )}
      </article>
    );
  }

  const { verdict } = view;
  if (!verdict) return <JudgeColumnSkeleton judgeId={judgeId} />;

  const evidenceAsk = verdict.evidence_to_change_verdict?.trim();
  const scoreChangeReasonTrimmed = scoreChangeReason?.trim();
  const showScoreChangeReason =
    scoreChangeReasonTrimmed &&
    scoreDelta != null &&
    scoreDelta !== 0 &&
    scoreChangeReasonTrimmed !== evidenceAsk;

  return (
    <article
      className="flex flex-col border-2 border-ink bg-card p-4 shadow-soft"
      aria-label={`${meta.name} — ${meta.lensTag} — ${verdict.verdict}`}
    >
      <header className="flex items-start justify-between gap-3">
        <div>
          <h3 className={cn("font-sans text-sm font-bold", meta.accentClass.split(" ")[0])}>
            {meta.name}
          </h3>
          <p className="mt-1 font-sans text-xs text-ink-muted">{meta.role}</p>
          <JudgeLensTag meta={meta} />
        </div>
        <div className="flex flex-col items-end gap-1">
          {scoreDelta != null && <ScoreDeltaBadge delta={scoreDelta} />}
          <p className="font-mono text-2xl font-bold tabular-nums text-ink">
            {verdict.score}
            <span className="text-sm font-normal text-ink-muted">/10</span>
          </p>
        </div>
      </header>

      <blockquote className="mt-6 border-l-2 border-ink pl-4 font-serif text-base italic leading-relaxed text-ink">
        {verdict.roast}
      </blockquote>

      <p className="mt-4 font-sans text-sm text-ink-muted">
        <span className="font-semibold text-ink">Key concern:</span> {verdict.key_concern}
      </p>

      {verdict.recommended_fix && (
        <p className="mt-3 font-sans text-sm text-ink-muted">
          <span className="font-semibold text-ink">Recommended fix:</span> {verdict.recommended_fix}
        </p>
      )}

      <p className="mt-3 font-sans text-sm text-ink-muted">
        <span className="font-semibold text-ink">Evidence ask:</span>{" "}
        {evidenceAsk || (
          <span className="text-ink-subtle italic">No explicit ask provided</span>
        )}
      </p>
      {evidenceAskCollides && (
        <p className="mt-1 font-sans text-xs text-ink-subtle" role="status">
          Same bar as another judge — use lens-specific proof when appealing.
        </p>
      )}

      {showScoreChangeReason && (
        <p className="mt-3 font-sans text-sm text-ink-muted">
          <span className="font-semibold text-ink">Why it moved:</span> {scoreChangeReasonTrimmed}
        </p>
      )}

      <div className="mt-6">
        <VerdictStamp verdict={verdict.verdict} animate={animateStamp} />
      </div>
    </article>
  );
}
