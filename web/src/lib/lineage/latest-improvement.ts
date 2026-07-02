import {
  panelAverageScore,
  summarizeEvidenceOutcomes,
} from "../appeal/coaching.ts";
import type { AppealResult } from "../sse/types.ts";
import type { VersionDiff } from "./version-diff.ts";

export type LatestImprovementKind = "version" | "evidence";

export type LatestImprovement = {
  kind: LatestImprovementKind;
  scoreBefore: number | null;
  scoreAfter: number | null;
  scoreDelta: number | null;
  summary: string;
};

export function deriveEvidenceProgress(appeal: AppealResult) {
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
    reasonSummary: summarizeEvidenceOutcomes(appeal.evidenceOutcomes ?? []),
  };
}

export function deriveLatestImprovementFromVersionDiff(
  diff: VersionDiff,
): LatestImprovement | null {
  const hasMovement =
    diff.scoreDelta !== 0 ||
    diff.removed.length > 0 ||
    diff.added.length > 0 ||
    diff.changed.length > 0 ||
    diff.evidenceAdded.length > 0;

  if (!hasMovement) return null;

  return {
    kind: "version",
    scoreBefore: diff.scoreBefore,
    scoreAfter: diff.scoreAfter,
    scoreDelta: diff.scoreDelta,
    summary: diff.reasonSummary,
  };
}

export function hasAppealMovement(appeal: AppealResult): boolean {
  const progress = deriveEvidenceProgress(appeal);
  if (progress.scoreDelta != null && progress.scoreDelta !== 0) return true;

  const outcomes = appeal.evidenceOutcomes ?? [];
  if (outcomes.some((item) => item.targeted && item.outcome === "Evidence met")) {
    return true;
  }
  return outcomes.some((item) => item.scoreDelta > 0);
}

export function deriveLatestImprovementFromAppeal(
  appeal: AppealResult,
): LatestImprovement | null {
  if (!hasAppealMovement(appeal)) return null;

  const progress = deriveEvidenceProgress(appeal);
  return {
    kind: "evidence",
    scoreBefore: progress.scoreBefore,
    scoreAfter: progress.scoreAfter,
    scoreDelta: progress.scoreDelta,
    summary: progress.reasonSummary,
  };
}
