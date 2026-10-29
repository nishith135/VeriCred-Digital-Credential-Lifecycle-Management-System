"""In-memory sliding-window rate limiter dependency for public verification endpoints."""

from collections import defaultdict, deque
import math
import time
from typing import Deque, Dict, Optional

from fastapi import Request

from backend.core.config import settings


class RateLimitExceededError(Exception):
    """Raised when a client exceeds the sliding-window request rate limit."""

    def __init__(self, retry_after: int, limit: int, window_seconds: int = 60):
        super().__init__(
            f"Rate limit exceeded ({limit} requests per {window_seconds}s). Retry after {retry_after}s."
        )
        self.retry_after = max(1, int(retry_after))
        self.limit = limit
        self.window_seconds = window_seconds


class SlidingWindowRateLimiter:
    """Callable FastAPI dependency enforcing a per-IP sliding-window rate limit."""

    def __init__(self, max_requests: Optional[int] = None, window_seconds: int = 60):
        self._override_max_requests: Optional[int] = max_requests
        self.window_seconds: int = window_seconds
        self._hits: Dict[str, Deque[float]] = defaultdict(deque)

    @property
    def max_requests(self) -> int:
        if self._override_max_requests is not None:
            return self._override_max_requests
        return settings.VERIFY_RATE_LIMIT_PER_MINUTE

    def set_limit(self, max_requests: Optional[int], window_seconds: int = 60) -> None:
        """Configure or reset the limit (useful for deterministic test overrides)."""
        self._override_max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits.clear()

    def reset(self) -> None:
        """Clear all recorded request timestamps."""
        self._hits.clear()

    async def __call__(self, request: Request) -> None:
        now = time.monotonic()
        client_ip = request.client.host if request.client and request.client.host else "127.0.0.1"
        cutoff = now - self.window_seconds

        bucket = self._hits[client_ip]
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()

        limit = self.max_requests
        if len(bucket) >= limit:
            oldest = bucket[0]
            retry_after = max(1, int(math.ceil((oldest + self.window_seconds) - now)))
            raise RateLimitExceededError(
                retry_after=retry_after,
                limit=limit,
                window_seconds=self.window_seconds,
            )

        bucket.append(now)


verify_rate_limiter = SlidingWindowRateLimiter()

