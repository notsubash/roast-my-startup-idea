/**
 * Appeal coaching helpers — keep in sync with src/appeal/coaching.py (canonical).
 */
import { JUDGE_ORDER } from "../sse/types.ts";
import type { JudgeId, Verdict, VerdictLabel } from "../sse/types.ts";

const APPEAL_PRIORITY: Record<VerdictLabel, number> = {
  FAIL: 0,
  CONDITIONAL: 1,
  PASS: 2,
};

const DERIVED_HINT_PREFIX = "Provide concrete evidence that addresses:";

// ponytail: Jaccard on word tokens catches near-paraphrase; upgrade path is embedding similarity.
const LENS_SIMILARITY_THRESHOLD = 0.85;

const GENERIC_EVIDENCE_PHRASES = [
  "do more research",
  "conduct more research",
  "provide more evidence",
  "show more evidence",
  "gather more data",
  "need more validation",
  "validate the market",
  "show traction",
  "prove product-market fit",
  "prove product market fit",
  "conduct market research",
  "more customer discovery",
  "build a stronger case",
] as const;

const FILLER_AFTER_GENERIC_PHRASE = new Set([
  "on",
  "the",
  "a",
  "an",
  "this",
  "that",
  "idea",
  "buyer",
  "market",
  "please",
  "first",
  "more",
  "your",
  "and",
  "or",
  "to",
  "for",
]);

function normalizeSentence(text: string): string {
  return text.toLowerCase().split(/\s+/).filter(Boolean).join(" ");
}

export function sentenceSimilarity(left: string, right: string): number {
  const leftTokens = new Set(normalizeSentence(left).split(" "));
  const rightTokens = new Set(normalizeSentence(right).split(" "));
  if (!leftTokens.size || !rightTokens.size) return 0;
  let overlap = 0;
  for (const token of leftTokens) {
    if (rightTokens.has(token)) overlap += 1;
  }
  const union = new Set([...leftTokens, ...rightTokens]).size;
  return union ? overlap / union : 0;
}

function isGenericClause(normalized: string): boolean {
  const phrases = [...GENERIC_EVIDENCE_PHRASES].sort(
    (left, right) => right.length - left.length,
  );
  for (const phrase of phrases) {
    if (normalized === phrase) return true;
    if (normalized.startsWith(phrase)) {
      const rest = normalized.slice(phrase.length).trim().replace(/[.]+$/, "");
      if (!rest || rest.split(/\s+/).every((word) => FILLER_AFTER_GENERIC_PHRASE.has(word))) {
        return true;
      }
    }
  }
  return false;
}

export function isGenericEvidence(text: string): boolean {
  const normalized = normalizeSentence(text);
  if (!normalized) return true;
  const parts = normalized
    .split(" and ")
    .map((part) => part.trim())
    .filter(Boolean);
  if (parts.length > 1) {
    return parts.every((part) => isGenericClause(part));
  }
  return isGenericClause(normalized);
}

export type AppealHintQuality = "precise" | "derived" | "generic" | "duplicate";

export function isDerivedCoachingHint(hint: string): boolean {
  return hint.trim().startsWith(DERIVED_HINT_PREFIX);
}

export function appealCoachingHint(verdict: Verdict): string {
  const evidence = verdict.evidence_to_change_verdict?.trim();
  if (evidence) return evidence;
  return `${DERIVED_HINT_PREFIX} ${verdict.key_concern.trim()}`;
}

export function isDegenerateEvidenceAsks(verdicts: Verdict[]): boolean {
  const asks = verdicts
    .map((verdict) => normalizeSentence(appealCoachingHint(verdict)))
    .filter(Boolean);
  if (asks.length < 2) return false;
  const first = asks[0];
  return asks.every((ask) => ask === first);
}

function hintQuality(
  verdict: Verdict,
  duplicateJudges: Set<JudgeId>,
): AppealHintQuality {
  if (duplicateJudges.has(verdict.judge)) return "duplicate";
  const evidence = verdict.evidence_to_change_verdict?.trim();
  if (!evidence) return "derived";
  if (isGenericEvidence(evidence)) return "generic";
  return "precise";
}

export function appealCoachingVerdicts(verdicts: Verdict[]): Verdict[] {
  return [...verdicts].sort((left, right) => {
    const priority =
      APPEAL_PRIORITY[left.verdict] - APPEAL_PRIORITY[right.verdict];
    if (priority !== 0) return priority;
    return (
      JUDGE_ORDER.indexOf(left.judge) - JUDGE_ORDER.indexOf(right.judge)
    );
  });
}

/** Verdicts with enough data to coach or appeal against. */
export function appealBaselineVerdicts(verdicts: Verdict[]): Verdict[] {
  return verdicts.filter((verdict) => verdict.score > 0 || Boolean(verdict.roast));
}

export interface AppealCoachingItem {
  judge: JudgeId;
  hint: string;
  verdict: VerdictLabel;
  score: number;
  quality: AppealHintQuality;
}

