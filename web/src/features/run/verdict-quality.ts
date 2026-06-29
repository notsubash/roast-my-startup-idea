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
