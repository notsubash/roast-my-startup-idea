"""Run-level cost and latency metrics for the live pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import logging
import threading
import time
from typing import Any, Literal

logger = logging.getLogger(__name__)

ModelRuntime = Literal["local", "deepseek"]

# ponytail: static per-1M-token rates for demo cost estimates; upgrade path is
# env-driven pricing or a model catalog keyed by provider + model id.
_COST_PER_MILLION: dict[ModelRuntime, dict[str, float]] = {
    "deepseek": {"input": 0.14, "output": 0.28},
    "local": {"input": 0.0, "output": 0.0},
}


def estimate_tokens_from_text(*texts: str) -> int:
    """Rough token count when providers omit usage metadata."""
    chars = sum(len(text) for text in texts if text)
    return max(0, chars // 4)


def extract_token_usage(response: Any) -> tuple[int, int]:
    """Read input/output token counts from a LangChain response when present."""
    usage = getattr(response, "usage_metadata", None)
    if usage is not None:
        if isinstance(usage, dict):
            input_tokens = int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0)
            output_tokens = int(usage.get("output_tokens") or usage.get("completion_tokens") or 0)
        else:
            input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
            output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
        if input_tokens or output_tokens:
            return input_tokens, output_tokens

    response_metadata = getattr(response, "response_metadata", None) or {}
    if isinstance(response_metadata, dict):
        token_usage = response_metadata.get("token_usage") or {}
        if token_usage:
            input_tokens = int(
                token_usage.get("prompt_tokens") or token_usage.get("input_tokens") or 0
            )
            output_tokens = int(
                token_usage.get("completion_tokens") or token_usage.get("output_tokens") or 0
            )
            return input_tokens, output_tokens

    return 0, 0


def resolve_token_usage(
    response: Any | None,
    *,
    prompt_text: str = "",
    output_text: str = "",
) -> tuple[int, int]:
    input_tokens, output_tokens = extract_token_usage(response) if response is not None else (0, 0)
    if input_tokens or output_tokens:
        return input_tokens, output_tokens
    return estimate_tokens_from_text(prompt_text), estimate_tokens_from_text(output_text)


def estimate_cost_usd(
    input_tokens: int,
    output_tokens: int,
    *,
    model_runtime: ModelRuntime,
) -> float:
    rates = _COST_PER_MILLION.get(model_runtime, _COST_PER_MILLION["local"])
    cost = (input_tokens * rates["input"] + output_tokens * rates["output"]) / 1_000_000
    return round(cost, 6)


@dataclass
class CallMetrics:
    label: str
    phase: Literal["roast", "debate"]
    seconds: float
    input_tokens: int
    output_tokens: int

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def as_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "phase": self.phase,
            "seconds": round(self.seconds, 2),
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
        }


@dataclass
class RunMetricsCollector:
    model_runtime: ModelRuntime = "local"
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _calls: list[CallMetrics] = field(default_factory=list)

    def record_call(
        self,
        *,
        label: str,
        phase: Literal["roast", "debate"],
        seconds: float,
        response: Any | None = None,
        prompt_text: str = "",
        output_text: str = "",
    ) -> None:
        input_tokens, output_tokens = resolve_token_usage(
            response,
            prompt_text=prompt_text,
            output_text=output_text,
        )
        call = CallMetrics(
            label=label,
            phase=phase,
            seconds=seconds,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        with self._lock:
            self._calls.append(call)

    def record_judge(
        self,
        judge: str,
        *,
        seconds: float,
        response: Any | None = None,
        prompt_text: str = "",
        output_text: str = "",
    ) -> None:
        self.record_call(
            label=judge,
            phase="roast",
            seconds=seconds,
            response=response,
            prompt_text=prompt_text,
            output_text=output_text,
        )

    def record_debate(
        self,
        label: str,
        *,
        seconds: float,
        response: Any | None = None,
        prompt_text: str = "",
        output_text: str = "",
    ) -> None:
        self.record_call(
            label=label,
            phase="debate",
            seconds=seconds,
            response=response,
            prompt_text=prompt_text,
            output_text=output_text,
        )

    def discard_phase(self, phase: Literal["roast", "debate"]) -> None:
        """Drop recorded calls for a phase (e.g. before a degenerate-panel retry)."""
        with self._lock:
            self._calls = [call for call in self._calls if call.phase != phase]

    def snapshot(
        self,
        *,
        roast_seconds: float,
        debate_seconds: float,
        total_seconds: float,
    ) -> dict[str, Any]:
        with self._lock:
            calls = list(self._calls)

        input_tokens = sum(call.input_tokens for call in calls)
        output_tokens = sum(call.output_tokens for call in calls)
        total_tokens = input_tokens + output_tokens
        estimated_cost_usd = estimate_cost_usd(
            input_tokens,
            output_tokens,
            model_runtime=self.model_runtime,
        )

        roast_calls = [call.as_dict() for call in calls if call.phase == "roast"]
        debate_calls = [call.as_dict() for call in calls if call.phase == "debate"]

        return {
            "roast_seconds": round(roast_seconds, 2),
            "debate_seconds": round(debate_seconds, 2),
            "total_seconds": round(total_seconds, 2),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "estimated_cost_usd": estimated_cost_usd,
            "model_runtime": self.model_runtime,
            "judge_calls": roast_calls,
            "debate_calls": debate_calls,
        }


def format_run_metrics_footer(metrics: dict[str, Any]) -> str:
    """Human-readable one-liner for UI footers."""
    total_tokens = int(metrics["total_tokens"])
    if total_tokens >= 1000:
        tokens_label = f"~{total_tokens / 1000:.1f}k tokens"
    else:
        tokens_label = f"~{total_tokens} tokens"

    cost = float(metrics["estimated_cost_usd"])
    if cost >= 0.01:
        cost_label = f"~${cost:.2f}"
    elif cost > 0:
        cost_label = f"~${cost:.3f}"
    else:
        cost_label = "~$0.00"

    return (
        f"Roast {metrics['roast_seconds']:.1f}s · "
        f"Debate {metrics['debate_seconds']:.1f}s · "
        f"{tokens_label} · "
        f"{cost_label}"
    )


def format_run_metrics_markdown(metrics: dict[str, Any] | None) -> list[str]:
    """Markdown lines for transcript export."""
    if not metrics:
        return []

    return [
        "## Run Metrics",
        "",
        f"**Summary:** {format_run_metrics_footer(metrics)}",
        "",
        f"- **Roast phase:** {metrics['roast_seconds']:.1f}s wall-clock",
        f"- **Debate phase:** {metrics['debate_seconds']:.1f}s wall-clock",
        f"- **Total time:** {metrics['total_seconds']:.1f}s",
        (
            f"- **Tokens:** {metrics['input_tokens']:,} input / "
            f"{metrics['output_tokens']:,} output ({metrics['total_tokens']:,} total)"
        ),
        f"- **Estimated cost:** ${metrics['estimated_cost_usd']:.4f} ({metrics['model_runtime']})",
        "",
    ]


def log_run_metrics(metrics: dict[str, Any], *, run_id: str | None = None) -> None:
    payload = {"run_id": run_id, **metrics} if run_id else metrics
    logger.info("run_metrics %s", json.dumps(payload, sort_keys=True))


class PhaseTimer:
    """Wall-clock helper lifted from evals/runner.py timing pattern."""

    def __init__(self) -> None:
        self._started_at = time.perf_counter()
        self._phase_started_at = self._started_at
        self.roast_seconds = 0.0
        self.debate_seconds = 0.0

    def start_debate(self) -> None:
        now = time.perf_counter()
        self.roast_seconds = now - self._phase_started_at
        self._phase_started_at = now

    def finish(self, *, in_debate: bool) -> tuple[float, float, float]:
        now = time.perf_counter()
        if in_debate:
            self.debate_seconds = now - self._phase_started_at
        else:
            self.roast_seconds = now - self._started_at
        total_seconds = now - self._started_at
        return self.roast_seconds, self.debate_seconds, total_seconds
