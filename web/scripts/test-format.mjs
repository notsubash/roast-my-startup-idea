import assert from "node:assert/strict";
import test from "node:test";

import { formatRunMetricsFooter } from "../src/lib/format/metrics.ts";
import {
  buildTranscriptMarkdown,
  formatExportDate,
  formatFilenameStamp,
  transcriptFilename,
} from "../src/lib/format/transcript-md.ts";
import { resolveExportIdea } from "../src/lib/format/run-idea.ts";
import { initialRunState } from "../src/lib/sse/run-reducer.ts";

const metrics = {
  roast_seconds: 4.2,
  debate_seconds: 11.8,
  total_seconds: 16.0,
  input_tokens: 2100,
  output_tokens: 980,
  total_tokens: 3080,
  estimated_cost_usd: 0.004,
  model_runtime: "deepseek",
  judge_calls: [],
  debate_calls: [],
};

const fixedDate = new Date(2026, 5, 28, 14, 30, 45);

test("formatRunMetricsFooter matches backend example", () => {
  assert.equal(
    formatRunMetricsFooter(metrics),
    "Roast 4.2s · Debate 11.8s · ~3.1k tokens · ~$0.004",
  );
  assert.equal(
    formatRunMetricsFooter({ ...metrics, estimated_cost_usd: 0 }),
    "Roast 4.2s · Debate 11.8s · ~3.1k tokens · ~$0.00",
  );
  assert.equal(
    formatRunMetricsFooter({ ...metrics, revote_seconds: 8.3 }),
    "Roast 4.2s · Debate 11.8s · Re-vote 8.3s · ~3.1k tokens · ~$0.004",
  );
});

test("export date and filename stamps mirror backend", () => {
  assert.equal(formatExportDate(fixedDate), "2026-06-28 14:30");
  assert.equal(formatFilenameStamp(fixedDate), "20260628_143045");
  assert.equal(
    transcriptFilename("AI for pets!", "run-abc", fixedDate),
    "20260628_143045_ai_for_pets.md",
  );
});

test("resolveExportIdea prefers API idea over preview", () => {
  assert.equal(
    resolveExportIdea("run-1", "short preview", "Full startup pitch text"),
    "Full startup pitch text",
  );
});

test("buildTranscriptMarkdown mirrors backend layout", () => {
  const state = initialRunState("completed");
  state.judges.vc = {
    status: "revealed",
    verdict: {
      judge: "vc",
      verdict: "FAIL",
      score: 4,
      roast: "Too small a market.",
      key_concern: "TAM is unclear.",
    },
  };
  state.debateTurns = [
    { speaker: "vc", round: 1, content: "Still too small.", streaming: false, thinking: false },
    { speaker: "engineer", round: 1, content: "Technically fine.", streaming: false, thinking: false },
    { speaker: "moderator", round: 1, content: "ignored", streaming: false, thinking: false },
  ];
  state.synthesis = "Needs sharper positioning.";

  const md = buildTranscriptMarkdown(
    {
      idea: "AI for pets",
      runId: "run-abc",
      judges: state.judges,
      debateTurns: state.debateTurns,
      synthesis: state.synthesis,
      metrics,
    },
    fixedDate,
  );

  const vcIdx = md.indexOf("**VC:**");
  const engineerIdx = md.indexOf("**ENGINEER:**");
  assert.ok(vcIdx !== -1 && engineerIdx !== -1 && vcIdx < engineerIdx, "debate export preserves turn order");

  assert.match(md, /## Phase 1: Individual Roasts/);
  assert.match(md, /### VC — FAIL \(4\/10\)/);
  assert.match(md, /## Phase 2: Debate/);
  assert.match(md, /\*\*VC:\*\* Still too small\./);
  assert.ok(!/moderator/i.test(md), "moderator turns should be omitted from export");
  assert.match(md, /## Final Synthesis/);
  assert.match(md, /## Run Metrics/);
  assert.match(md, /\*\*Date:\*\* 2026-06-28 14:30/);
  assert.ok(!/\*\*Run:\*\*/.test(md), "backend exporter omits run id line");
  assert.match(md, /Partial export: 1 of 5 judge verdicts recorded\./);
});
