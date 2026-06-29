import type { Verdict } from "@/lib/sse/types";

import type { ConfidenceLevel, StructuredSynthesis } from "./structured-synthesis";

function normalizeSentence(text: string): string {
  return text.toLowerCase().replace(/\s+/g, " ").trim();
}

function isDegenerateFixes(verdicts: Verdict[]): boolean {
  const fixes = verdicts
    .map((verdict) => verdict.recommended_fix?.trim())
    .filter((fix): fix is string => Boolean(fix))
    .map(normalizeSentence);
  if (fixes.length < 2) return false;
  const first = fixes[0];
  return fixes.every((fix) => fix === first);
}

export interface RevoteOutputQuality {
  herdedDeltas: boolean;
  directionalPileOn: boolean;
  pileOnDirection: "up" | "down" | null;
  degeneratePanel: boolean;
  scoresMoved: boolean;
  /** Suspicious herding only — identical deltas or uniform revised panel. */
  lowConfidence: boolean;
  /** Debate shifted multiple judges the same direction with varied deltas. */
  panelConverged: boolean;
  /** Informational note when the panel converged coherently after debate. */
  convergenceNote: string | null;
  reasons: string[];
}

export function assessRevoteOutputQuality(
  baseline: Partial<Record<string, Verdict>>,
  current: Verdict[],
): RevoteOutputQuality {
  const deltas: number[] = [];
  for (const verdict of current) {
    const original = baseline[verdict.judge];
    if (!original) continue;
    deltas.push(verdict.score - original.score);
  }
  const nonZero = deltas.filter((delta) => delta !== 0);
  const herdedDeltas = nonZero.length >= 4 && new Set(nonZero).size === 1;
  const signs = new Set(nonZero.map((delta) => (delta > 0 ? 1 : -1)));
  const directionalPileOn = nonZero.length >= 3 && signs.size === 1;
  const pileOnDirection = directionalPileOn
    ? signs.has(1)
      ? "up"
      : "down"
    : null;
  const scores = current.map((verdict) => verdict.score);
  const verdictLabels = current.map((verdict) => verdict.verdict);
  const degeneratePanel =
    scores.length >= 2 &&
    scores.every((score) => score === scores[0]) &&
    verdictLabels.every((label) => label === verdictLabels[0]);

  const panelConverged = directionalPileOn && !herdedDeltas && !degeneratePanel;
  let convergenceNote: string | null = null;
  if (panelConverged && pileOnDirection) {
    const directionWord = pileOnDirection === "down" ? "lower" : "higher";
    convergenceNote = `${nonZero.length} judges scored ${directionWord} after the debate — the panel converged on shared concerns.`;
  }

  const reasons: string[] = [];
  if (herdedDeltas) {
    reasons.push("Four or more judges moved by the exact same score delta — scores may have herded.");
  }
  if (degeneratePanel) {
    reasons.push("Revised panel scores are suspiciously uniform.");
  }

  return {
    herdedDeltas,
    directionalPileOn,
    pileOnDirection,
    degeneratePanel,
    scoresMoved: nonZero.length > 0,
    lowConfidence: reasons.length > 0,
    panelConverged,
    convergenceNote,
    reasons,
  };
}

export interface VerdictOutputQuality {
  lowConfidence: boolean;
  reasons: string[];
  degenerateFixes: boolean;
}

export function assessVerdictOutputQuality(
  verdicts: Verdict[],
  synthesis: StructuredSynthesis | null,
  proseFallback: boolean,
): VerdictOutputQuality {
  const reasons: string[] = [];

  if (verdicts.length > 0 && isDegenerateFixes(verdicts)) {
    reasons.push("Judges returned near-identical recommended fixes.");
  }

  if (proseFallback) {
    reasons.push("Moderator fell back to free-text synthesis.");
  }

  if (synthesis?.confidence === ("LOW" satisfies ConfidenceLevel)) {
    reasons.push("Moderator reported low confidence in the recommendation.");
  }

  return {
    lowConfidence: reasons.length > 0,
    reasons,
    degenerateFixes: isDegenerateFixes(verdicts),
  };
}