export interface AppealCoachingAssessment {
  degraded: boolean;
  reasons: string[];
  items: AppealCoachingItem[];
  degenerateAsks: boolean;
}

/** Judges whose normalized evidence ask collides with another panel member. */
export function findDuplicateEvidenceJudges(verdicts: Verdict[]): Set<JudgeId> {
  const duplicateJudges = new Set<JudgeId>();
  const seen = new Map<string, JudgeId>();

  for (const verdict of verdicts) {
    const normalized = normalizeSentence(appealCoachingHint(verdict));
    if (!normalized) continue;
    const prior = seen.get(normalized);
    if (prior !== undefined) {
      duplicateJudges.add(verdict.judge);
      duplicateJudges.add(prior);
    } else {
      seen.set(normalized, verdict.judge);
    }
  }

  const evidenceItems: { judge: JudgeId; text: string }[] = [];
  for (const verdict of verdicts) {
    const evidence = verdict.evidence_to_change_verdict?.trim();
    if (!evidence) continue;
    evidenceItems.push({
      judge: verdict.judge,
      text: normalizeSentence(evidence),
    });
  }
  for (let index = 0; index < evidenceItems.length; index += 1) {
    for (let other = index + 1; other < evidenceItems.length; other += 1) {
      const left = evidenceItems[index];
      const right = evidenceItems[other];
      if (
        left.text === right.text ||
        sentenceSimilarity(left.text, right.text) >= LENS_SIMILARITY_THRESHOLD
      ) {
        duplicateJudges.add(left.judge);
        duplicateJudges.add(right.judge);
      }
    }
  }

  return duplicateJudges;
}

export function assessAppealCoaching(verdicts: Verdict[]): AppealCoachingAssessment {
  const ordered = appealCoachingVerdicts(verdicts);
  const duplicateJudges = findDuplicateEvidenceJudges(ordered);

  const items: AppealCoachingItem[] = ordered.map((verdict) => ({
    judge: verdict.judge,
    hint: appealCoachingHint(verdict),
    verdict: verdict.verdict,
    score: verdict.score,
    quality: hintQuality(verdict, duplicateJudges),
  }));

  const degenerateAsks = ordered.length > 0 && isDegenerateEvidenceAsks(ordered);
  const reasons: string[] = [];
  if (degenerateAsks) {
    reasons.push("Judges returned near-identical evidence asks.");
  } else if (duplicateJudges.size > 0) {
    reasons.push("Some judges asked for the same proof.");
  } else {
    const genericCount = items.filter((item) => item.quality === "generic").length;
    if (genericCount > 0) {
      reasons.push(
        `${genericCount} evidence ask${genericCount === 1 ? "" : "s"} look generic — treat them as directional, not precise targets.`,
      );
    }
  }

  return {
    degraded: reasons.length > 0,
    reasons,
    items,
    degenerateAsks,
  };
}

export function normalizeTargetJudges(judges: JudgeId[] | undefined): JudgeId[] {
  if (!judges?.length) return [];
  const allowed = new Set(JUDGE_ORDER);
  return JUDGE_ORDER.filter((judge) => allowed.has(judge) && judges.includes(judge));
}

export function appealEvidenceOutcome(
  original: Verdict,
  revised: Verdict,
): string {
  const delta = revised.score - original.score;
  if (delta > 0) return "Evidence met";
  if (delta < 0) return "Not met";
  if (original.verdict === "PASS") return "Already passing";
  return "Not met";
}

export interface AppealJudgeOutcome {
  judge: JudgeId;
  evidenceAsk: string;
  outcome: string;
  targeted: boolean;
  scoreDelta: number;
}

export function appealJudgeOutcomes(
  baseline: Verdict[],
  revised: Verdict[],
  targetJudges: JudgeId[] = [],
): AppealJudgeOutcome[] {
  const originals = new Map(baseline.map((verdict) => [verdict.judge, verdict]));
  const targets = new Set(normalizeTargetJudges(targetJudges));
  return revised.flatMap((revisedVerdict) => {
    const original = originals.get(revisedVerdict.judge);
    if (!original) return [];
    const scoreDelta = revisedVerdict.score - original.score;
    return [
      {
        judge: revisedVerdict.judge,
        evidenceAsk: appealCoachingHint(original),
        outcome: appealEvidenceOutcome(original, revisedVerdict),
        targeted: targets.has(revisedVerdict.judge),
        scoreDelta,
      },
    ];
  });
}

export function appealScoreMovement(
  baseline: Verdict[],
  revised: Verdict[],
): { positiveMoves: number; netDelta: number } {
  const originals = new Map(baseline.map((verdict) => [verdict.judge, verdict]));
  let positiveMoves = 0;
  let netDelta = 0;
  for (const revisedVerdict of revised) {
    const original = originals.get(revisedVerdict.judge);
    if (!original) continue;
    const delta = revisedVerdict.score - original.score;
    netDelta += delta;
    if (delta > 0) positiveMoves += 1;
  }
  return { positiveMoves, netDelta };
}
