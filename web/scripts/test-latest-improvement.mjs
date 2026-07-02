import assert from "node:assert/strict";
import {
  deriveLatestImprovementFromAppeal,
  deriveLatestImprovementFromVersionDiff,
  hasAppealMovement,
} from "../src/lib/lineage/latest-improvement.ts";
import { computeVersionDiff } from "../src/lib/lineage/version-diff.ts";

const prior = [
  {
    judge: "customer",
    verdict: "FAIL",
    roast: "No pay.",
    score: 3,
    key_concern: "No willingness to pay.",
    evidence_to_change_verdict: "Show LOIs.",
  },
  {
    judge: "pm",
    verdict: "CONDITIONAL",
    roast: "ICP fuzzy.",
    score: 5,
    key_concern: "Buyer unclear.",
  },
  {
    judge: "vc",
    verdict: "FAIL",
    roast: "Small market.",
    score: 4,
    key_concern: "TAM too small.",
  },
  {
    judge: "engineer",
    verdict: "PASS",
    roast: "Fine.",
    score: 7,
    key_concern: "Ops risk.",
  },
  {
    judge: "competitor",
    verdict: "FAIL",
    roast: "Crowded.",
    score: 4,
    key_concern: "Incumbents dominate.",
  },
];

const improved = prior.map((verdict) =>
  verdict.judge === "customer"
    ? { ...verdict, score: 6, key_concern: "Pricing still unproven." }
    : verdict,
);

const diff = computeVersionDiff(prior, improved);
assert.ok(diff);

const versionImprovement = deriveLatestImprovementFromVersionDiff(diff);
assert.ok(versionImprovement);
assert.equal(versionImprovement.kind, "version");
assert.ok(versionImprovement.scoreDelta != null && versionImprovement.scoreDelta > 0);
assert.ok(versionImprovement.summary.length > 0);

const flat = computeVersionDiff(prior, prior);
assert.ok(flat);
assert.equal(deriveLatestImprovementFromVersionDiff(flat), null);

const appealWithMovement = {
  appealText: "We signed two LOIs.",
  originalByJudge: { customer: prior[0] },
  revisedByJudge: { customer: { ...prior[0], score: 6 } },
  revisedSynthesis:
    "**Recommendation:** ITERATE\n\n**Confidence:** MEDIUM\n\n**Biggest disagreement:** Split on wedge.",
  targetJudges: ["customer"],
  evidenceOutcomes: [
    {
      judge: "customer",
      evidenceAsk: "Show LOIs.",
      outcome: "Evidence met",
      targeted: true,
      scoreDelta: 3,
    },
  ],
};

assert.equal(hasAppealMovement(appealWithMovement), true);
const evidenceImprovement = deriveLatestImprovementFromAppeal(appealWithMovement);
assert.ok(evidenceImprovement);
assert.equal(evidenceImprovement.kind, "evidence");
assert.equal(evidenceImprovement.scoreDelta, 3);
assert.ok(evidenceImprovement.summary.includes("met"));

const flatAppeal = {
  ...appealWithMovement,
  revisedByJudge: { customer: prior[0] },
  evidenceOutcomes: [
    {
      judge: "customer",
      evidenceAsk: "Show LOIs.",
      outcome: "Evidence not met",
      targeted: true,
      scoreDelta: 0,
    },
  ],
};

assert.equal(hasAppealMovement(flatAppeal), false);
assert.equal(deriveLatestImprovementFromAppeal(flatAppeal), null);

console.log("test-latest-improvement: ok");
