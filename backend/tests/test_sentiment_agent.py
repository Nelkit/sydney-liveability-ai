"""Tests for backend/agents/query/sentiment.py — full agentic RAG specialist.

The agent now drives a CrewAI ReAct loop, so behavioural tests stub
`Crew.kickoff` with canned JSON and verify the impl parses, normalises,
and merges in deterministic fields (emotions, overall label, status).
The no-data short-circuits run before any LLM call and are tested
directly.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture(autouse=True)
def _stub_chromadb(monkeypatch):
    """Replace the ChromaDB query path with an empty-result stub."""
    from core.agent import tools as agent_tools

    monkeypatch.setattr(
        agent_tools,
        "_query_chunks",
        lambda query, k, filters: [],
    )


def _import_module():
    pytest.importorskip("crewai")
    from agents.query import sentiment

    return sentiment


def _stub_kickoff(monkeypatch, raw_json: str) -> None:
    """Patch Crew.kickoff so tests don't need a real LLM."""
    from crewai import Crew

    monkeypatch.setattr(
        Crew,
        "kickoff",
        lambda self, *args, **kwargs: SimpleNamespace(raw=raw_json),
    )


def test_sentiment_agent_no_data_for_unknown_suburb() -> None:
    """Unknown suburbs short-circuit before the agent loop runs."""
    sentiment = _import_module()
    result = sentiment._query_sentiment_impl("Atlantis")
    assert result["status"] == "no_data"
    assert result["evidence_trace"] == []
    assert result["aspects"] == {}


def test_sentiment_agent_no_data_for_empty_suburb() -> None:
    sentiment = _import_module()
    result = sentiment._query_sentiment_impl("")
    assert result["status"] == "no_data"
    assert result["aspects"] == {}


def test_sentiment_agent_parses_canned_agent_output(monkeypatch) -> None:
    """When the agent returns valid JSON, impl normalises and merges emotions."""
    sentiment = _import_module()
    canned = (
        '{"aspects": {"transport": {"score": 0.78, "source": "reddit", "coverage": "strong"}}, '
        '"sources": [{"text": "trains run on time", "suburb": "Newtown", '
        '"dimension": "transport", "url": "https://example.com/post"}]}'
    )
    _stub_kickoff(monkeypatch, canned)

    result = sentiment._query_sentiment_impl(
        "Newtown",
        question="how reliable is the bus into the city?",
    )

    assert result["status"] == "ok"
    assert result["suburb"] == "Newtown"
    assert "transport" in result["aspects"]
    assert result["aspects"]["transport"]["score"] == 0.78
    assert result["overall"] == "positive"
    assert result["sources"] and result["sources"][0]["dimension"] == "transport"
    # Emotions come from the cached SuburbAnalysis, not the agent.
    assert isinstance(result["emotions"], dict)


def test_sentiment_agent_handles_unparseable_agent_output(monkeypatch) -> None:
    sentiment = _import_module()
    _stub_kickoff(monkeypatch, "I am thinking about this question and have no JSON.")

    result = sentiment._query_sentiment_impl("Newtown", question="anything")

    assert result["status"] == "no_data"
    assert "did not return parseable JSON" in result.get("reason", "")


def test_sentiment_agent_strips_markdown_fenced_json(monkeypatch) -> None:
    sentiment = _import_module()
    canned = (
        "Here is the answer.\n```json\n"
        '{"aspects": {"safety": {"score": 0.3, "source": "reddit", "coverage": "weak"}}, '
        '"sources": []}\n```'
    )
    _stub_kickoff(monkeypatch, canned)

    result = sentiment._query_sentiment_impl("Newtown", question="is it safe?")

    assert result["status"] == "ok"
    assert result["aspects"]["safety"]["score"] == 0.3
    assert result["overall"] == "negative"
