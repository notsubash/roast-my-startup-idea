import type { VerdictLabel } from "@/lib/sse/types";

export interface ParsedSynthesis {
  verdict: VerdictLabel | null;
  score: string | null;
  sections: Array<{ title: string; bullets: string[] }>;
}

const VERDICT_LABELS: VerdictLabel[] = ["PASS", "FAIL", "CONDITIONAL"];

function parseVerdictLabel(raw: string | undefined): VerdictLabel | null {
  if (!raw) return null;
  const upper = raw.toUpperCase();
  for (const label of VERDICT_LABELS) {
    if (upper.includes(label)) return label;
  }
  return null;
}

function parseSectionChunk(chunk: string): { number: number; title: string; body: string } | null {
  const match = chunk.match(/^\*\*(\d+)\.\s*(.+?)\*\*:?\s*([\s\S]*)$/);
  if (!match) return null;
  return {
    number: Number(match[1]),
    title: match[2].trim().replace(/:$/, ""),
    body: match[3].trim(),
  };
}

/** Split list body on newlines or inline ` - ` separators (model often omits newlines). */
export function splitBulletBody(body: string): string[] {
  const trimmed = body.trim();
  if (!trimmed) return [];

  const byNewline = trimmed
    .split(/\n\s*[-•]\s+/)
    .map((s) => s.replace(/^[-•]\s+/, "").trim())
    .filter(Boolean);
  if (byNewline.length > 1) return byNewline;

  if (/\s-\s/.test(trimmed)) {
    return trimmed
      .split(/\s+-\s+/)
      .map((s) => s.replace(/^[-•]\s+/, "").trim())
      .filter(Boolean);
  }

  return [trimmed.replace(/^[-•]\s+/, "")];
}

/** Parse moderator synthesis markdown (fixed 5-section shape from moderator_node_prompt). */
export function parseSynthesis(content: string): ParsedSynthesis | null {
  const chunks = content
    .split(/(?=\*\*\d+\.)/)
    .map((s) => s.trim())
    .filter(Boolean);
  if (chunks.length === 0) return null;

  const parsed = chunks.map(parseSectionChunk).filter((s) => s !== null);
  if (parsed.length === 0) return null;

  const verdictChunk = parsed.find((s) => s.number === 1);
  const scoreChunk = parsed.find((s) => s.number === 2);
  const sections = parsed
    .filter((s) => s.number >= 3)
    .map((s) => ({
      title: s.title,
      bullets: splitBulletBody(s.body),
    }));

  return {
    verdict: parseVerdictLabel(verdictChunk?.body),
    score: scoreChunk?.body?.trim() || null,
    sections,
  };
}
