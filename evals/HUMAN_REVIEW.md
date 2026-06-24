# Human Review Rubric (Tier 3 Calibration)

Use this checklist quarterly (~30 minutes) to calibrate the monthly DeepSeek LLM grader. Spot-check **5 audit outputs** from `evals/results/audits/`.

Grader prompts live in `src/prompts/eval_grader_system.jinja2` and `src/prompts/eval_grader_user.jinja2`. If human scores diverge from DeepSeek by >1 point on average, revise those prompts — not the product prompts.

## Setup

1. Pick the 5 most recent audit JSON files (or the latest file’s first 5 ideas).
2. Open the corresponding baseline or local run in `evals/dataset/baselines/latest/`.
3. Record scores in `evals/results/human_labels.jsonl` (one JSON object per line).

## Label Format

```json
{
  "audit_timestamp": "20260623_120000",
  "idea_id": "smartpatch",
  "reviewer": "your_name",
  "scores": {
    "persona_consistency": 4,
    "roast_specificity": 4,
    "debate_engagement": 3,
    "synthesis_faithfulness": 4,
    "appeal_calibration": 4
  },
  "notes": "Engineer stayed in role; synthesis softened VC dissent too much."
}
```

All scores are **1–5** (1=poor, 5=excellent).

## Review Checklist (per idea)

### Phase 1 — Roasts

- [ ] Did each judge sound like their persona (VC / Engineer / PM / Customer / Competitor)?
- [ ] Were roasts specific to the idea (not generic startup advice)?
- [ ] Did verdict labels match the severity of the roast?

### Phase 2 — Debate

- [ ] Did judges reference each other’s arguments (not talk past one another)?
- [ ] Did later rounds add new points instead of repeating round 1?

### Moderator Synthesis

- [ ] Did the synthesis reflect the main concerns from Phase 1?
- [ ] Was meaningful disagreement preserved (not falsely unified)?

### Appeal Mode (if present)

- [ ] Did weak appeals fail to move scores inappropriately?
- [ ] Did strong appeals with evidence produce reasonable score shifts?

## Calibration Rule

Compare your human scores to DeepSeek grader dimensions in the audit JSON:

- If average absolute delta **> 1.0** across 5 ideas → revise grader prompts in `src/prompts/eval_grader_*.jinja2`.
- If DeepSeek scores are low but outputs look good → grader may be too harsh; adjust rubric wording.

Do **not** change product prompts based on a single human review session.

## Pairwise Prompt Comparison (optional)

When changing product prompts, run the same 5 ideas before and after, then pick a winner per idea:

```json
{
  "idea_id": "smartpatch",
  "winner": "after",
  "reason": "Engineer roast cited calibration limits with concrete mechanism."
}
```

Store pairwise results in the same `human_labels.jsonl` file with a `"type": "pairwise"` field.
