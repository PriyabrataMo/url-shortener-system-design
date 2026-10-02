from __future__ import annotations

from collections import OrderedDict
from threading import RLock
from time import monotonic


class LocalTTLCache:
    """A bounded, process-local LRU cache for hot redirect keys."""

    def __init__(self, max_entries: int, ttl_seconds: int) -> None:
        self.max_entries = max_entries
        self.ttl_seconds = ttl_seconds
        self._items: OrderedDict[str, tuple[object, float]] = OrderedDict()
        self._lock = RLock()

    def get(self, key: str) -> object | None:
        now = monotonic()
        with self._lock:
            item = self._items.get(key)
            if item is None:
                return None
            value, expires_at = item
            if expires_at <= now:
                del self._items[key]
                return None
            self._items.move_to_end(key)
            return value

    def set(self, key: str, value: object, ttl_seconds: int | None = None) -> None:
        expires_at = monotonic() + (ttl_seconds or self.ttl_seconds)
        with self._lock:
            self._items[key] = (value, expires_at)
            self._items.move_to_end(key)
            while len(self._items) > self.max_entries:
                self._items.popitem(last=False)

    def delete(self, key: str) -> None:
        with self._lock:
            self._items.pop(key, None)
