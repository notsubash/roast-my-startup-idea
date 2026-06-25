"""Shared FastAPI dependencies and in-memory run registry."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
import logging
import os
from threading import Lock
from uuid import uuid4

from api.schemas import CreateRunRequest
from config import Settings, get_settings
from idea_context import build_startup_idea_context as _build_startup_idea_context
from modeling import build_chat_model
from research.service import (
    TavilyHttpClient,
    build_research_context,
    decide_web_search_usage,
    format_research_context,
)

logger = logging.getLogger(__name__)


@dataclass
class RunRecord:
    run_id: str
    request: CreateRunRequest
    status: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class RunRegistry:
    # ponytail: in-memory, per-process, no eviction — fine for dev/single-worker uvicorn;
    # upgrade path: SQLite/Redis + TTL for stale "running" runs after crashes.
    def __init__(self) -> None:
        self._runs: dict[str, RunRecord] = {}
        self._lock = Lock()

    def create(self, request: CreateRunRequest) -> RunRecord:
        run_id = str(uuid4())
        record = RunRecord(run_id=run_id, request=request, status="created")
        with self._lock:
            self._runs[run_id] = record
        return record

    def get(self, run_id: str) -> RunRecord | None:
        with self._lock:
            return self._runs.get(run_id)

    def try_claim(self, run_id: str) -> bool:
        with self._lock:
            record = self._runs.get(run_id)
            if record is None or record.status != "created":
                return False
            record.status = "running"
            return True

    def mark_completed(self, run_id: str) -> None:
        with self._lock:
            record = self._require_unlocked(run_id)
            record.status = "completed"

    def mark_failed(self, run_id: str) -> None:
        with self._lock:
            record = self._require_unlocked(run_id)
            record.status = "failed"

    def _require_unlocked(self, run_id: str) -> RunRecord:
        record = self._runs.get(run_id)
        if record is None:
            raise KeyError(run_id)
        return record


# ponytail: module singleton — multi-worker uvicorn needs shared storage or sticky sessions.
_registry = RunRegistry()


def get_run_registry() -> RunRegistry:
    return _registry


def get_app_settings() -> Settings:
    return get_settings()


def get_cors_origins() -> list[str]:
    raw = os.getenv(
        "ROAST_CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    )
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def build_idea_preview(idea: str, *, max_length: int = 120) -> str:
    text = idea.strip().replace("\n", " ")
    if len(text) <= max_length:
        return text
    return text[: max_length - 3].rstrip() + "..."


def build_startup_idea_context(request: CreateRunRequest) -> str:
    return _build_startup_idea_context(
        request.idea,
        target_customer=request.target_customer,
        pricing=request.pricing,
        traction=request.traction,
        competitors=request.competitors or None,
    )


def build_model_for_run(request: CreateRunRequest, settings: Settings):
    return build_chat_model(
        request.model_runtime,
        settings,
        os.getenv("DEEPSEEK_API_KEY"),
    )


def build_research_context_for_run(
    request: CreateRunRequest,
    startup_idea: str,
    settings: Settings,
    model,
) -> str | None:
    if not request.enable_web_search:
        return None

    tavily_key = os.getenv("TAVILY_API_KEY")
    if not tavily_key:
        return None

    try:
        search_decision = decide_web_search_usage(
            policy_model=model,
            startup_idea=startup_idea,
        )
        if not search_decision.use_search:
            return None

        research = build_research_context(
            startup_idea=startup_idea,
            tavily_client=TavilyHttpClient(tavily_key),
            max_results=settings.web_search_max_results,
            enabled=True,
            decision=search_decision,
        )
        if research is None:
            return None
        return format_research_context(research)
    except Exception:
        logger.exception("Web research failed for API run")
        return None
