import assert from "node:assert/strict";
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

const current = [
  {
    ...prior[0],
    score: 6,
    key_concern: "Pricing still unproven.",
    evidence_to_change_verdict: "Signed two pilot contracts.",
  },
  {
    ...prior[1],
    score: 6,
    key_concern: "SMB payroll teams only.",
  },
  {
    ...prior[2],
    score: 4,
    key_concern: "TAM too small.",
  },
  {
    ...prior[3],
    score: 7,
    key_concern: "Ops risk.",
  },
  {
    ...prior[4],
    score: 5,
    key_concern: "Differentiation improving.",
  },
];

const diff = computeVersionDiff(prior, current);
assert.ok(diff);
assert.ok(diff.scoreDelta > 0);
assert.ok(diff.removed.some((item) => item.text.includes("willingness")));
assert.ok(diff.added.some((item) => item.judge === "pm" && item.text.includes("SMB")));
assert.ok(diff.evidenceAdded.some((item) => item.text.includes("pilot")));
assert.match(diff.reasonSummary, /improved|addressed/i);

const sameConcernPrior = [
  {
    judge: "customer",
    verdict: "FAIL",
    roast: "No pay.",
    score: 4,
    key_concern: "No willingness to pay.",
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

const sameConcernCurrent = sameConcernPrior.map((verdict) =>
  verdict.judge === "customer" ? { ...verdict, score: 6 } : verdict,
);

const sameConcernDiff = computeVersionDiff(sameConcernPrior, sameConcernCurrent);
assert.ok(sameConcernDiff);
assert.equal(sameConcernDiff.removed.length, 0);
assert.ok(sameConcernDiff.scoreDelta > 0);

console.log("test-version-diff: ok");
