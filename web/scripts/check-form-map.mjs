/** ponytail: runnable guard — keep mapping logic in sync with to-create-run-request.ts */
import assert from "node:assert/strict";

function toCreateRunRequest(values) {
  const competitors = (values.competitorsText ?? "")
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);

  const request = {
    idea: values.idea.trim(),
    model_runtime: values.model_runtime,
    execution_flow: "deterministic",
    max_debate_rounds: values.max_debate_rounds,
    enable_web_search: values.enable_web_search,
  };

  const targetCustomer = values.target_customer?.trim();
  const pricing = values.pricing?.trim();
  const traction = values.traction?.trim();

  if (targetCustomer) request.target_customer = targetCustomer;
  if (pricing) request.pricing = pricing;
  if (traction) request.traction = traction;
  if (competitors.length > 0) request.competitors = competitors;

  return request;
}

const payload = toCreateRunRequest({
  idea: "A marketplace for vintage synthesizers with escrow.",
  competitorsText: "Reverb\n\n Sweetwater \n",
  target_customer: "  ",
  model_runtime: "local",
  max_debate_rounds: 5,
  enable_web_search: true,
});

assert.equal(payload.execution_flow, "deterministic");
assert.deepEqual(payload.competitors, ["Reverb", "Sweetwater"]);
assert.equal(payload.target_customer, undefined);
assert.equal(payload.model_runtime, "local");
assert.equal(payload.max_debate_rounds, 5);
assert.equal(payload.enable_web_search, true);

console.log("check-form-map: ok");
