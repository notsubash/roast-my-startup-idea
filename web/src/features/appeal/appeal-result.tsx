"use client";

import { JUDGE_ORDER } from "@/lib/sse/types";
import type { AppealJudgeOutcome, AppealResult } from "@/lib/sse/types";
import type { JudgeId } from "@/lib/sse/types";
import { Badge } from "@/ui/badge";

import { JudgeColumn } from "../run/judge-column";
import { SynthesisBlock } from "../run/synthesis-block";

function scoreDelta(original: number, revised: number): number {
  return revised - original;
}

function outcomeVariant(outcome: string): "pass" | "fail" | "conditional" | "default" {
  if (outcome === "Evidence met") return "pass";
  if (outcome === "Already passing") return "default";
  return "fail";
}

export function AppealResultView({ appeal }: { appeal: AppealResult }) {
  const outcomes = new Map(
    (appeal.evidenceOutcomes ?? []).map((item) => [item.judge, item]),
  );

  return (
    <section className="mt-12 border-t-2 border-rule-soft pt-10" aria-labelledby="appeal-result-heading">
      <h2 id="appeal-result-heading" className="font-serif text-2xl font-semibold text-ink">
        Appeal result
      </h2>
      <p className="mt-2 max-w-prose font-sans text-sm text-ink-muted">
        Revised verdicts after your rebuttal. Outcome badges show whether each judge&apos;s
        evidence ask was met.
      </p>

      <blockquote className="mt-6 border-l-2 border-heat pl-4 font-sans text-sm text-ink-muted">
        <span className="font-semibold text-ink">Your appeal:</span> {appeal.appealText}
      </blockquote>

      {appeal.targetJudges.length > 0 && (
        <p className="mt-4 font-sans text-sm text-ink-muted">
          <span className="font-semibold text-ink">You targeted:</span>{" "}
          {appeal.targetJudges.map((judge) => judge.toUpperCase()).join(", ")}
        </p>
      )}

      <div className="mt-8 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {JUDGE_ORDER.map((judgeId) => (
          <AppealJudgeCard
            key={judgeId}
            judgeId={judgeId}
            appeal={appeal}
            outcome={outcomes.get(judgeId)}
          />
        ))}
      </div>

      <div className="mt-10">
        <h3 className="font-sans text-xs font-semibold uppercase tracking-widest text-ink-muted">
          Revised synthesis
        </h3>
        <div className="mt-3">
          <SynthesisBlock content={appeal.revisedSynthesis} variant="appeal" />
        </div>
      </div>
    </section>
  );
}

function AppealJudgeCard({
  judgeId,
  appeal,
  outcome,
}: {
  judgeId: JudgeId;
  appeal: AppealResult;
  outcome?: AppealJudgeOutcome;
}) {
  const original = appeal.originalByJudge[judgeId];
  const revised = appeal.revisedByJudge[judgeId];
  if (!revised) return null;

  const delta = original ? scoreDelta(original.score, revised.score) : null;

  return (
    <div className="space-y-3">
      {outcome && (
        <div className="space-y-2 px-1">
          <Badge variant={outcomeVariant(outcome.outcome)} className="font-sans text-xs">
            {outcome.outcome}
          </Badge>
          {outcome.targeted && (
            <p className="font-sans text-xs text-ink-muted">You targeted this judge</p>
          )}
          <p className="font-sans text-xs text-ink-muted">
            <span className="font-semibold text-ink">Evidence ask:</span> {outcome.evidenceAsk}
          </p>
        </div>
      )}
      <JudgeColumn
        judgeId={judgeId}
        view={{ status: "revealed", verdict: revised }}
        animateStamp={false}
        scoreDelta={delta}
      />
    </div>
  );
}
