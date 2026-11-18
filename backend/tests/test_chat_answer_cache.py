"""Tests for the repeated-question answer cache in api/chat.py."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture()
def chat(monkeypatch):
    pytest.importorskip("crewai")
    from api import chat as chat_module

    chat_module._answer_cache.clear()
    yield chat_module
    chat_module._answer_cache.clear()


def _good_response(answer: str = "Newtown is lively.") -> dict:
    return {
        "answer": answer,
        "sources": [{"source": "reddit", "suburb": "Newtown"}],
        "suburb_scores": [{"name": "Newtown", "score": 71.0}],
        "map_state": None,
        "outputs": {"crime": {"Newtown": {"suburb": "Newtown", "crime_summary": {}}}},
    }


def _parse_sse(frames: list[str]) -> list[tuple[str, dict]]:
    events = []
    for frame in frames:
        event_line, data_line = frame.strip().split("\n", 1)
        events.append((event_line.removeprefix("event: "), json.loads(data_line.removeprefix("data: "))))
    return events


def _drain(streaming_response) -> list[str]:
    """Collect SSE frames; StreamingResponse exposes the body as an async iterator."""

    async def collect() -> list[str]:
        return [chunk async for chunk in streaming_response.body_iterator]

    return asyncio.run(collect())


# ---------------------------------------------------------------------------
# Cacheability rules
# ---------------------------------------------------------------------------


def test_good_response_is_cacheable(chat):
    assert chat._is_cacheable(_good_response())


def test_response_with_error_is_not_cacheable(chat):
    response = _good_response()
    response["error"] = {"type": "RuntimeError"}
    assert not chat._is_cacheable(response)


def test_response_with_failed_specialist_is_not_cacheable(chat):
    response = _good_response()
    response["outputs"]["sentiment"] = {"Newtown": {"status": "error", "reason": "sentiment timed out after 45s"}}
    assert not chat._is_cacheable(response)


def test_response_with_sentiment_timeout_no_data_is_not_cacheable(chat):
    response = _good_response()
    response["outputs"]["sentiment"] = {
        "Newtown": {"status": "no_data", "reason": "agent timed out after 40s"}
    }
    assert not chat._is_cacheable(response)


def test_genuine_no_data_is_cacheable(chat):
    response = _good_response()
    response["outputs"]["sentiment"] = {
        "Newtown": {"status": "no_data", "reason": "no cached SuburbAnalysis for this suburb"}
    }
    assert chat._is_cacheable(response)


# ---------------------------------------------------------------------------
# Blocking endpoint
# ---------------------------------------------------------------------------


def test_chat_reuses_cached_answer_for_repeated_question(chat, monkeypatch):
    calls = {"n": 0}

    def fake_run_query(question, weights):
        calls["n"] += 1
        return _good_response()

    monkeypatch.setattr(chat, "run_query", fake_run_query)
    first = chat.chat(chat.ChatRequest(question="Is Newtown safe?"))
    second = chat.chat(chat.ChatRequest(question="  is newtown SAFE? "))

    assert calls["n"] == 1
    assert first == second
    assert second["answer"] == "Newtown is lively."


def test_chat_recomputes_when_weights_differ(chat, monkeypatch):
    calls = {"n": 0}

    def fake_run_query(question, weights):
        calls["n"] += 1
        return _good_response()

    monkeypatch.setattr(chat, "run_query", fake_run_query)
    chat.chat(chat.ChatRequest(question="q", weights={"safety": 1.0}))
    chat.chat(chat.ChatRequest(question="q", weights={"transport": 1.0}))
    assert calls["n"] == 2


def test_chat_does_not_cache_degraded_answers(chat, monkeypatch):
    calls = {"n": 0}

    def fake_run_query(question, weights):
        calls["n"] += 1
        response = _good_response()
        response["error"] = {"type": "Timeout"}
        return response

    monkeypatch.setattr(chat, "run_query", fake_run_query)
    chat.chat(chat.ChatRequest(question="q"))
    chat.chat(chat.ChatRequest(question="q"))
    assert calls["n"] == 2


# ---------------------------------------------------------------------------
# Streaming endpoint
# ---------------------------------------------------------------------------


def test_stream_caches_done_payload_and_replays_it(chat, monkeypatch):
    calls = {"n": 0}

    def fake_stream(question, weights):
        calls["n"] += 1
        yield ("step", {"text": "Routing question…"})
        yield ("done", _good_response())

    monkeypatch.setattr(chat, "run_query_stream", fake_stream)
    first = _parse_sse(_drain(chat.chat_stream(chat.ChatRequest(message="Is Newtown safe?"))))
    second = _parse_sse(_drain(chat.chat_stream(chat.ChatRequest(message="is newtown safe?"))))

    assert calls["n"] == 1
    assert first[-1] == ("done", _good_response())
    assert second[-1] == ("done", _good_response())


def test_stream_and_blocking_share_the_cache(chat, monkeypatch):
    def fake_stream(question, weights):
        yield ("done", _good_response("from stream"))

    def fail_run_query(question, weights):  # pragma: no cover - must not run
        raise AssertionError("run_query should not run on a cache hit")

    monkeypatch.setattr(chat, "run_query_stream", fake_stream)
    monkeypatch.setattr(chat, "run_query", fail_run_query)
    _drain(chat.chat_stream(chat.ChatRequest(message="q")))
    assert chat.chat(chat.ChatRequest(question="q"))["answer"] == "from stream"
