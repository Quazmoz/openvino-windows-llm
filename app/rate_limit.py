"""Simple per-IP sliding-window rate limiter for the FastAPI server.

Configurable via ``OV_LLM_RATE_LIMIT`` (requests per minute, 0 = disabled).
Uses an in-memory dict of timestamps per IP, cleaned periodically.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict, deque

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

logger = logging.getLogger("ov-llm.ratelimit")


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding-window rate limiter keyed by client IP address.

    Only applies to ``/v1/`` API routes; static pages and health checks are exempt.
    """

    def __init__(self, app, requests_per_minute: int = 60) -> None:
        super().__init__(app)
        self.rpm = max(requests_per_minute, 0)
        self.window = 60.0  # seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._last_cleanup = time.monotonic()

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if self.rpm <= 0:
            return await call_next(request)

        path = request.url.path
        # Only rate-limit API endpoints, not UI / health
        if not path.startswith("/v1/"):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        now = time.monotonic()

        # Periodic cleanup of stale entries (every 60s)
        if now - self._last_cleanup > 60.0:
            self._cleanup(now)
            self._last_cleanup = now

        window = self._hits[client_ip]
        # Remove timestamps outside the sliding window
        cutoff = now - self.window
        while window and window[0] < cutoff:
            window.popleft()

        if len(window) >= self.rpm:
            retry_after = int(window[0] + self.window - now) + 1
            logger.warning(
                "Rate limit exceeded for %s (%d/%d rpm)", client_ip, len(window), self.rpm
            )
            return Response(
                content=f'{{"detail":"Rate limit exceeded. Try again in {retry_after}s."}}',
                status_code=429,
                media_type="application/json",
                headers={"Retry-After": str(retry_after)},
            )

        window.append(now)
        return await call_next(request)

    def _cleanup(self, now: float) -> None:
        """Remove IPs with no recent activity to avoid unbounded memory growth."""
        cutoff = now - self.window
        stale = [ip for ip, dq in self._hits.items() if not dq or dq[-1] < cutoff]
        for ip in stale:
            del self._hits[ip]
