import assert from "node:assert/strict";
import {
  concernAddressedStatus,
  fixStatusLabel,
  groupByLineage,
  recommendedFixStatus,
  sidebarLineageVersions,
} from "../src/lib/lineage/lineage.ts";

const baseVerdict = {
  judge: "vc",
  verdict: "FAIL",
  roast: "Distribution is expensive and the market does not look venture scale.",
  score: 3,
  key_concern: "No urgent buyer.",
};

const improved = {
  ...baseVerdict,
  score: 5,
  key_concern: "Still unclear ICP.",
};

assert.equal(concernAddressedStatus(baseVerdict, improved), "Likely addressed");
assert.equal(
  concernAddressedStatus(
    { ...baseVerdict, score: 6 },
    { ...baseVerdict, score: 4, key_concern: "Buyer still unclear." },
  ),
  "Still open",
);
assert.equal(
  concernAddressedStatus(
    { ...baseVerdict, verdict: "FAIL", score: 4 },
    { ...baseVerdict, verdict: "CONDITIONAL", score: 4, key_concern: "ICP still fuzzy." },
  ),
  "Likely addressed",
);
assert.equal(
  recommendedFixStatus({ ...baseVerdict, recommended_fix: "Run five buyer interviews." }, improved),
  "Likely addressed",
);
assert.equal(
  recommendedFixStatus(
    { ...baseVerdict, recommended_fix: "Run five buyer interviews.", score: 5 },
    { ...baseVerdict, score: 3 },
  ),
  "Still open",
);
assert.equal(recommendedFixStatus(baseVerdict, improved), null);
assert.equal(fixStatusLabel("Concern shifted"), "Status unclear");

const runs = [1, 2, 3, 4, 5].map((version) => ({
  run_id: `run-${version}`,
  status: "completed",
  idea_preview: `Pitch v${version}`,
  created_at: `2026-01-0${version}T12:00:00Z`,
  version,
  parent_run_id: version > 1 ? `run-${version - 1}` : null,
}));

const { visible, hidden } = sidebarLineageVersions(
  runs.sort((a, b) => a.version - b.version),
);
assert.deepEqual(visible.map((r) => r.version), [4, 5]);
assert.deepEqual(hidden.map((r) => r.version), [1, 2, 3]);

const grouped = groupByLineage(runs);
assert.equal(grouped.length, 1);
assert.deepEqual(grouped[0].map((r) => r.version), [1, 2, 3, 4, 5]);

console.log("test-lineage: ok");
