from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass
class CacheEntry(Generic[T]):
    value: T
    expires_at: float


class TTLCache(Generic[T]):
    def __init__(self) -> None:
        self._store: dict[str, CacheEntry[T]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> T | None:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            if entry.expires_at <= time.monotonic():
                self._store.pop(key, None)
                return None
            return entry.value

    def set(self, key: str, value: T, ttl_s: int) -> None:
        with self._lock:
            self._store[key] = CacheEntry(value=value, expires_at=time.monotonic() + ttl_s)
