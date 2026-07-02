import { panelAverageScore } from "../appeal/coaching.ts";
import { concernAddressedStatus } from "./lineage.ts";
import { JUDGE_ORDER } from "../sse/types.ts";
import type { JudgeId, Verdict } from "../sse/types.ts";

export type VersionDiffItem = {
  judge: JudgeId;
  text: string;
};

export type VersionDiffChange = {
  judge: JudgeId;
  before: string;
  after: string;
};

export type VersionDiff = {
  scoreBefore: number;
  scoreAfter: number;
  scoreDelta: number;
  reasonSummary: string;
  removed: VersionDiffItem[];
  added: VersionDiffItem[];
  changed: VersionDiffChange[];
  evidenceAdded: VersionDiffItem[];
};

function normalizeText(text: string): string {
  return text.trim().toLowerCase();
}

function summarizeVersionDiff(
  scoreDelta: number,
  removed: VersionDiffItem[],
  added: VersionDiffItem[],
  changed: VersionDiffChange[],
): string {
  if (scoreDelta > 0.3) {
    if (removed.length > 0) {
      return `${removed.length} prior concern${removed.length === 1 ? "" : "s"} addressed — panel score rose.`;
    }
    return `Panel score improved by ${scoreDelta.toFixed(1)}.`;
  }
  if (scoreDelta < -0.3) {
    if (added.length > 0) {
      return `${added.length} new concern${added.length === 1 ? "" : "s"} surfaced.`;
    }
    return `Panel score dropped by ${Math.abs(scoreDelta).toFixed(1)}.`;
  }
  if (changed.length > 0) {
    return `${changed.length} concern${changed.length === 1 ? "" : "s"} shifted focus without a net score change.`;
  }
  if (removed.length > 0) {
    return `${removed.length} concern${removed.length === 1 ? "" : "s"} cleared — scores held steady.`;
  }
  if (added.length > 0) {
    return `${added.length} new note${added.length === 1 ? "" : "s"} added — scores held steady.`;
  }
  return "No material score movement between versions.";
}

export function computeVersionDiff(prior: Verdict[], current: Verdict[]): VersionDiff | null {
  if (prior.length === 0 || current.length === 0) return null;

  const scoreBefore = panelAverageScore(prior);
  const scoreAfter = panelAverageScore(current);
  if (scoreBefore == null || scoreAfter == null) return null;

  const removed: VersionDiffItem[] = [];
  const added: VersionDiffItem[] = [];
  const changed: VersionDiffChange[] = [];
  const evidenceAdded: VersionDiffItem[] = [];

  for (const judgeId of JUDGE_ORDER) {
    const priorVerdict = prior.find((verdict) => verdict.judge === judgeId);
    const currentVerdict = current.find((verdict) => verdict.judge === judgeId);
    if (!priorVerdict || !currentVerdict) continue;

    const priorConcern = priorVerdict.key_concern.trim();
    const currentConcern = currentVerdict.key_concern.trim();
    const status = concernAddressedStatus(priorVerdict, currentVerdict);
    const sameConcern =
      priorConcern &&
      currentConcern &&
      normalizeText(priorConcern) === normalizeText(currentConcern);

    if (priorConcern && !currentConcern) {
      removed.push({ judge: judgeId, text: priorConcern });
    } else if (!priorConcern && currentConcern) {
      added.push({ judge: judgeId, text: currentConcern });
    } else if (priorConcern && currentConcern && !sameConcern) {
      if (status === "Likely addressed" && currentVerdict.score > priorVerdict.score) {
        removed.push({ judge: judgeId, text: priorConcern });
        if (currentConcern) {
          added.push({ judge: judgeId, text: currentConcern });
        }
      } else {
        changed.push({ judge: judgeId, before: priorConcern, after: currentConcern });
      }
    }

    const priorEvidence = (priorVerdict.evidence_to_change_verdict ?? "").trim();
    const currentEvidence = (currentVerdict.evidence_to_change_verdict ?? "").trim();
    if (
      currentEvidence &&
      normalizeText(currentEvidence) !== normalizeText(priorEvidence)
    ) {
      evidenceAdded.push({ judge: judgeId, text: currentEvidence });
    }
  }

  const scoreDelta = Math.round((scoreAfter - scoreBefore) * 10) / 10;

  return {
    scoreBefore,
    scoreAfter,
    scoreDelta,
    reasonSummary: summarizeVersionDiff(scoreDelta, removed, added, changed),
    removed,
    added,
    changed,
    evidenceAdded,
  };
}
