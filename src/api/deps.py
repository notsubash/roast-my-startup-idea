"""Shared FastAPI dependencies and run helpers."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
import logging
import os

from api.schemas import CreateRunRequest
from config import Settings, get_settings
from idea_context import (
    build_startup_idea_context as _build_startup_idea_context,
)
from idea_context import (
    idea_display_summary,
)
from modeling import build_chat_model
from research.service import (
    ResearchContext,
    TavilyHttpClient,
    build_research_context,
    decide_web_search_usage,
)

logger = logging.getLogger(__name__)


@dataclass
class RunRecord:
    run_id: str
    request: CreateRunRequest
    status: str = "created"
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


def get_app_settings() -> Settings:
    return get_settings()


def get_cors_origins() -> list[str]:
    raw = os.getenv(
        "ROAST_CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    )
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def build_idea_preview(idea: str, *, max_length: int = 120) -> str:
    return idea_display_summary(idea, max_chars=max_length)


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
) -> ResearchContext | None:
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

        return build_research_context(
            startup_idea=startup_idea,
            tavily_client=TavilyHttpClient(tavily_key),
            max_results=settings.web_search_max_results,
            enabled=True,
            decision=search_decision,
        )
    except Exception as exc:
        logger.warning("Web research skipped for API run: %s", exc)
        return None


_idea_store = None


def get_idea_store():
    from memory.factory import build_idea_store
    from memory.identity import get_local_user_id

    global _idea_store
    if _idea_store is None:
        _idea_store = build_idea_store()
        get_local_user_id(_idea_store)
    return _idea_store
