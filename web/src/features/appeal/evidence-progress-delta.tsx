"use client";

import { ArrowRight, TrendingUp } from "lucide-react";

import {
  panelAverageScore,
  summarizeEvidenceOutcomes,
} from "@/lib/appeal/coaching";
import type { AppealResult } from "@/lib/sse/types";
import type { ConfidenceLevel } from "@/features/run/structured-synthesis";
import {
  parseDecisionVerdictProse,
} from "@/features/run/structured-synthesis";
import { cn } from "@/lib/utils";

import { ScoreDeltaBadge } from "./score-delta-badge";
import { EVIDENCE_COPY } from "../run/run-page-copy";

function parseConfidenceAfter(revisedSynthesis: string): ConfidenceLevel | null {
  const prose = parseDecisionVerdictProse(revisedSynthesis);
  return prose?.confidence ?? null;
}

function formatConfidence(level: ConfidenceLevel | null): string {
  if (!level) return "—";
  return level.charAt(0) + level.slice(1).toLowerCase();
}

export function deriveEvidenceProgress(
  appeal: AppealResult,
  confidenceBefore: ConfidenceLevel | null,
) {
  const originalVerdicts = Object.values(appeal.originalByJudge);
  const revisedVerdicts = Object.values(appeal.revisedByJudge);
  const scoreBefore = panelAverageScore(originalVerdicts);
  const scoreAfter = panelAverageScore(revisedVerdicts);
  const scoreDelta =
    scoreBefore != null && scoreAfter != null
      ? Math.round((scoreAfter - scoreBefore) * 10) / 10
      : null;

  return {
    scoreBefore,
    scoreAfter,
    scoreDelta,
    confidenceBefore,
    confidenceAfter: parseConfidenceAfter(appeal.revisedSynthesis),
    reasonSummary: summarizeEvidenceOutcomes(appeal.evidenceOutcomes ?? []),
  };
}

export function EvidenceProgressDelta({
  appeal,
  confidenceBefore,
  className,
}: {
  appeal: AppealResult;
  confidenceBefore: ConfidenceLevel | null;
  className?: string;
}) {
  const progress = deriveEvidenceProgress(appeal, confidenceBefore);

  return (
    <section
      className={cn("border-2 border-ink bg-card shadow-hard", className)}
      aria-labelledby="evidence-progress-heading"
    >
      <header className="flex items-start gap-3 border-b-2 border-ink px-5 py-4">
        <TrendingUp className="mt-0.5 size-5 shrink-0 text-heat-ink" aria-hidden />
        <div>
          <h3
            id="evidence-progress-heading"
            tabIndex={-1}
            className="font-sans text-sm font-semibold text-ink outline-none"
          >
            {EVIDENCE_COPY.progressTitle}
          </h3>
          <p className="mt-1 font-sans text-sm text-ink-muted">{progress.reasonSummary}</p>
        </div>
      </header>

      <dl className="grid gap-4 px-5 py-4 sm:grid-cols-2">
        <div>
          <dt className="font-sans text-xs font-semibold uppercase tracking-widest text-ink-muted">
            {EVIDENCE_COPY.panelScore}
          </dt>
          <dd className="mt-2 flex flex-wrap items-center gap-2 font-sans text-sm text-ink">
            <span className="font-mono font-semibold">
              {progress.scoreBefore != null ? progress.scoreBefore.toFixed(1) : "—"}
            </span>
            <ArrowRight className="size-4 text-ink-subtle" aria-hidden />
            <span className="font-mono font-semibold">
              {progress.scoreAfter != null ? progress.scoreAfter.toFixed(1) : "—"}
            </span>
            {progress.scoreDelta != null && progress.scoreDelta !== 0 && (
              <ScoreDeltaBadge delta={progress.scoreDelta} />
            )}
          </dd>
        </div>
        <div>
          <dt className="font-sans text-xs font-semibold uppercase tracking-widest text-ink-muted">
            {EVIDENCE_COPY.confidence}
          </dt>
          <dd className="mt-2 flex flex-wrap items-center gap-2 font-sans text-sm text-ink">
            <span>{formatConfidence(progress.confidenceBefore)}</span>
            <ArrowRight className="size-4 text-ink-subtle" aria-hidden />
            <span>{formatConfidence(progress.confidenceAfter)}</span>
          </dd>
        </div>
      </dl>
    </section>
  );
}
