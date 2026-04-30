"""Unit tests for backend/core/agent/tools.py.

Use real fixture suburbs from data/processed/reddit_analyses/:
- Newtown: high coverage across dims (good for the structured-lookup path)
- Abbotsbury: noise dimension is null-scored with source=none (good for
  the no-data refusal path)

ChromaDB is monkeypatched out where possible so we don't need the
collection populated to assert no_data behaviour. The semantic-search
happy path is covered in test_chromadb.py.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.agent import tools  # noqa: E402


def test_get_suburb_aspect_returns_structured_entry() -> None:
    result = tools.get_suburb_aspect("Newtown", "transport")
    assert result["status"] == "ok"
    assert result["suburb"] == "Newtown"
    assert result["dimension"] == "transport"
    assert isinstance(result["score"], float)
    assert result["source"] == "reddit"


def test_get_suburb_aspect_returns_no_data_for_null_dim() -> None:
    result = tools.get_suburb_aspect("Abbotsbury", "noise")
    assert result["status"] == "no_data"
    assert result["suburb"] == "Abbotsbury"
    assert result["dimension"] == "noise"


def test_get_suburb_aspect_returns_no_data_for_unknown_suburb() -> None:
    result = tools.get_suburb_aspect("Atlantis", "transport")
    assert result["status"] == "no_data"


def test_search_posts_short_circuits_on_null_dimension(monkeypatch) -> None:
    """When the cached analysis says no_data, ChromaDB MUST NOT be queried."""
    called: dict = {"hit": False}

    def _spy(*a, **kw):
        called["hit"] = True
        return []

    monkeypatch.setattr(tools, "_query_chunks", _spy)

    result = tools.search_posts(
        suburb="Abbotsbury",
        dimension="noise",
        query="how loud is it at night",
        k=3,
    )
    assert result["status"] == "no_data"
    assert called["hit"] is False, "search_posts must not query ChromaDB for null dims"


def test_search_posts_passes_filters_through(monkeypatch) -> None:
    captured: dict = {}

    def _spy(query, k, filters):
        captured["query"] = query
        captured["k"] = k
        captured["filters"] = filters
        return [{"text": "x", "metadata": {"suburb": "Newtown"}, "distance": 0.1}]

    monkeypatch.setattr(tools, "_query_chunks", _spy)
    result = tools.search_posts(
        suburb="Newtown",
        dimension="transport",
        query="bus reliability",
        k=4,
    )
    assert result["status"] == "ok"
    assert result["result_count"] == 1
    assert captured["filters"] == {"suburb": "Newtown", "dimension": "transport"}
    assert captured["k"] == 4


def test_search_posts_omits_dimension_filter_when_null(monkeypatch) -> None:
    captured: dict = {}

    def _spy(query, k, filters):
        captured["filters"] = filters
        return []

    monkeypatch.setattr(tools, "_query_chunks", _spy)
    tools.search_posts(suburb="Newtown", dimension=None, query="vibe", k=2)
    assert captured["filters"] == {"suburb": "Newtown"}


def test_compare_suburbs_drops_nulls_and_sorts() -> None:
    """Newtown has nightlife scored from Reddit, Abbotsbury does not (null aspect)."""
    result = tools.compare_suburbs(
        suburbs=["Newtown", "Abbotsbury", "Bondi"],
        dimension="nightlife",
    )
    assert result["status"] == "ok"
    suburbs_in_ranked = [r["suburb"] for r in result["ranked"]]
    # Newtown must be present; the order is descending by score
    assert "Newtown" in suburbs_in_ranked
    scores = [r["score"] for r in result["ranked"]]
    assert scores == sorted(scores, reverse=True)


def test_compare_suburbs_refuses_oversized_input() -> None:
    too_many = [f"S{i}" for i in range(11)]
    result = tools.compare_suburbs(too_many, "transport")
    assert result["status"] == "too_many"
    assert result["max"] == 10
