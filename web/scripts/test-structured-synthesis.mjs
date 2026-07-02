import assert from "node:assert/strict";
import test from "node:test";

import {
  collectRecommendedFixes,
  deriveNextActions,
  deriveRecommendedExperiment,
  deriveWorkflowBrief,
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

test("deriveRecommendedExperiment templates blocker into validation step", () => {
  assert.match(
    deriveRecommendedExperiment("Interview ten buyers."),
    /Interview ten buyers/,
  );
  assert.match(deriveRecommendedExperiment(null), /concrete customer evidence/);
});

test("deriveWorkflowBrief surfaces top blocker and experiment", () => {
  const brief = deriveWorkflowBrief(null, STRUCTURED, []);
  assert.equal(brief.blocker, "VC and PM disagree on wedge size.");
  assert.match(brief.experiment, /No buyer proof yet/);
  assert.equal(brief.problems.length, 2);
});

test("deriveWorkflowBrief omits blocker when it would repeat problem one", () => {
  const structured = {
    ...STRUCTURED,
    biggest_disagreement: "No buyer proof yet.",
  };
  const brief = deriveWorkflowBrief(null, structured, []);
  assert.equal(brief.blocker, null);
  assert.equal(brief.problems[0], "No buyer proof yet.");
});

test("deriveWorkflowBrief uses judge fixes when synthesis has no risks", () => {
  const structured = {
    ...STRUCTURED,
    top_risks: [],
    biggest_disagreement: "Split on go-to-market.",
  };
  const verdicts = [
    { judge: "vc", verdict: "FAIL", score: 2, recommended_fix: "Interview ten buyers." },
  ];
  const brief = deriveWorkflowBrief(null, structured, verdicts);
  assert.deepEqual(brief.problems, ["Interview ten buyers."]);
  assert.equal(brief.blocker, "Split on go-to-market.");
});

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

test("deriveNextActions falls back to judge fixes without structured synthesis", () => {
  const verdicts = [
    {
      judge: "vc",
      verdict: "FAIL",
      score: 3,
      recommended_fix: "Interview ten buyers.",
    },
    {
      judge: "pm",
      verdict: "CONDITIONAL",
      score: 5,
      recommended_fix: "Narrow the wedge.",
    },
  ];
  assert.deepEqual(deriveNextActions(null, null, verdicts), [
    "Interview ten buyers.",
    "Narrow the wedge.",
  ]);
});

test("deriveNextActions prefers synthesis risks over fixes", () => {
  const parsed = parseStructuredSynthesis(STRUCTURED);
  assert.ok(parsed);
  assert.deepEqual(
    deriveNextActions(null, STRUCTURED, [
      { judge: "vc", verdict: "FAIL", score: 2, recommended_fix: "Ignored when risks exist." },
    ]),
    ["No buyer proof yet.", "Long sales cycles."],
  );
});

test("collectRecommendedFixes ranks FAIL before PASS", () => {
  const fixes = collectRecommendedFixes([
    { verdict: "PASS", score: 8, recommended_fix: "Ship faster." },
    { verdict: "FAIL", score: 2, recommended_fix: "Prove demand." },
  ]);
  assert.deepEqual(fixes, ["Prove demand.", "Ship faster."]);
});

test("deriveNextActions caps at three risks", () => {
  const structured = {
    ...STRUCTURED,
    top_risks: ["Risk A.", "Risk B.", "Risk C.", "Risk D."],
  };
  assert.deepEqual(
    deriveNextActions(null, structured, []),
    ["Risk A.", "Risk B.", "Risk C."],
  );
});

test("deriveNextActions dedupes identical fixes", () => {
  const sameFix = "Interview ten buyers.";
  assert.deepEqual(
    deriveNextActions(null, null, [
      { judge: "vc", verdict: "FAIL", score: 2, recommended_fix: sameFix },
      { judge: "pm", verdict: "FAIL", score: 3, recommended_fix: sameFix },
      { judge: "customer", verdict: "CONDITIONAL", score: 5, recommended_fix: "Other fix." },
    ]),
    [sameFix, "Other fix."],
  );
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
