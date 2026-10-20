"""Tiny in-memory sliding-window limiter for unauthenticated endpoints."""
import threading
import time
from collections import defaultdict, deque
from ..domain.errors import DrassError


class RateLimited(DrassError):
    error_code, http_status = "RATE_LIMITED", 429


_hits: dict = defaultdict(deque)
_lock = threading.Lock()


def check(key: str, limit: int, window_s: int) -> None:
    now = time.monotonic()
    with _lock:
        q = _hits[key]
        while q and now - q[0] > window_s:
            q.popleft()
        if len(q) >= limit:
            raise RateLimited("Too many requests. Please wait a moment and try again.")
        q.append(now)


def reset() -> None:
    with _lock:
        _hits.clear()
