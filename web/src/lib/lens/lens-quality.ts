/**
 * Lens uniqueness checks — keep in sync with src/verification/lens.py (canonical).
 *
 * SSE `panel_quality.lens_uniqueness_passed` maps to eval `lens_differentiation_passed`.
 */
import {
  appealCoachingHint,
  findDuplicateEvidenceJudges,
  isGenericEvidence,
  sentenceSimilarity,
} from "../appeal/coaching.ts";
import type { JudgeId, Verdict } from "../sse/types.ts";

// ponytail: Jaccard on word tokens catches near-paraphrase; upgrade path is embedding similarity.
export const LENS_SIMILARITY_THRESHOLD = 0.85;
export const MAX_GENERIC_EVIDENCE_RATE = 0.4;

function normalizeSentence(text: string): string {
  return text.toLowerCase().split(/\s+/).filter(Boolean).join(" ");
}

export interface LensOverlapPair {
  left: JudgeId;
  right: JudgeId;
  similarity: number;
}

export interface LensUniquenessAssessment {
  lensLegacy: boolean;
  lensUniquenessPassed: boolean;
  duplicateEvidenceJudges: JudgeId[];
  overlappingConcernPairs: LensOverlapPair[];
  overlappingEvidencePairs: LensOverlapPair[];
  genericEvidenceCount: number;
  genericEvidenceRate: number;
}

function findOverlappingJudgePairs(
  verdicts: Verdict[],
  field: "key_concern" | "evidence_to_change_verdict",
  threshold = LENS_SIMILARITY_THRESHOLD,
): LensOverlapPair[] {
  const pairs: LensOverlapPair[] = [];
  const items: { judge: JudgeId; text: string }[] = [];

  for (const verdict of verdicts) {
    const raw =
      field === "evidence_to_change_verdict"
        ? verdict.evidence_to_change_verdict?.trim()
        : verdict.key_concern?.trim();
    if (!raw) continue;
    items.push({ judge: verdict.judge, text: normalizeSentence(raw) });
  }

  for (let index = 0; index < items.length; index += 1) {
    for (let other = index + 1; other < items.length; other += 1) {
      const left = items[index];
      const right = items[other];
      if (left.text === right.text) {
        pairs.push({ left: left.judge, right: right.judge, similarity: 1 });
        continue;
      }
      const similarity = sentenceSimilarity(left.text, right.text);
      if (similarity >= threshold) {
        pairs.push({
          left: left.judge,
          right: right.judge,
          similarity: Math.round(similarity * 1000) / 1000,
        });
      }
    }
  }
  return pairs;
}

export function assessLensUniqueness(verdicts: Verdict[]): LensUniquenessAssessment {
  const empty: LensUniquenessAssessment = {
    lensLegacy: true,
    lensUniquenessPassed: true,
    duplicateEvidenceJudges: [],
    overlappingConcernPairs: [],
    overlappingEvidencePairs: [],
    genericEvidenceCount: 0,
    genericEvidenceRate: 0,
  };
  if (!verdicts.length) return empty;

  const hasEvidenceFields = verdicts.every((verdict) =>
    Boolean(verdict.evidence_to_change_verdict?.trim()),
  );
  if (!hasEvidenceFields) return empty;

  const duplicateEvidenceJudges = [...findDuplicateEvidenceJudges(verdicts)];
  const overlappingConcernPairs = findOverlappingJudgePairs(verdicts, "key_concern");
  const overlappingEvidencePairs = findOverlappingJudgePairs(
    verdicts,
    "evidence_to_change_verdict",
  );

  let genericEvidenceCount = 0;
  for (const verdict of verdicts) {
    const evidence = verdict.evidence_to_change_verdict?.trim();
    if (evidence && isGenericEvidence(evidence)) genericEvidenceCount += 1;
  }
  const genericEvidenceRate =
    Math.round((genericEvidenceCount / verdicts.length) * 1000) / 1000;

  const lensUniquenessPassed =
    duplicateEvidenceJudges.length === 0 &&
    overlappingConcernPairs.length === 0 &&
    overlappingEvidencePairs.length === 0 &&
    genericEvidenceRate <= MAX_GENERIC_EVIDENCE_RATE;

  return {
    lensLegacy: false,
    lensUniquenessPassed,
    duplicateEvidenceJudges,
    overlappingConcernPairs,
    overlappingEvidencePairs,
    genericEvidenceCount,
    genericEvidenceRate,
  };
}

/** Parse maintainer panel_quality payload from run_completed SSE. */
export function parsePanelQuality(
  raw: unknown,
): LensUniquenessAssessment | null {
  if (!raw || typeof raw !== "object") return null;
  const payload = raw as Record<string, unknown>;
  if (typeof payload.lens_uniqueness_passed !== "boolean") return null;
  return {
    lensLegacy: Boolean(payload.lens_legacy),
    lensUniquenessPassed: payload.lens_uniqueness_passed,
    duplicateEvidenceJudges: Array.isArray(payload.lens_duplicate_evidence_judges)
      ? (payload.lens_duplicate_evidence_judges as JudgeId[])
      : [],
    overlappingConcernPairs: Array.isArray(payload.lens_overlapping_concern_pairs)
      ? (payload.lens_overlapping_concern_pairs as LensOverlapPair[])
      : [],
    overlappingEvidencePairs: Array.isArray(payload.lens_overlapping_evidence_pairs)
      ? (payload.lens_overlapping_evidence_pairs as LensOverlapPair[])
      : [],
    genericEvidenceCount:
      typeof payload.lens_generic_evidence_count === "number"
        ? payload.lens_generic_evidence_count
        : 0,
    genericEvidenceRate:
      typeof payload.lens_generic_evidence_rate === "number"
        ? payload.lens_generic_evidence_rate
        : 0,
  };
}

export function lensQualitySummary(quality: LensUniquenessAssessment): string[] {
  const reasons: string[] = [];
  if (quality.duplicateEvidenceJudges.length > 0) {
    reasons.push(
      `Duplicate evidence asks: ${quality.duplicateEvidenceJudges.join(", ")}.`,
    );
  }
  for (const pair of quality.overlappingConcernPairs) {
    reasons.push(
      `Overlapping concerns (${pair.left}/${pair.right}, sim ${pair.similarity}).`,
    );
  }
  for (const pair of quality.overlappingEvidencePairs) {
    reasons.push(
      `Overlapping evidence (${pair.left}/${pair.right}, sim ${pair.similarity}).`,
    );
  }
  if (quality.genericEvidenceRate > MAX_GENERIC_EVIDENCE_RATE) {
    reasons.push(
      `Generic evidence rate ${quality.genericEvidenceRate} exceeds ${MAX_GENERIC_EVIDENCE_RATE}.`,
    );
  }
  return reasons;
}

/** Effective coaching hint for overlap checks (matches Python coaching_hint). */
export function coachingHintForLens(verdict: Verdict): string {
  return appealCoachingHint(verdict);
}
