from __future__ import annotations

import threading
import time
from collections import defaultdict, deque


class SlidingWindowRateLimiter:
    """In-process sliding-window limiter with lock protection for concurrent access."""

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, rpm: int) -> bool:
        now = time.monotonic()
        window_start = now - 60

        with self._lock:
            q = self._hits[key]
            while q and q[0] < window_start:
                q.popleft()

            if len(q) >= rpm:
                return False

            q.append(now)
            return True
