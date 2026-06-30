import assert from "node:assert/strict";
import test from "node:test";

import { assessLensUniqueness, parsePanelQuality } from "../src/lib/lens/lens-quality.ts";

function verdict(judge, evidence, concern = "concern") {
  return {
    judge,
    verdict: "CONDITIONAL",
    roast: "x".repeat(40),
    score: 5,
    key_concern: concern,
    evidence_to_change_verdict: evidence,
  };
}

test("assessLensUniqueness passes distinct lens asks", () => {
  const verdicts = [
    verdict("vc", "Three signed LOIs with $50k+ ACV.", "Weak venture returns."),
    verdict("engineer", "Production benchmark with p99 under 200ms.", "Unproven reliability at scale."),
    verdict("pm", "Ten ICP interviews ranking pain top-two.", "ICP is too broad."),
    verdict("customer", "Paid pilot with twenty renewals after month one.", "Price is too high."),
    verdict("competitor", "Exclusive distribution blocking incumbents for eighteen months.", "Easy to copy."),
  ];
  const result = assessLensUniqueness(verdicts);
  assert.equal(result.lensLegacy, false);
  assert.equal(result.lensUniquenessPassed, true);
});

test("assessLensUniqueness fails duplicate evidence asks", () => {
  const shared = "Three signed LOIs with fifty thousand ACV each.";
  const verdicts = [
    verdict("vc", shared),
    verdict("customer", shared),
    verdict("engineer", "Benchmark p99 latency under 200ms."),
    verdict("pm", "Ten ICP interviews naming top-two pain."),
    verdict("competitor", "Exclusive distribution for eighteen months."),
  ];
  const result = assessLensUniqueness(verdicts);
  assert.equal(result.lensUniquenessPassed, false);
  assert.ok(result.duplicateEvidenceJudges.includes("vc"));
});

test("parsePanelQuality maps run_completed payload", () => {
  const parsed = parsePanelQuality({
    lens_legacy: false,
    lens_uniqueness_passed: true,
    lens_duplicate_evidence_judges: [],
    lens_overlapping_concern_pairs: [],
    lens_overlapping_evidence_pairs: [],
    lens_generic_evidence_count: 0,
    lens_generic_evidence_rate: 0,
  });
  assert.ok(parsed);
  assert.equal(parsed.lensUniquenessPassed, true);
});
