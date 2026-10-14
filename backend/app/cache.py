"""In-memory cache with TTL entries, never-expiring "final" entries and stale-on-error."""
import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.errors import YahooUnavailable


@dataclass(frozen=True)
class CacheResult:
    data: Any
    fetched_at: float
    stale: bool
    refresh_throttled: bool
    final: bool


@dataclass(frozen=True)
class _Entry:
    data: Any
    fetched_at: float
    expires_at: float | None  # None = final, never expires

    @property
    def final(self) -> bool:
        return self.expires_at is None

    def result(self, *, stale: bool = False, refresh_throttled: bool = False) -> CacheResult:
        return CacheResult(self.data, self.fetched_at, stale, refresh_throttled, self.final)


class Cache:
    def __init__(self, clock: Callable[[], float] = time.time, max_entries: int = 64,
                 refresh_min_age: float = 30.0, failure_cooldown: float = 30.0):
        self._clock = clock
        self._max_entries = max_entries
        self._refresh_min_age = refresh_min_age
        self._failure_cooldown = failure_cooldown
        self._failed_until: dict[str, float] = {}
        self._entries: OrderedDict[str, _Entry] = OrderedDict()
        self._lock = threading.Lock()
        self._key_locks: dict[str, threading.Lock] = {}

    def get_or_fetch(self, key: str, fetch: Callable[[], Any], ttl: float | None,
                     refresh: bool = False) -> CacheResult:
        """Return cached data for `key`, fetching it when missing, expired or refreshed.

        `ttl=None` stores the fetched data as final (kept forever, refresh ignored).
        """
        with self._key_lock(key):
            entry = self._get(key)
            if entry is not None:
                if entry.final:
                    return entry.result()
                age = self._clock() - entry.fetched_at
                if refresh and age < self._refresh_min_age:
                    return entry.result(refresh_throttled=True)
                if not refresh and self._clock() < entry.expires_at:
                    return entry.result()

            # After a failure, don't call Yahoo again for this key until the cooldown passes;
            # otherwise every visitor (and every queued request) repeats a slow or rate-limited call.
            if self._clock() < self._failed_until.get(key, 0.0):
                if entry is None:
                    raise YahooUnavailable(f"{key} failed recently; retrying after cooldown")
                return entry.result(stale=True)

            try:
                data = fetch()
            except YahooUnavailable:
                self._failed_until[key] = self._clock() + self._failure_cooldown
                if entry is None:
                    raise
                return entry.result(stale=True)
            self._failed_until.pop(key, None)

            now = self._clock()
            entry = _Entry(data, now, None if ttl is None else now + ttl)
            self._put(key, entry)
            return entry.result()

    def _key_lock(self, key: str) -> threading.Lock:
        with self._lock:
            return self._key_locks.setdefault(key, threading.Lock())

    def _get(self, key: str) -> _Entry | None:
        with self._lock:
            entry = self._entries.get(key)
            if entry is not None:
                self._entries.move_to_end(key)
            return entry

    def _put(self, key: str, entry: _Entry) -> None:
        with self._lock:
            self._entries[key] = entry
            self._entries.move_to_end(key)
            non_final = [k for k, e in self._entries.items() if not e.final]
            for old_key in non_final[:max(0, len(non_final) - self._max_entries)]:
                del self._entries[old_key]
