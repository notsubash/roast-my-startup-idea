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

function parseAppealSectionChunk(chunk: string): { title: string; body: string } | null {
  const match = chunk.match(/^\*\*(.+?)\*\*:?\s*([\s\S]*)$/);
  if (!match) return null;
  return {
    title: match[1].trim().replace(/:$/, ""),
    body: match[2].trim(),
  };
}

function parseAppealScore(body: string): string | null {
  const revised = body.match(/(?:revised score|score)[:\s]*([\d.]+)\s*(?:\/\s*10)?/i);
  if (revised) return revised[1];
  const plain = body.match(/([\d.]+)\s*\/\s*10/);
  return plain ? plain[1] : null;
}

/** Parse appeal synthesis markdown (section headings + bullet lists, not numbered sections). */
export function parseAppealSynthesis(content: string): ParsedSynthesis | null {
  const chunks = content
    .split(/\n\n+/)
    .map((s) => s.trim())
    .filter(Boolean);
  if (chunks.length === 0) return null;

  let verdict: VerdictLabel | null = null;
  let score: string | null = null;
  const sections: Array<{ title: string; bullets: string[] }> = [];

  for (const chunk of chunks) {
    const parsed = parseAppealSectionChunk(chunk);
    if (!parsed) continue;

    const titleLower = parsed.title.toLowerCase();
    if (titleLower === "appeal synthesis") continue;

    if (titleLower.includes("overall verdict")) {
      verdict = parseVerdictLabel(parsed.body);
      score = parseAppealScore(parsed.body);
      continue;
    }

    if (parsed.body) {
      sections.push({
        title: parsed.title,
        bullets: splitBulletBody(parsed.body),
      });
    }
  }

  if (!verdict && !score && sections.length === 0) return null;
  return { verdict, score, sections };
}

/** ponytail: naive inline markdown for synthesis bullets — upgrade path is a shared markdown renderer. */
export function splitInlineMarkdown(text: string): Array<{ kind: "text" | "bold" | "italic"; value: string }> {
  const parts: Array<{ kind: "text" | "bold" | "italic"; value: string }> = [];
  const re = /(\*\*[^*]+\*\*|\*[^*]+\*)/g;
  let last = 0;
  for (const match of text.matchAll(re)) {
    const index = match.index ?? 0;
    if (index > last) {
      parts.push({ kind: "text", value: text.slice(last, index) });
    }
    const token = match[0];
    if (token.startsWith("**")) {
      parts.push({ kind: "bold", value: token.slice(2, -2) });
    } else {
      parts.push({ kind: "italic", value: token.slice(1, -1) });
    }
    last = index + token.length;
  }
  if (last < text.length) {
    parts.push({ kind: "text", value: text.slice(last) });
  }
  return parts.length > 0 ? parts : [{ kind: "text", value: text }];
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
