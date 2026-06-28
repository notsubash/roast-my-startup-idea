import assert from "node:assert/strict";
import test from "node:test";

import { parseSynthesis, splitBulletBody } from "../src/features/run/synthesis-format.ts";

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
