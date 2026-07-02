import assert from "node:assert/strict";
import {
  computeConfidenceFromVerdicts,
  confidenceDelta,
  confidenceTier,
  lineageCurrentScore,
  lineageScoreDelta,
} from "../src/lib/confidence/confidence.ts";

assert.equal(confidenceTier(30), "Low");
assert.equal(confidenceTier(55), "Medium");
assert.equal(confidenceTier(75), "High");

const verdicts = [
  {
    judge: "pm",
    verdict: "CONDITIONAL",
    roast: "ICP unclear.",
    score: 5,
    key_concern: "Who buys this?",
  },
  {
    judge: "customer",
    verdict: "FAIL",
    roast: "Would not pay.",
    score: 3,
    key_concern: "No urgency.",
  },
  {
    judge: "competitor",
    verdict: "FAIL",
    roast: "Crowded.",
    score: 4,
    key_concern: "Incumbents win.",
  },
  {
    judge: "vc",
    verdict: "CONDITIONAL",
    roast: "Small TAM.",
    score: 6,
    key_concern: "Moat unclear.",
  },
  {
    judge: "engineer",
    verdict: "PASS",
    roast: "Buildable.",
    score: 7,
    key_concern: "Ops risk.",
  },
];

const snapshot = computeConfidenceFromVerdicts(verdicts);
assert.ok(snapshot);
assert.equal(snapshot.weakest, "pricing");
assert.equal(snapshot.dimensions.find((item) => item.dimension === "demand")?.value, 40);
assert.equal(snapshot.dimensions.find((item) => item.dimension === "pricing")?.value, 30);
assert.equal(snapshot.dimensions.find((item) => item.dimension === "competition")?.value, 40);
assert.equal(snapshot.dimensions.find((item) => item.dimension === "moat")?.value, 65);

const improved = verdicts.map((verdict) =>
  verdict.judge === "customer" ? { ...verdict, score: 6 } : verdict,
);
const after = computeConfidenceFromVerdicts(improved);
assert.ok(after);
const delta = confidenceDelta(snapshot, after);
assert.equal(delta.pricing, 30);

const lineage = [
  {
    run_id: "a",
    status: "completed",
    idea_preview: "Pitch",
    created_at: "2026-01-01T00:00:00Z",
    version: 1,
    parent_run_id: null,
    verdict_summary: { pass: 1, fail: 2, conditional: 2, avg_score: 4.2 },
  },
  {
    run_id: "b",
    status: "completed",
    idea_preview: "Pitch",
    created_at: "2026-01-02T00:00:00Z",
    version: 2,
    parent_run_id: "a",
    verdict_summary: { pass: 2, fail: 1, conditional: 2, avg_score: 5.4 },
  },
];

assert.equal(lineageCurrentScore(lineage), 5.4);
assert.equal(lineageScoreDelta(lineage), 1.2);

const lineageWithGap = [
  lineage[0],
  {
    run_id: "failed",
    status: "failed",
    idea_preview: "Pitch",
    created_at: "2026-01-01T12:30:00Z",
    version: 2,
    parent_run_id: "a",
    verdict_summary: null,
  },
  lineage[1],
];
assert.equal(lineageScoreDelta(lineageWithGap), 1.2);

const partialPanel = verdicts.filter((verdict) => verdict.judge !== "customer");
const partialSnapshot = computeConfidenceFromVerdicts(partialPanel);
assert.ok(partialSnapshot);
assert.equal(
  partialSnapshot.dimensions.find((item) => item.dimension === "pricing"),
  undefined,
);

console.log("test-confidence: ok");
