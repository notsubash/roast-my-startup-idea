"""In-process token-bucket rate limiter keyed by client IP.

ponytail: single-box only; slowapi or Redis is the upgrade for multi-machine.
"""

import threading
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from config import Settings, get_settings


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


def build_rate_limiter(settings: Settings) -> TokenBucketLimiter | None:
    if not settings.rate_limit_enabled:
        return None
    window = max(settings.rate_limit_window_seconds, 1.0)
    capacity = float(max(settings.rate_limit_burst, 1))
    rate = settings.rate_limit_requests / window
    return TokenBucketLimiter(rate=rate, capacity=capacity)


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        *,
        limiter: TokenBucketLimiter | None = None,
        trust_proxy: bool = False,
    ) -> None:
        super().__init__(app)
        self._limiter = limiter
        self._trust_proxy = trust_proxy

    async def dispatch(self, request: Request, call_next) -> Response:
        if self._limiter is None or request.method != "POST" or request.url.path != "/api/runs":
            return await call_next(request)
        if not self._limiter.allow(_client_ip(request, trust_proxy=self._trust_proxy)):
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many run requests. Please try again shortly."},
            )
        return await call_next(request)


def add_rate_limit_middleware(app, *, settings: Settings | None = None) -> None:
    resolved = settings or get_settings()
    limiter = build_rate_limiter(resolved)
    if limiter is not None:
        app.add_middleware(
            RateLimitMiddleware,
            limiter=limiter,
            trust_proxy=resolved.trust_proxy,
        )
