import assert from "node:assert/strict";
import test from "node:test";

import {
  parseDecisionVerdictProse,
  parseStructuredSynthesis,
  topPriorities,
} from "../src/features/run/structured-synthesis.ts";
import { assessRevoteOutputQuality, assessVerdictOutputQuality } from "../src/features/run/verdict-quality.ts";

const STRUCTURED = {
  overall_recommendation: "ITERATE",
  confidence: "MEDIUM",
  top_strengths: ["Clear pain point."],
  top_risks: ["No buyer proof yet.", "Long sales cycles."],
  biggest_disagreement: "VC and PM disagree on wedge size.",
};

test("parseStructuredSynthesis validates decision-ready shape", () => {
  const parsed = parseStructuredSynthesis(STRUCTURED);
  assert.equal(parsed?.overall_recommendation, "ITERATE");
  assert.deepEqual(parsed?.top_risks, ["No buyer proof yet.", "Long sales cycles."]);
});

test("parseDecisionVerdictProse reads synthesis_to_prose markdown", () => {
  const prose =
    "**Recommendation:** ITERATE\n\n**Confidence:** MEDIUM\n\n**Strengths:**\n- Clear pain point.\n\n**Top risks:**\n- No buyer proof yet.\n\n**Biggest disagreement:** VC and PM disagree on wedge size.";
  const parsed = parseDecisionVerdictProse(prose);
  assert.equal(parsed?.overall_recommendation, "ITERATE");
  assert.equal(parsed?.confidence, "MEDIUM");
  assert.equal(parsed?.top_risks.length, 1);
});

test("topPriorities prefers structured risks", () => {
  const parsed = parseStructuredSynthesis(STRUCTURED);
  assert.ok(parsed);
  assert.deepEqual(topPriorities(parsed, ["fallback fix"]), ["No buyer proof yet.", "Long sales cycles."]);
});

test("assessVerdictOutputQuality flags degenerate fixes", () => {
  const identicalFix = "Interview ten target buyers and document their top workflow pain.";
  const verdicts = [
    {
      judge: "vc",
      verdict: "FAIL",
      roast: "Weak distribution path for this idea in a crowded market.",
      score: 3,
      key_concern: "No buyer.",
      recommended_fix: identicalFix,
    },
    {
      judge: "engineer",
      verdict: "FAIL",
      roast: "The technical path is harder than the pitch suggests for this team.",
      score: 2,
      key_concern: "Reliability risk.",
      recommended_fix: identicalFix,
    },
  ];
  const quality = assessVerdictOutputQuality(verdicts, parseStructuredSynthesis(STRUCTURED), false);
  assert.equal(quality.lowConfidence, true);
  assert.equal(quality.degenerateFixes, true);
});

test("assessVerdictOutputQuality flags prose-only synthesis fallback", () => {
  const parsed = parseDecisionVerdictProse(
    "**Recommendation:** ITERATE\n\n**Confidence:** MEDIUM\n\n**Biggest disagreement:** Split on wedge.",
  );
  const quality = assessVerdictOutputQuality([], parsed, true);
  assert.equal(quality.lowConfidence, true);
  assert.match(quality.reasons.join(" "), /free-text synthesis/);
});

test("assessVerdictOutputQuality accepts numbered prose fallback shape", () => {
  const prose =
    "**1. Overall verdict:** FAIL\n\n**2. Final score from 1-10:** 2.0\n\n**3. Consensus points**\n- Scope is too broad.";
  const quality = assessVerdictOutputQuality([], null, false);
  assert.equal(quality.lowConfidence, false);
  assert.equal(quality.reasons.length, 0);
});

function verdict(judge, score) {
  return {
    judge,
    verdict: "CONDITIONAL",
    roast: "Needs work.",
    score,
    key_concern: "Gap.",
    recommended_fix: `Fix for ${judge}.`,
  };
}

test("assessRevoteOutputQuality treats varied same-direction moves as convergence", () => {
  const baseline = {
    vc: verdict("vc", 7),
    pm: verdict("pm", 7),
    customer: verdict("customer", 6),
    competitor: verdict("competitor", 5),
    engineer: verdict("engineer", 6),
  };
  const current = [
    verdict("vc", 5),
    verdict("pm", 6),
    verdict("customer", 5),
    verdict("competitor", 3),
    verdict("engineer", 6),
  ];
  const quality = assessRevoteOutputQuality(baseline, current);
  assert.equal(quality.panelConverged, true);
  assert.equal(quality.lowConfidence, false);
  assert.match(quality.convergenceNote ?? "", /converged on shared concerns/);
});

test("assessRevoteOutputQuality flags identical deltas as suspicious", () => {
  const baseline = {
    vc: verdict("vc", 7),
    pm: verdict("pm", 7),
    customer: verdict("customer", 7),
    competitor: verdict("competitor", 7),
    engineer: verdict("engineer", 7),
  };
  const current = [
    verdict("vc", 5),
    verdict("pm", 5),
    verdict("customer", 5),
    verdict("competitor", 5),
    verdict("engineer", 7),
  ];
  const quality = assessRevoteOutputQuality(baseline, current);
  assert.equal(quality.herdedDeltas, true);
  assert.equal(quality.lowConfidence, true);
  assert.equal(quality.panelConverged, false);
  assert.match(quality.reasons.join(" "), /herded/);
});
