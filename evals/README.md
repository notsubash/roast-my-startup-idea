# Evaluation Guide

How to run evals for **Roast My Startup**, what each tier does, and when to use it.

## Overview

| Tier | When | Cost | What it checks |
|------|------|------|----------------|
| **0 — CI** | Every PR | $0 | Orchestration, schema, structural baselines |
| **1 — Local run** | Before prompt/model changes | $0 (Ollama) | Pipeline completes; all judges + debate + appeals run |
| **2 — DeepSeek audit** | Monthly | ~$0.50–2 | Quality via **one LLM-as-judge call per idea** |

Quality judgement uses DeepSeek with prompts in [`src/prompts/eval_grader_*.jinja2`](../src/prompts/) — not keyword heuristics.

---

## Prerequisites

- Python deps: `pip install -r requirements.txt`
- **Tier 1:** Ollama running with your `LOCAL_MODEL` (default `qwen3.5:9b`)
- **Tier 2:** `DEEPSEEK_API_KEY` in `.env` or GitHub secrets

---

## Tier 0 — CI (automatic)

Runs on every push/PR:

```bash
python -m unittest discover -s tests
```

Includes `tests/test_eval_regression.py` — validates golden dataset and structural baselines in `evals/dataset/baselines/latest/`.

---

## Tier 1 — Golden set (local or DeepSeek)

**Run when:** you change prompts, models, or pipeline code.

**What it does:** runs the real production pipeline on ideas from `evals/dataset/golden_ideas.jsonl` and checks structural reliability (all judges returned, debate completed, schema valid). Does **not** judge roast quality.

Choose the pipeline LLM with `--runtime`:

| Runtime | When to use | Requirements |
|---------|-------------|--------------|
| `local` | Default; $0 smoke/regression on Ollama | Ollama + `LOCAL_MODEL` |
| `deepseek` | Faster baseline refresh; same pipeline via API | `DEEPSEEK_API_KEY` in `.env` |

```bash
# Quick smoke — 3 ideas (~30–90 min local; ~5–15 min DeepSeek)
python -m evals.run_eval --runtime local
python -m evals.run_eval --runtime deepseek

# Full golden set — all 12 ideas + appeals
python -m evals.run_eval --runtime local --full
python -m evals.run_eval --runtime deepseek --full

# Refresh the 3 committed baselines (pick runtime)
python -m evals.run_eval --runtime local --ideas smartpatch,metrics_strong,compliance_copilot --write-baselines
python -m evals.run_eval --runtime deepseek --ideas smartpatch,metrics_strong,compliance_copilot --write-baselines

# Same via write_baselines helper
python -m evals.dataset.write_baselines --runtime synthetic   # fast CI fixtures (default)
python -m evals.dataset.write_baselines --runtime deepseek    # live pipeline → baselines/latest/

# Faster smoke: skip appeals and reduce debate rounds
python -m evals.run_eval --runtime local --no-appeals --debate-rounds 2
python -m evals.run_eval --runtime deepseek --no-appeals --debate-rounds 2

# Specific ideas only
python -m evals.run_eval --runtime local --ideas smartpatch,compliance_copilot

# Skip appeals (faster)
python -m evals.run_eval --runtime local --full --no-appeals
```

### Logging

Evals log progress to stderr by default:

```bash
# Verbose debate speaker output
python -m evals.run_eval --runtime local --log-level DEBUG

# Or via environment
LOG_LEVEL=DEBUG python -m evals.run_eval --runtime local
LOG_FILE=evals/results/eval.log python -m evals.run_eval --runtime local --full
```

You'll see per-idea phase transitions (roast → debate → appeals), judge completions, and elapsed time so a long run doesn't look stuck.

Reports: `evals/results/local/<timestamp>.json` and `.md` (gitignored).

**Pass criteria:** `pass_rate` = 1.0 (all ideas structurally complete). Block prompt merges if any idea fails.

### Refresh committed baselines

After prompt changes that intentionally alter outputs:

```bash
# Live pipeline (choose runtime)
python -m evals.run_eval --runtime local --full --write-baselines
python -m evals.run_eval --runtime deepseek --ideas smartpatch,metrics_strong,compliance_copilot --write-baselines

# Or regenerate fast synthetic CI fixtures (no LLM):
python -m evals.dataset.write_baselines --runtime synthetic
git add evals/dataset/baselines/latest/
```

Commit baseline JSON so the monthly audit and CI have inputs to grade.

---

## Tier 2 — Monthly DeepSeek audit

**Run when:** once a month (or after refreshing baselines post-prompt-change).

**What it does:** sends each idea's full output to DeepSeek in **one structured call** — persona, debate, synthesis, and appeal quality graded together. Cost-effective vs multiple calls per phase.

```bash
# Estimate tokens/calls without spending
python -m evals.run_audit --dry-run --no-reuse-last-local --baseline-only

# Grade committed baselines (recommended default — 3 ideas, ~3 API calls)
python -m evals.run_audit --no-reuse-last-local --baseline-only

# Grade latest local run instead of baselines
python -m evals.run_audit --reuse-last-local

# Re-run pipeline on full golden set, then grade (slow + costs more)
python -m evals.run_audit --refresh-local --runtime local
python -m evals.run_audit --refresh-local --runtime deepseek
```

Reports: `evals/results/audits/<timestamp>.json` (gitignored).

**Regression signals:** compare to prior audit — any dimension drop ≥ 0.5, or a gate newly failing. See report `regressions` array.

Scheduled automatically on the **1st of each month** via `.github/workflows/eval-audit.yml` (requires `DEEPSEEK_API_KEY` secret).

---

## Decision tree

```
Changed code?
├─ Yes → Tier 0 (CI) must pass
├─ Changed prompts/models?
│   ├─ Yes → Tier 1 full local eval
│   │        └─ Pass? → refresh baselines → commit
│   └─ Monthly or post-baseline refresh → Tier 2 audit
└─ No → nothing required
```

---

## Human calibration (optional, quarterly)

See [HUMAN_REVIEW.md](HUMAN_REVIEW.md). Spot-check 5 audit outputs; store labels in `evals/results/human_labels.jsonl`.

---

## File map

```
evals/
  dataset/
    golden_ideas.jsonl       # 12 test ideas + expected topics
    baselines/latest/        # Committed outputs for CI + monthly audit
  run_eval.py                # Tier 1 CLI
  run_audit.py               # Tier 2 CLI
  grader/deepseek_judge.py   # Single-call LLM grader
  scorers/reliability.py     # Tier 1 structural checks only
  results/                   # Local + audit reports (gitignored)
src/prompts/
  eval_grader_system.jinja2  # Grader system prompt
  eval_grader_user.jinja2    # Grader user prompt (all phases in one)
```
