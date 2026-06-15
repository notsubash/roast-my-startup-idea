from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import os
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
    max_debate_rounds: int

@lru_cache
def get_settings() -> Settings:
    load_dotenv(PROJECT_ROOT / ".env")
    return Settings(
        local_model=os.getenv("LOCAL_MODEL", "ollama:qwen3.5:9b"),
        max_debate_rounds=int(os.getenv("MAX_DEBATE_ROUNDS", "3")),
    )