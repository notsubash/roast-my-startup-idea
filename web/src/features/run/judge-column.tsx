"use client";

import { AlertCircle } from "lucide-react";

import { JUDGE_META } from "@/lib/sse/judges";
import type { JudgeView } from "@/lib/sse/types";
import type { JudgeId } from "@/lib/sse/types";
import { cn } from "@/lib/utils";
import { Skeleton } from "@/ui/skeleton";

import { ScoreDeltaBadge } from "../appeal/score-delta-badge";

import { VerdictStamp } from "./verdict-stamp";

export function JudgeColumnSkeleton() {
  return (
    <article className="flex flex-col border-2 border-rule-soft bg-card p-4">
      <Skeleton className="h-4 w-24" />
      <Skeleton className="mt-2 h-3 w-full" />
      <Skeleton className="mt-6 h-16 w-full" />
      <Skeleton className="mt-4 h-20 w-full" />
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
}: {
  judgeId: JudgeId;
  view: JudgeView;
  animateStamp?: boolean;
  /** When set, shows a delta badge beside the score (appeal or post-debate re-vote). */
  scoreDelta?: number | null;
  /** One-line justification when a post-debate score moved. */
  scoreChangeReason?: string | null;
}) {
  const meta = JUDGE_META[judgeId];

  if (view.status === "failed") {
    return (
      <article
        className="flex flex-col border-2 border-rule-soft bg-paper-2 p-4"
        aria-label={`${meta.name} — unavailable`}
      >
        <header>
          <h3 className={cn("font-sans text-sm font-bold", meta.accentClass.split(" ")[0])}>
            {meta.name}
          </h3>
          <p className="mt-1 font-sans text-xs text-ink-muted">{meta.role}</p>
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
        aria-label={`${meta.name}${view.status === "thinking" ? " — reading your pitch" : ""}`}
      >
        <header>
          <h3 className={cn("font-sans text-sm font-bold", meta.accentClass.split(" ")[0])}>
            {meta.name}
          </h3>
          <p className="mt-1 font-sans text-xs text-ink-muted">{meta.role}</p>
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
  if (!verdict) return <JudgeColumnSkeleton />;

  return (
    <article
      className="flex flex-col border-2 border-ink bg-card p-4 shadow-soft"
      aria-label={`${meta.name} — ${verdict.verdict}`}
    >
      <header className="flex items-start justify-between gap-3">
        <div>
          <h3 className={cn("font-sans text-sm font-bold", meta.accentClass.split(" ")[0])}>
            {meta.name}
          </h3>
          <p className="mt-1 font-sans text-xs text-ink-muted">{meta.role}</p>
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

      {scoreChangeReason && (
        <p className="mt-3 font-sans text-sm text-ink-muted">
          <span className="font-semibold text-ink">Why it moved:</span> {scoreChangeReason}
        </p>
      )}

      <div className="mt-6">
        <VerdictStamp verdict={verdict.verdict} animate={animateStamp} />
      </div>
    </article>
  );
}
