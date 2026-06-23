"""Evaluation harness for Roast My Startup (Tier 1 local + Tier 2 DeepSeek audit)."""

from pathlib import Path

EVAL_RUNTIMES = ("local", "deepseek")
BASELINE_SOURCES = ("synthetic", *EVAL_RUNTIMES)

EVALS_ROOT = Path(__file__).resolve().parent
DATASET_DIR = EVALS_ROOT / "dataset"
GOLDEN_IDEAS_PATH = DATASET_DIR / "golden_ideas.jsonl"
BASELINES_DIR = DATASET_DIR / "baselines" / "latest"
RESULTS_LOCAL_DIR = EVALS_ROOT / "results" / "local"
RESULTS_AUDITS_DIR = EVALS_ROOT / "results" / "audits"
