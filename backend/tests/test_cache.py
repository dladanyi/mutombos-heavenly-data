import threading
import time

import pytest

from app.cache import Cache
from app.errors import YahooUnavailable


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


class Fetch:
    def __init__(self, value="v1"):
        self.calls = 0
        self.value = value
        self.error = None

    def __call__(self):
        self.calls += 1
        if self.error:
            raise self.error
        return f"{self.value}#{self.calls}"


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def cache(clock):
    return Cache(clock=clock)


def test_miss_fetches_and_caches(cache):
    fetch = Fetch()
    first = cache.get_or_fetch("k", fetch, ttl=300)
    second = cache.get_or_fetch("k", fetch, ttl=300)
    assert fetch.calls == 1
    assert first.data == second.data == "v1#1"
    assert first.fetched_at == 1000.0
    assert (first.stale, first.refresh_throttled, first.final) == (False, False, False)


def test_ttl_expiry_refetches(cache, clock):
    fetch = Fetch()
    cache.get_or_fetch("k", fetch, ttl=300)
    clock.now += 299
    cache.get_or_fetch("k", fetch, ttl=300)
    assert fetch.calls == 1
    clock.now += 2
    assert cache.get_or_fetch("k", fetch, ttl=300).data == "v1#2"


def test_final_entry_never_expires(cache, clock):
    fetch = Fetch()
    cache.get_or_fetch("k", fetch, ttl=None)
    clock.now += 10 * 365 * 86400
    result = cache.get_or_fetch("k", fetch, ttl=300)
    assert fetch.calls == 1
    assert result.final is True


def test_refresh_ignored_for_final(cache, clock):
    fetch = Fetch()
    cache.get_or_fetch("k", fetch, ttl=None)
    clock.now += 3600
    result = cache.get_or_fetch("k", fetch, ttl=None, refresh=True)
    assert fetch.calls == 1
    assert result.refresh_throttled is False


def test_refresh_bypasses_ttl_after_30s(cache, clock):
    fetch = Fetch()
    cache.get_or_fetch("k", fetch, ttl=300)
    clock.now += 31
    assert cache.get_or_fetch("k", fetch, ttl=300, refresh=True).data == "v1#2"
    assert fetch.calls == 2


def test_refresh_throttled_within_30s(cache, clock):
    fetch = Fetch()
    cache.get_or_fetch("k", fetch, ttl=300)
    clock.now += 10
    result = cache.get_or_fetch("k", fetch, ttl=300, refresh=True)
    assert fetch.calls == 1
    assert result.refresh_throttled is True
    assert result.data == "v1#1"


def test_refresh_on_miss_fetches(cache):
    fetch = Fetch()
    result = cache.get_or_fetch("k", fetch, ttl=300, refresh=True)
    assert fetch.calls == 1
    assert result.refresh_throttled is False


def test_failure_serves_stale(cache, clock):
    fetch = Fetch()
    cache.get_or_fetch("k", fetch, ttl=300)
    clock.now += 301
    fetch.error = YahooUnavailable("down")
    result = cache.get_or_fetch("k", fetch, ttl=300)
    assert result.stale is True
    assert result.data == "v1#1"
    assert result.fetched_at == 1000.0


def test_failed_refresh_serves_stale(cache, clock):
    fetch = Fetch()
    cache.get_or_fetch("k", fetch, ttl=300)
    clock.now += 31
    fetch.error = YahooUnavailable("down")
    assert cache.get_or_fetch("k", fetch, ttl=300, refresh=True).stale is True


def test_failure_without_entry_raises(cache):
    fetch = Fetch()
    fetch.error = YahooUnavailable("down")
    with pytest.raises(YahooUnavailable):
        cache.get_or_fetch("k", fetch, ttl=300)


def test_other_exceptions_propagate(cache, clock):
    fetch = Fetch()
    cache.get_or_fetch("k", fetch, ttl=300)
    clock.now += 301
    fetch.error = RuntimeError("bug")
    with pytest.raises(RuntimeError):
        cache.get_or_fetch("k", fetch, ttl=300)


