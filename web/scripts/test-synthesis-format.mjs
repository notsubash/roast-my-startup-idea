import assert from "node:assert/strict";
import test from "node:test";

import { parseAppealSynthesis, parseSynthesis, splitBulletBody } from "../src/features/run/synthesis-format.ts";

test("parseSynthesis splits glued markdown sections", () => {
  const raw =
    "**1. Overall verdict:** FAIL **2. Final score from 1-10:** 2.5 **3. Consensus points** - Tech is hard - Market is crowded **4. Main disagreements** - VC vs Engineer **5. Best next steps for the startup founder** - Pivot to patches";
  const parsed = parseSynthesis(raw);
  assert.equal(parsed?.verdict, "FAIL");
  assert.equal(parsed?.score, "2.5");
  assert.equal(parsed?.sections.length, 3);
  assert.deepEqual(parsed?.sections[0].bullets, ["Tech is hard", "Market is crowded"]);
});

test("splitBulletBody handles newline bullets", () => {
  assert.deepEqual(splitBulletBody("- One\n- Two"), ["One", "Two"]);
});

test("parseAppealSynthesis parses overall verdict and sections", () => {
  const raw =
    "**Overall Verdict:** CONDITIONAL (Revised Score: 4.5/10, *unchanged*)\n\n**What Changed (Improvements in the Appeal)**\n- **Privacy architecture is now explicit:** On-device first processing.\n- **ICP narrowed:** Focus on parents.\n\n**What Did Not Change (Persistent Weaknesses)**\n- **Technical feasibility is still unproven:** No benchmarks.";
  const parsed = parseAppealSynthesis(raw);
  assert.equal(parsed?.verdict, "CONDITIONAL");
  assert.equal(parsed?.score, "4.5");
  assert.equal(parsed?.sections.length, 2);
  assert.match(parsed?.sections[0].bullets[0], /Privacy architecture/);
});

test("parseAppealSynthesis parses lowercase section headers", () => {
  const raw =
    "**What changed:**\n- The founder's appeal consisted of a single statement.\n\n**What did not change:**\n- All five panelists maintained or lowered their scores.";
  const parsed = parseAppealSynthesis(raw);
  assert.equal(parsed?.sections.length, 2);
  assert.equal(parsed?.sections[0].title, "What changed");
});
