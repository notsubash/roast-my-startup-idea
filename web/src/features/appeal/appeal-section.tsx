"use client";

import { useCallback, useEffect, useState } from "react";

import type { AppealResponse } from "@/lib/api/types-helpers";
import type { AppealResult, JudgeId, Verdict } from "@/lib/sse/types";
import { JUDGE_ORDER } from "@/lib/sse/types";

import { AppealForm } from "./appeal-form";
import { AppealResultView } from "./appeal-result";

function toVerdictMap(panel: AppealResponse["revised_panel"]): Record<JudgeId, Verdict> {
  const map = {} as Record<JudgeId, Verdict>;
  const verdicts = (panel as { verdicts?: unknown[] }).verdicts;
  if (!Array.isArray(verdicts)) return map;
  for (const item of verdicts) {
    if (
      item &&
      typeof item === "object" &&
      typeof (item as Verdict).judge === "string" &&
      (JUDGE_ORDER as readonly string[]).includes((item as Verdict).judge)
    ) {
      map[(item as Verdict).judge] = item as Verdict;
    }
  }
  return map;
}

function responseToAppeal(result: AppealResponse): AppealResult {
  return {
    appealText: result.appeal_text,
    originalByJudge: toVerdictMap(result.original_panel),
    revisedByJudge: toVerdictMap(result.revised_panel),
    revisedSynthesis: result.revised_synthesis,
  };
}

export function AppealSection({
  runId,
  completed,
  streamAppeal,
}: {
  runId: string;
  completed: boolean;
  streamAppeal: AppealResult | null;
}) {
  const [localAppeal, setLocalAppeal] = useState<AppealResult | null>(streamAppeal);

  useEffect(() => {
    if (streamAppeal) setLocalAppeal(streamAppeal);
  }, [streamAppeal]);

  const onSuccess = useCallback((result: AppealResponse) => {
    setLocalAppeal(responseToAppeal(result));
  }, []);

  if (!completed) return null;

  if (localAppeal) {
    return <AppealResultView appeal={localAppeal} />;
  }

  return (
    <section className="mt-12 border-t-2 border-rule-soft pt-10" aria-labelledby="appeal-form-heading">
      <AppealForm runId={runId} onSuccess={onSuccess} />
    </section>
  );
}
