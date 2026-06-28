"use client";

import { JUDGE_ORDER } from "@/lib/sse/types";
import type { AppealResult } from "@/lib/sse/types";
import type { JudgeId } from "@/lib/sse/types";

import { JudgeColumn } from "../run/judge-column";
import { SynthesisBlock } from "../run/synthesis-block";

function scoreDelta(original: number, revised: number): number {
  return revised - original;
}

export function AppealResultView({ appeal }: { appeal: AppealResult }) {
  return (
    <section className="mt-12 border-t-2 border-rule-soft pt-10" aria-labelledby="appeal-result-heading">
      <h2 id="appeal-result-heading" className="font-serif text-2xl font-semibold text-ink">
        Appeal result
      </h2>
      <p className="mt-2 max-w-prose font-sans text-sm text-ink-muted">
        Revised verdicts after your rebuttal. Delta badges compare each judge&apos;s new score to
        the original panel.
      </p>

      <blockquote className="mt-6 border-l-2 border-heat pl-4 font-sans text-sm text-ink-muted">
        <span className="font-semibold text-ink">Your appeal:</span> {appeal.appealText}
      </blockquote>

      <div className="mt-8 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {JUDGE_ORDER.map((judgeId) => (
          <AppealJudgeCard
            key={judgeId}
            judgeId={judgeId}
            appeal={appeal}
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
}: {
  judgeId: JudgeId;
  appeal: AppealResult;
}) {
  const original = appeal.originalByJudge[judgeId];
  const revised = appeal.revisedByJudge[judgeId];
  if (!revised) return null;

  const delta = original ? scoreDelta(original.score, revised.score) : null;

  return (
    <JudgeColumn
      judgeId={judgeId}
      view={{ status: "revealed", verdict: revised }}
      animateStamp={false}
      scoreDelta={delta}
    />
  );
}
