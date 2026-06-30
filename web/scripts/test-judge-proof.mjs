import assert from "node:assert/strict";
import test from "node:test";

import { findDuplicateEvidenceJudges } from "../src/lib/appeal/coaching.ts";
import { JUDGE_META } from "../src/lib/sse/judges.ts";
import { JUDGE_ORDER } from "../src/lib/sse/types.ts";

test("every judge has a concise lens tag", () => {
  for (const id of JUDGE_ORDER) {
    const tag = JUDGE_META[id].lensTag;
    assert.ok(tag.length > 0 && tag.length <= 24, `${id} lensTag: ${tag}`);
  }
});

test("findDuplicateEvidenceJudges flags normalized ask collisions", () => {
  const sharedAsk = "Three signed LOIs would change this verdict.";
  const verdicts = [
    {
      judge: "vc",
      verdict: "CONDITIONAL",
      roast: "x",
      score: 4,
      key_concern: "a",
      evidence_to_change_verdict: sharedAsk,
    },
    {
      judge: "customer",
      verdict: "FAIL",
      roast: "x",
      score: 3,
      key_concern: "b",
      evidence_to_change_verdict: sharedAsk,
    },
    {
      judge: "engineer",
      verdict: "PASS",
      roast: "x",
      score: 8,
      key_concern: "c",
      evidence_to_change_verdict: "Ship a working prototype with latency under 200ms.",
    },
  ];
  const duplicates = findDuplicateEvidenceJudges(verdicts);
  assert.equal(duplicates.has("vc"), true);
  assert.equal(duplicates.has("customer"), true);
  assert.equal(duplicates.has("engineer"), false);
});

test("findDuplicateEvidenceJudges is case-insensitive", () => {
  const verdicts = [
    {
      judge: "pm",
      verdict: "CONDITIONAL",
      roast: "x",
      score: 5,
      key_concern: "a",
      evidence_to_change_verdict: "Show 10 paid pilots.",
    },
    {
      judge: "competitor",
      verdict: "FAIL",
      roast: "x",
      score: 3,
      key_concern: "b",
      evidence_to_change_verdict: "show 10 paid pilots.",
    },
  ];
  const duplicates = findDuplicateEvidenceJudges(verdicts);
  assert.equal(duplicates.size, 2);
});

test("findDuplicateEvidenceJudges flags near-paraphrase evidence asks", () => {
  const leftAsk =
    "Three signed LOIs from enterprise buyers with fifty thousand ACV";
  const nearAsk =
    "Three signed LOIs from enterprise buyers with fifty thousand ACV each";
  const verdicts = [
    {
      judge: "vc",
      verdict: "CONDITIONAL",
      roast: "x",
      score: 4,
      key_concern: "a",
      evidence_to_change_verdict: leftAsk,
    },
    {
      judge: "engineer",
      verdict: "FAIL",
      roast: "x",
      score: 3,
      key_concern: "b",
      evidence_to_change_verdict: nearAsk,
    },
    {
      judge: "pm",
      verdict: "PASS",
      roast: "x",
      score: 8,
      key_concern: "c",
      evidence_to_change_verdict: "Ten ICP interviews naming workflow pain.",
    },
  ];
  const duplicates = findDuplicateEvidenceJudges(verdicts);
  assert.equal(duplicates.has("vc"), true);
  assert.equal(duplicates.has("engineer"), true);
  assert.equal(duplicates.has("pm"), false);
});

test("findDuplicateEvidenceJudges flags derived-hint collisions", () => {
  const sharedConcern = "No signed LOIs yet.";
  const verdicts = [
    {
      judge: "vc",
      verdict: "CONDITIONAL",
      roast: "x",
      score: 4,
      key_concern: sharedConcern,
      evidence_to_change_verdict: undefined,
    },
    {
      judge: "customer",
      verdict: "FAIL",
      roast: "x",
      score: 3,
      key_concern: sharedConcern,
      evidence_to_change_verdict: undefined,
    },
  ];
  const duplicates = findDuplicateEvidenceJudges(verdicts);
  assert.equal(duplicates.has("vc"), true);
  assert.equal(duplicates.has("customer"), true);
});
