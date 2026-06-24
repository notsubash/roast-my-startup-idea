from dataclasses import dataclass
from functools import lru_cache
import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROMPTS_DIR = PROJECT_ROOT / "src" / "prompts"

JUDGE_ORDER = ["vc", "engineer", "pm", "customer", "competitor"]

DEBATE_PERSONAS = {
    "vc": "A blunt VC. Focus on market size, moat, CAC, scalability, and fundability.",
    "engineer": "A senior staff engineer. Focus on feasibility, complexity, reliability, and technical differentiation.",
    "pm": "A principal product manager. Focus on ICP, pain, positioning, prioritization, and product-market fit.",
    "customer": "An impatient target customer. Focus on willingness to pay, friction, alternatives, and urgency.",
    "competitor": "An incumbent competitor. Focus on defensibility, replication risk, switching costs, and market position.",
}


@dataclass(frozen=True)
class Settings:
    local_model: str
    deepseek_model: str
    deepseek_base_url: str
    max_debate_rounds: int
    enable_web_search: bool
    web_search_max_results: int


def _read_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@lru_cache
def get_settings() -> Settings:
    load_dotenv(PROJECT_ROOT / ".env")
    return Settings(
        local_model=os.getenv("LOCAL_MODEL", "ollama:qwen3.5:9b"),
        deepseek_model=os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash"),
        deepseek_base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        max_debate_rounds=int(os.getenv("MAX_DEBATE_ROUNDS", "3")),
        enable_web_search=_read_bool("ENABLE_WEB_SEARCH", False),
        web_search_max_results=int(os.getenv("WEB_SEARCH_MAX_RESULTS", "3")),
    )