def test_ttl_taken_from_the_call_that_fetched(cache, clock):
    fetch = Fetch()
    cache.get_or_fetch("k", fetch, ttl=300)
    clock.now += 301
    cache.get_or_fetch("k", fetch, ttl=None)
    clock.now += 10 ** 8
    assert cache.get_or_fetch("k", fetch, ttl=300).final is True
    assert fetch.calls == 2


def test_lru_evicts_oldest_non_final_only(clock):
    cache = Cache(clock=clock, max_entries=2)
    fetches = {k: Fetch(k) for k in ["final", "a", "b", "c"]}
    cache.get_or_fetch("final", fetches["final"], ttl=None)
    for key in ["a", "b", "c"]:
        clock.now += 1
        cache.get_or_fetch(key, fetches[key], ttl=300)
    for key in ["final", "b", "c"]:
        cache.get_or_fetch(key, fetches[key], ttl=300)
    assert [fetches[k].calls for k in ["final", "b", "c"]] == [1, 1, 1]
    cache.get_or_fetch("a", fetches["a"], ttl=300)
    assert fetches["a"].calls == 2


def test_lru_counts_recent_use(clock):
    cache = Cache(clock=clock, max_entries=2)
    fa, fb, fc = Fetch("a"), Fetch("b"), Fetch("c")
    cache.get_or_fetch("a", fa, ttl=300)
    cache.get_or_fetch("b", fb, ttl=300)
    cache.get_or_fetch("a", fa, ttl=300)  # a is now most recently used
    cache.get_or_fetch("c", fc, ttl=300)  # evicts b
    cache.get_or_fetch("a", fa, ttl=300)
    cache.get_or_fetch("b", fb, ttl=300)
    assert (fa.calls, fb.calls) == (1, 2)


def test_concurrent_misses_fetch_once(cache):
    gate = threading.Event()
    calls = []

    def slow_fetch():
        calls.append(1)
        gate.wait(timeout=5)
        return "data"

    results = []
    threads = [threading.Thread(target=lambda: results.append(cache.get_or_fetch("k", slow_fetch, ttl=300)))
               for _ in range(8)]
    for t in threads:
        t.start()
    time.sleep(0.1)  # let every thread reach the cache while the first fetch is blocked
    gate.set()
    for t in threads:
        t.join(timeout=5)
    assert len(calls) == 1
    assert [r.data for r in results] == ["data"] * 8


def test_different_keys_fetch_independently(cache):
    fa, fb = Fetch("a"), Fetch("b")
    cache.get_or_fetch("a", fa, ttl=300)
    cache.get_or_fetch("b", fb, ttl=300)
    assert (fa.calls, fb.calls) == (1, 1)


def test_failure_cooldown_serves_stale_without_calling_yahoo(cache, clock):
    fetch = Fetch()
    cache.get_or_fetch("k", fetch, ttl=300)
    clock.now += 301
    fetch.error = YahooUnavailable("down")
    assert cache.get_or_fetch("k", fetch, ttl=300).stale is True
    clock.now += 10
    assert cache.get_or_fetch("k", fetch, ttl=300).stale is True
    assert cache.get_or_fetch("k", fetch, ttl=300, refresh=True).stale is True
    assert fetch.calls == 2
    clock.now += 31
    fetch.error = None
    assert cache.get_or_fetch("k", fetch, ttl=300).data == "v1#3"


def test_failure_cooldown_without_entry_raises_without_calling_yahoo(cache, clock):
    fetch = Fetch()
    fetch.error = YahooUnavailable("down")
    for _ in range(3):
        with pytest.raises(YahooUnavailable):
            cache.get_or_fetch("k", fetch, ttl=300)
    assert fetch.calls == 1
    clock.now += 31
    fetch.error = None
    assert cache.get_or_fetch("k", fetch, ttl=300).data == "v1#2"
