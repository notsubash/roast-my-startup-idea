export type OverallRecommendation = "GO" | "ITERATE" | "NO-GO";
export type ConfidenceLevel = "LOW" | "MEDIUM" | "HIGH";

export interface StructuredSynthesis {
  overall_recommendation: OverallRecommendation;
  confidence: ConfidenceLevel;
  top_strengths: string[];
  top_risks: string[];
  biggest_disagreement: string;
}

const RECOMMENDATIONS: OverallRecommendation[] = ["GO", "ITERATE", "NO-GO"];
const CONFIDENCE_LEVELS: ConfidenceLevel[] = ["LOW", "MEDIUM", "HIGH"];

function asStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is string => typeof item === "string" && item.trim().length > 0);
}

export function parseStructuredSynthesis(raw: unknown): StructuredSynthesis | null {
  if (!raw || typeof raw !== "object") return null;
  const data = raw as Record<string, unknown>;
  const recommendation = data.overall_recommendation;
  const confidence = data.confidence;
  const disagreement = data.biggest_disagreement;
  if (
    typeof recommendation !== "string" ||
    !RECOMMENDATIONS.includes(recommendation as OverallRecommendation) ||
    typeof confidence !== "string" ||
    !CONFIDENCE_LEVELS.includes(confidence as ConfidenceLevel) ||
    typeof disagreement !== "string" ||
    !disagreement.trim()
  ) {
    return null;
  }
  return {
    overall_recommendation: recommendation as OverallRecommendation,
    confidence: confidence as ConfidenceLevel,
    top_strengths: asStringArray(data.top_strengths),
    top_risks: asStringArray(data.top_risks),
    biggest_disagreement: disagreement.trim(),
  };
}

/** Parse moderator prose emitted by synthesis_to_prose when structured JSON is unavailable. */
export function parseDecisionVerdictProse(content: string): StructuredSynthesis | null {
  const chunks = content
    .split(/\n\n+/)
    .map((chunk) => chunk.trim())
    .filter(Boolean);
  if (chunks.length === 0) return null;

  let recommendation: OverallRecommendation | null = null;
  let confidence: ConfidenceLevel | null = null;
  const top_strengths: string[] = [];
  const top_risks: string[] = [];
  let biggest_disagreement = "";

  for (const chunk of chunks) {
    const headerMatch = chunk.match(/^\*\*([^*]+):\*\*\s*([\s\S]*)$/);
    if (!headerMatch) continue;
    const label = headerMatch[1].trim().toLowerCase();
    const body = headerMatch[2].trim();

    if (label === "recommendation") {
      const upper = body.toUpperCase();
      recommendation = RECOMMENDATIONS.find((item) => upper.includes(item)) ?? null;
      continue;
    }
    if (label === "confidence") {
      const upper = body.toUpperCase();
      confidence = CONFIDENCE_LEVELS.find((item) => upper.includes(item)) ?? null;
      continue;
    }
    if (label === "strengths") {
      top_strengths.push(...body.split("\n").map((line) => line.replace(/^[-•]\s*/, "").trim()).filter(Boolean));
      continue;
    }
    if (label === "top risks") {
      top_risks.push(...body.split("\n").map((line) => line.replace(/^[-•]\s*/, "").trim()).filter(Boolean));
      continue;
    }
    if (label === "biggest disagreement") {
      biggest_disagreement = body;
    }
  }

  if (!recommendation || !confidence || !biggest_disagreement) return null;
  return {
    overall_recommendation: recommendation,
    confidence,
    top_strengths,
    top_risks,
    biggest_disagreement,
  };
}

export function topPriorities(
  synthesis: StructuredSynthesis,
  fixes: string[],
  limit = 3,
): string[] {
  if (synthesis.top_risks.length > 0) {
    return synthesis.top_risks.slice(0, limit);
  }
  return fixesToPriorities(fixes, limit);
}

function fixesToPriorities(fixes: string[], limit: number): string[] {
  const seen = new Set<string>();
  const priorities: string[] = [];
  for (const fix of fixes) {
    const trimmed = fix.trim();
    if (!trimmed || seen.has(trimmed)) continue;
    seen.add(trimmed);
    priorities.push(trimmed);
    if (priorities.length >= limit) break;
  }
  return priorities;
}

/** Judge fixes ranked FAIL → CONDITIONAL → PASS, lowest score first within tier. */
export function collectRecommendedFixes(
  verdicts: Array<{ verdict: string; score: number; recommended_fix?: string | null }>,
): string[] {
  const rank: Record<string, number> = { FAIL: 0, CONDITIONAL: 1, PASS: 2 };
  return [...verdicts]
    .sort((a, b) => {
      const rankA = rank[a.verdict] ?? 9;
      const rankB = rank[b.verdict] ?? 9;
      if (rankA !== rankB) return rankA - rankB;
      return a.score - b.score;
    })
    .map((verdict) => verdict.recommended_fix?.trim())
    .filter((fix): fix is string => Boolean(fix));
}

const NEXT_ACTION_SLOTS = 3;

/** Top founder actions from synthesis risks or judge recommended fixes. */
export function deriveNextActions(
  synthesisProse: string | null,
  structuredSynthesis: unknown,
  verdicts: Array<{ verdict: string; score: number; recommended_fix?: string | null }>,
  limit = NEXT_ACTION_SLOTS,
): string[] {
  const structured =
    parseStructuredSynthesis(structuredSynthesis) ??
    (synthesisProse ? parseDecisionVerdictProse(synthesisProse) : null);
  if (structured) {
    return topPriorities(structured, collectRecommendedFixes(verdicts), limit);
  }
  return fixesToPriorities(collectRecommendedFixes(verdicts), limit);
}

export interface WorkflowBrief {
  problems: string[];
  blocker: string | null;
  experiment: string;
}

/** Deterministic experiment suggestion from the top blocker — no LLM. */
export function deriveRecommendedExperiment(blocker: string | null): string {
  if (!blocker) {
    return "Gather concrete customer evidence that addresses the panel's top concern.";
  }
  return `Run a focused validation experiment: ${blocker}`;
}

export function deriveWorkflowBrief(
  synthesisProse: string | null,
  structuredSynthesis: unknown,
  verdicts: Array<{ verdict: string; score: number; recommended_fix?: string | null }>,
): WorkflowBrief {
  const problems = deriveNextActions(synthesisProse, structuredSynthesis, verdicts);
  const structured =
    parseStructuredSynthesis(structuredSynthesis) ??
    (synthesisProse ? parseDecisionVerdictProse(synthesisProse) : null);
  const disagreement = structured?.biggest_disagreement?.trim();
  // ponytail: blocker = uncertainty signal; problem #1 already covers the top fix
  const blocker = disagreement && disagreement !== problems[0] ? disagreement : null;
  const experimentFocus = problems[0] ?? blocker;
  return {
    problems,
    blocker,
    experiment: deriveRecommendedExperiment(experimentFocus),
  };
}

export { NEXT_ACTION_SLOTS };
