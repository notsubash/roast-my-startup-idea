import { JUDGE_ORDER } from "../sse/types.ts";
import type { DebateTurnView, JudgeView, RunMetrics, Verdict } from "../sse/types.ts";

import { formatRunMetricsMarkdown } from "./metrics.ts";

export interface TranscriptInput {
  idea: string;
  runId: string;
  judges: Record<(typeof JUDGE_ORDER)[number], JudgeView>;
  debateTurns: DebateTurnView[];
  synthesis: string | null;
  metrics: RunMetrics | null;
}

function pad2(n: number): string {
  return String(n).padStart(2, "0");
}

/** Local wall-clock stamp matching backend `transcript_exporter`. */
export function formatExportDate(date = new Date()): string {
  return `${date.getFullYear()}-${pad2(date.getMonth() + 1)}-${pad2(date.getDate())} ${pad2(date.getHours())}:${pad2(date.getMinutes())}`;
}

export function formatFilenameStamp(date = new Date()): string {
  return `${date.getFullYear()}${pad2(date.getMonth() + 1)}${pad2(date.getDate())}_${pad2(date.getHours())}${pad2(date.getMinutes())}${pad2(date.getSeconds())}`;
}

function collectVerdicts(judges: TranscriptInput["judges"]): Verdict[] {
  return JUDGE_ORDER.map((id) => judges[id].verdict).filter(
    (v): v is Verdict => v !== undefined,
  );
}

function debateMessagesForExport(turns: DebateTurnView[]) {
  return turns
    .filter((t) => t.speaker !== "moderator" && t.content.trim())
    .map((t) => ({ speaker: t.speaker, round: t.round, content: t.content }));
}

/** Client-side mirror of backend `transcript_exporter.export_transcript`. */
export function buildTranscriptMarkdown(input: TranscriptInput, now = new Date()): string {
  const verdicts = collectVerdicts(input.judges);
  const messages = debateMessagesForExport(input.debateTurns);
  const partial = verdicts.length > 0 && verdicts.length < JUDGE_ORDER.length;

  const lines: string[] = [
    "# Roast My Startup — Transcript",
    "",
    `**Idea:** ${input.idea}`,
    `**Date:** ${formatExportDate(now)}`,
    "",
  ];

  if (partial) {
    lines.push(
      `> Partial export: ${verdicts.length} of ${JUDGE_ORDER.length} judge verdicts recorded.`,
      "",
    );
  }

  lines.push(...formatRunMetricsMarkdown(input.metrics), "---", "", "## Phase 1: Individual Roasts", "");

  for (const v of verdicts) {
    lines.push(`### ${v.judge.toUpperCase()} — ${v.verdict} (${v.score}/10)`);
    lines.push("");
    lines.push(`> ${v.roast}`);
    lines.push("");
    lines.push(`**Key concern:** ${v.key_concern}`);
    lines.push("");
  }

  lines.push("---", "", "## Phase 2: Debate", "");

  let currentRound = 0;
  for (const msg of messages) {
    if (msg.round !== currentRound) {
      currentRound = msg.round;
      lines.push(`### Round ${currentRound}`, "");
    }
    lines.push(`**${msg.speaker.toUpperCase()}:** ${msg.content}`);
    lines.push("");
  }

  if (input.synthesis?.trim()) {
    lines.push("---", "", "## Final Synthesis", "", input.synthesis, "");
  }

  return lines.join("\n");
}

export function transcriptFilename(idea: string, runId: string, now = new Date()): string {
  const slug = idea
    .slice(0, 40)
    .replace(/[^a-zA-Z0-9 ]/g, "")
    .trim()
    .replace(/\s+/g, "_")
    .toLowerCase();
  return `${formatFilenameStamp(now)}_${slug || runId.slice(0, 8)}.md`;
}
