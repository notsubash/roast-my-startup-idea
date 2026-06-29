import assert from "node:assert/strict";
import test from "node:test";

import {
  appealEvidenceOutcome,
  appealJudgeOutcomes,
  appealScoreMovement,
  assessAppealCoaching,
  isGenericEvidence,
  normalizeTargetJudges,
} from "../src/lib/appeal/coaching.ts";

const BASELINE = {
  judge: "vc",
  verdict: "CONDITIONAL",
  roast: "Needs proof.",
  score: 4,
  key_concern: "No LOIs yet.",
  evidence_to_change_verdict: "Three signed LOIs would change this verdict.",
};

test("normalizeTargetJudges keeps panel order and drops unknown ids", () => {
  assert.deepEqual(normalizeTargetJudges(["customer", "vc", "unknown"]), ["vc", "customer"]);
  assert.deepEqual(normalizeTargetJudges(undefined), []);
});

test("appealEvidenceOutcome follows score delta", () => {
  assert.equal(
    appealEvidenceOutcome(BASELINE, { ...BASELINE, score: 6 }),
    "Evidence met",
  );
  assert.equal(
    appealEvidenceOutcome(BASELINE, { ...BASELINE, score: 4 }),
    "Not met",
  );
  assert.equal(
    appealEvidenceOutcome(
      { ...BASELINE, verdict: "PASS", score: 8 },
      { ...BASELINE, verdict: "PASS", score: 8 },
    ),
    "Already passing",
  );
});

test("appealJudgeOutcomes marks targeted judges", () => {
  const revised = { ...BASELINE, score: 6 };
  const outcomes = appealJudgeOutcomes([BASELINE], [revised], ["vc"]);
  assert.equal(outcomes.length, 1);
  assert.equal(outcomes[0]?.targeted, true);
  assert.equal(outcomes[0]?.outcome, "Evidence met");
});

test("assessAppealCoaching flags generic and duplicate asks", () => {
  const verdicts = [
    { ...BASELINE, judge: "vc", evidence_to_change_verdict: "Show traction with signed LOIs." },
    { ...BASELINE, judge: "engineer", key_concern: "No moat.", evidence_to_change_verdict: undefined },
    { ...BASELINE, judge: "pm", evidence_to_change_verdict: "Do more research on the buyer." },
    { ...BASELINE, judge: "customer", evidence_to_change_verdict: "Three signed LOIs would change this verdict." },
    { ...BASELINE, judge: "competitor", evidence_to_change_verdict: "Three signed LOIs would change this verdict." },
  ];
  const coaching = assessAppealCoaching(verdicts);
  assert.equal(coaching.degraded, true);
  assert.equal(coaching.items.find((item) => item.judge === "engineer")?.quality, "derived");
  assert.equal(coaching.items.find((item) => item.judge === "pm")?.quality, "generic");
  assert.equal(coaching.items.find((item) => item.judge === "customer")?.quality, "duplicate");
  assert.equal(isGenericEvidence("Show traction with signed LOIs."), false);
  assert.equal(isGenericEvidence("Do more research on the buyer."), true);
});

test("appealScoreMovement counts positive moves", () => {
  const baseline = [
    { ...BASELINE, judge: "vc", score: 4 },
    { ...BASELINE, judge: "engineer", score: 4 },
  ];
  const revised = [
    { ...BASELINE, judge: "vc", score: 6 },
    { ...BASELINE, judge: "engineer", score: 4 },
  ];
  assert.deepEqual(appealScoreMovement(baseline, revised), {
    positiveMoves: 1,
    netDelta: 2,
  });
});
