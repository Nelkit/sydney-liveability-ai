"""Tests for backend/agents/query/sentiment.py — CrewAI sentiment specialist.

Exercises the new tool-driven retrieval path: structured aspects via
get_suburb_aspect, no-data refusal for null dimensions, and the
evidence_trace shape that the synthesiser depends on. ChromaDB is
monkeypatched out so these tests don't need the index populated.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture(autouse=True)
def _stub_chromadb(monkeypatch):
    """Replace search_posts ChromaDB call with an empty-result stub."""
    from core.agent import tools as agent_tools

    monkeypatch.setattr(
        agent_tools,
        "_query_chunks",
        lambda query, k, filters: [],
    )


def _import_sentiment_agent():
    """Import lazily because the module pulls in CrewAI at import time."""
    pytest.importorskip("crewai")
    from agents.query.sentiment import _query_sentiment_impl

    return _query_sentiment_impl


def test_sentiment_agent_returns_structured_aspects_for_known_suburb() -> None:
    impl = _import_sentiment_agent()
    result = impl("Newtown")
    assert result["status"] == "ok"
    assert result["suburb"] == "Newtown"
    assert "transport" in result["aspects"]
    transport = result["aspects"]["transport"]
    assert transport.get("status") != "no_data"
    assert isinstance(transport["score"], float)
    # Every aspect produced one trace entry; pipeline stays well under budget.
    assert any(
        e["tool"] == "get_suburb_aspect" and e["arguments"]["dimension"] == "transport"
        for e in result["evidence_trace"]
    )


def test_sentiment_agent_marks_null_dim_as_no_data() -> None:
    """Abbotsbury's `noise` aspect is null in the cached analysis fixture."""
    impl = _import_sentiment_agent()
    result = impl("Abbotsbury")
    assert result["status"] == "ok"
    noise = result["aspects"].get("noise")
    assert noise is not None
    assert noise.get("status") == "no_data", f"expected no_data, got {noise}"


def test_sentiment_agent_no_data_for_unknown_suburb() -> None:
    impl = _import_sentiment_agent()
    result = impl("Atlantis")
    assert result["status"] == "no_data"
    assert result["evidence_trace"] == []
    assert result["aspects"] == {}


def test_sentiment_agent_question_routes_to_dimension() -> None:
    """A transport-themed question routes the search_posts call to dimension=transport."""
    impl = _import_sentiment_agent()
    result = impl("Newtown", question="how reliable is the bus into the city?")
    search_calls = [e for e in result["evidence_trace"] if e["tool"] == "search_posts"]
    assert search_calls, "expected one search_posts trace entry"
    assert search_calls[0]["arguments"]["dimension"] == "transport"


def test_sentiment_agent_falls_back_to_curated_sources() -> None:
    """When no question-driven hits come back, the curated quotes carry citations."""
    impl = _import_sentiment_agent()
    result = impl("Newtown")
    assert result["sources"], "expected curated fallback sources"
    assert all(isinstance(s, dict) and "text" in s for s in result["sources"])
