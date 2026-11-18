"""Tests for backend/core/cache.py — thread-safe TTL cache and memoising decorator."""

from __future__ import annotations

import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.cache import MISSING, TTLCache, answer_cache_key, ttl_cached  # noqa: E402


class _Clock:
    """Manual clock so expiry can be tested without sleeping."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_get_returns_missing_for_unknown_key():
    cache = TTLCache(maxsize=4, ttl=60)
    assert cache.get("nope") is MISSING


def test_set_then_get_returns_value():
    cache = TTLCache(maxsize=4, ttl=60)
    cache.set("k", {"a": 1})
    assert cache.get("k") == {"a": 1}


def test_entry_expires_after_ttl():
    clock = _Clock()
    cache = TTLCache(maxsize=4, ttl=60, timer=clock)
    cache.set("k", 1)
    clock.now += 59
    assert cache.get("k") == 1
    clock.now += 2
    assert cache.get("k") is MISSING


def test_evicts_least_recently_used_when_full():
    cache = TTLCache(maxsize=2, ttl=60)
    cache.set("a", 1)
    cache.set("b", 2)
    cache.get("a")  # "a" becomes most recently used
    cache.set("c", 3)
    assert cache.get("b") is MISSING
    assert cache.get("a") == 1
    assert cache.get("c") == 3


def test_zero_ttl_disables_cache():
    cache = TTLCache(maxsize=4, ttl=0)
    cache.set("k", 1)
    assert cache.get("k") is MISSING


def test_cached_values_are_isolated_from_caller_mutation():
    cache = TTLCache(maxsize=4, ttl=60)
    value = {"weights": {}}
    cache.set("k", value)
    value["weights"]["safety"] = 1.0  # mutate the original after storing
    first = cache.get("k")
    first["weights"]["transport"] = 1.0  # mutate the returned copy
    assert cache.get("k") == {"weights": {}}


def test_ttl_cached_calls_function_once_per_key():
    calls: list[tuple] = []

    @ttl_cached(maxsize=8, ttl=60, key=lambda suburbs: tuple(sorted(suburbs)))
    def load(suburbs):
        calls.append(tuple(suburbs))
        return {"suburbs": list(suburbs)}

    assert load(["Glebe", "Newtown"]) == {"suburbs": ["Glebe", "Newtown"]}
    assert load(["Newtown", "Glebe"]) == {"suburbs": ["Glebe", "Newtown"]}
    assert len(calls) == 1


def test_ttl_cached_does_not_cache_exceptions():
    attempts = {"n": 0}

    @ttl_cached(maxsize=8, ttl=60)
    def flaky(x):
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise RuntimeError("db down")
        return x * 2

    try:
        flaky(2)
    except RuntimeError:
        pass
    assert flaky(2) == 4
    assert flaky(2) == 4
    assert attempts["n"] == 2


def test_ttl_cached_exposes_cache_clear():
    calls = {"n": 0}

    @ttl_cached(maxsize=8, ttl=60)
    def load(x):
        calls["n"] += 1
        return x

    load(1)
    load.cache_clear()
    load(1)
    assert calls["n"] == 2


def test_ttl_cached_is_safe_under_concurrency():
    @ttl_cached(maxsize=64, ttl=60)
    def square(x):
        return {"v": x * x}

    errors: list[Exception] = []

    def worker():
        try:
            for i in range(200):
                assert square(i % 16) == {"v": (i % 16) ** 2}
        except Exception as exc:  # pragma: no cover - surfaced via assert below
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []


def test_answer_cache_key_normalises_question_and_weights():
    a = answer_cache_key("  Is NEWTOWN   safe? ", {"safety": 0.5, "transport": 0.5})
    b = answer_cache_key("is newtown safe?", {"transport": 0.5, "safety": 0.5})
    assert a == b


def test_answer_cache_key_distinguishes_weights():
    a = answer_cache_key("is newtown safe?", {"safety": 0.6, "transport": 0.4})
    b = answer_cache_key("is newtown safe?", {"safety": 0.4, "transport": 0.6})
    assert a != b


def test_answer_cache_key_treats_none_and_empty_weights_alike():
    assert answer_cache_key("q", None) == answer_cache_key("q", {})
