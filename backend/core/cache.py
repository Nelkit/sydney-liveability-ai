"""In-process TTL caches shared by the chat pipeline.

Two kinds of data are cached here:

* Static reference data (BOCSAR, OSM, transport, sentiment profiles). These
  tables change at most quarterly, yet every chat turn used to query them on
  the remote Postgres instance. A per-suburb TTL cache means each row set is
  fetched at most once per TTL window.
* Full chat answers keyed by (normalised question, weights). Portfolio
  visitors tend to repeat the suggested questions, so a repeated question is
  answered instantly instead of re-running every agent and the LLM.

Design notes:

* The cache is thread-safe. Specialists run in a thread pool and FastAPI
  serves sync endpoints from a thread pool, so concurrent access is normal.
* Values are deep-copied on write and on read. Callers routinely mutate the
  dicts they receive (the synthesiser writes ``context["weights"]``), and
  without copying, one request's mutation would leak into the next.
* Exceptions are never cached, so a transient database failure is retried
  on the next call instead of being frozen for the whole TTL window.
* The cache lives in process memory and is cleared on restart, which is the
  expected way to pick up freshly ingested data.
"""

from __future__ import annotations

import copy
import functools
import json
import threading
import time
from collections import OrderedDict
from collections.abc import Callable, Hashable
from typing import Any, TypeVar

MISSING: Any = object()

F = TypeVar("F", bound=Callable[..., Any])


class TTLCache:
    """Bounded LRU cache whose entries expire ``ttl`` seconds after writing."""

    def __init__(
        self,
        maxsize: int,
        ttl: float,
        timer: Callable[[], float] = time.monotonic,
    ) -> None:
        self.maxsize = maxsize
        self.ttl = ttl
        self._timer = timer
        self._data: OrderedDict[Hashable, tuple[float, Any]] = OrderedDict()
        self._lock = threading.Lock()

    @property
    def enabled(self) -> bool:
        return self.ttl > 0 and self.maxsize > 0

    def get(self, key: Hashable) -> Any:
        """Return a copy of the cached value, or ``MISSING``."""
        if not self.enabled:
            return MISSING
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                return MISSING
            expires_at, value = entry
            if self._timer() >= expires_at:
                del self._data[key]
                return MISSING
            self._data.move_to_end(key)
        return copy.deepcopy(value)

    def set(self, key: Hashable, value: Any) -> None:
        """Store a private copy of ``value`` under ``key``."""
        if not self.enabled:
            return
        stored = copy.deepcopy(value)
        with self._lock:
            self._data[key] = (self._timer() + self.ttl, stored)
            self._data.move_to_end(key)
            while len(self._data) > self.maxsize:
                self._data.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._data)


def ttl_cached(
    maxsize: int,
    ttl: float,
    key: Callable[..., Hashable] | None = None,
) -> Callable[[F], F]:
    """Memoise a function returning plain data (dicts, lists, scalars).

    ``key`` builds the cache key from the call arguments; by default the
    positional and keyword arguments themselves are used. Two concurrent
    misses for the same key may both execute the function — acceptable for
    idempotent reads and cheaper than holding a lock across a DB round trip.
    """

    def decorator(func: F) -> F:
        cache = TTLCache(maxsize=maxsize, ttl=ttl)

        def make_key(*args: Any, **kwargs: Any) -> Hashable:
            if key is not None:
                return key(*args, **kwargs)
            return (args, tuple(sorted(kwargs.items())))

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            cache_key = make_key(*args, **kwargs)
            cached = cache.get(cache_key)
            if cached is not MISSING:
                return cached
            result = func(*args, **kwargs)
            cache.set(cache_key, result)
            return result

        wrapper.cache = cache  # type: ignore[attr-defined]
        wrapper.cache_clear = cache.clear  # type: ignore[attr-defined]
        return wrapper  # type: ignore[return-value]

    return decorator


def answer_cache_key(question: str, weights: dict[str, Any] | None) -> tuple[str, str]:
    """Normalise a chat turn so trivially different phrasings share a key."""
    normalised_question = " ".join((question or "").lower().split())
    normalised_weights = json.dumps(weights or {}, sort_keys=True, default=str)
    return (normalised_question, normalised_weights)
