"""In-process token-bucket rate limiter keyed by client IP.

ponytail: single-box only; slowapi or Redis is the upgrade for multi-machine.
"""

import threading
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from config import Settings, get_settings

RUN_RATE_LIMIT_MESSAGE = "Too many run requests. Please try again shortly."
APPEAL_RATE_LIMIT_MESSAGE = "Too many appeal requests. Please try again shortly."


class TokenBucketLimiter:
    def __init__(self, *, rate: float, capacity: float) -> None:
        self._rate = rate
        self._capacity = capacity
        self._buckets: dict[str, tuple[float, float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            tokens, last = self._buckets.get(key, (self._capacity, now))
            tokens = min(self._capacity, tokens + (now - last) * self._rate)
            if tokens >= 1.0:
                tokens -= 1.0
                self._buckets[key] = (tokens, now)
                return True
            self._buckets[key] = (tokens, now)
            return False


def _client_ip(request: Request, *, trust_proxy: bool) -> str:
    if trust_proxy:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
    if request.client is not None:
        return request.client.host
    return "unknown"


def _build_limiter(requests: int, burst: int, window_seconds: float) -> TokenBucketLimiter:
    window = max(window_seconds, 1.0)
    capacity = float(max(burst, 1))
    rate = requests / window
    return TokenBucketLimiter(rate=rate, capacity=capacity)


def build_rate_limiters(settings: Settings) -> dict[str, TokenBucketLimiter]:
    if not settings.rate_limit_enabled:
        return {}
    return {
        "run": _build_limiter(
            settings.rate_limit_requests,
            settings.rate_limit_burst,
            settings.rate_limit_window_seconds,
        ),
        "appeal": _build_limiter(
            settings.rate_limit_appeal_requests,
            settings.rate_limit_appeal_burst,
            settings.rate_limit_appeal_window_seconds,
        ),
    }


def _rate_limit_kind(path: str, method: str) -> str | None:
    if method != "POST":
        return None
    if path == "/api/runs":
        return "run"
    if path.startswith("/api/runs/") and path.endswith("/appeal"):
        return "appeal"
    return None


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        *,
        limiters: dict[str, TokenBucketLimiter] | None = None,
        trust_proxy: bool = False,
    ) -> None:
        super().__init__(app)
        self._limiters = limiters or {}
        self._trust_proxy = trust_proxy

    async def dispatch(self, request: Request, call_next) -> Response:
        kind = _rate_limit_kind(request.url.path, request.method)
        if kind is None:
            return await call_next(request)
        limiter = self._limiters.get(kind)
        if limiter is None:
            return await call_next(request)
        if not limiter.allow(_client_ip(request, trust_proxy=self._trust_proxy)):
            message = APPEAL_RATE_LIMIT_MESSAGE if kind == "appeal" else RUN_RATE_LIMIT_MESSAGE
            return JSONResponse(status_code=429, content={"detail": message})
        return await call_next(request)


def add_rate_limit_middleware(app, *, settings: Settings | None = None) -> None:
    resolved = settings or get_settings()
    limiters = build_rate_limiters(resolved)
    if limiters:
        app.add_middleware(
            RateLimitMiddleware,
            limiters=limiters,
            trust_proxy=resolved.trust_proxy,
        )
