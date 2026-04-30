"""Unit test for backend/db/chromadb.py.

Loads MiniLM (~80 MB) on first run, so it is slow on cold cache. Runs
against an in-memory ChromaDB by pointing `settings.chromadb_path` at a
tmp dir before the singleton client is created.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

pytest.importorskip("sentence_transformers")
pytest.importorskip("chromadb")
pytest.importorskip("langchain_text_splitters")


@pytest.fixture
def fresh_collection(tmp_path, monkeypatch):
    """Reset the singleton client to a tmp_path-backed instance.

    The module-level lru_cache must be cleared so the fixture's
    chromadb_path actually takes effect.
    """
    from config import settings
    from db import chromadb as chromadb_helpers

    monkeypatch.setattr(settings, "chromadb_path", str(tmp_path / "chroma"))
    chromadb_helpers.get_chromadb_client.cache_clear()
    chromadb_helpers.initialize_collection.cache_clear() if hasattr(
        chromadb_helpers.initialize_collection, "cache_clear"
    ) else None

    collection_name = "test_sydney_liveability"
    collection = chromadb_helpers.initialize_collection(collection_name)
    yield collection_name, collection
    chromadb_helpers.get_chromadb_client.cache_clear()


def test_chunk_upsert_query_roundtrip(fresh_collection) -> None:
    """A 5-record fixture survives chunking, upsert, and retrieves on a known query."""
    from db import chromadb as chromadb_helpers

    collection_name, _ = fresh_collection

    fixtures = [
        {
            "suburb": "Newtown",
            "dimension": "transport",
            "text": "The 422 bus into the city is reliable in peak hour from Newtown",
        },
        {
            "suburb": "Newtown",
            "dimension": "food_and_cafe",
            "text": "King Street is full of great cafes and brunch spots in Newtown",
        },
        {
            "suburb": "Bondi",
            "dimension": "green_space",
            "text": "Bondi has the cliff walk and several big parks for outdoor exercise",
        },
        {
            "suburb": "Glebe",
            "dimension": "community",
            "text": "Glebe has a friendly neighbourhood feel with lots of locals chatting",
        },
        {
            "suburb": "Manly",
            "dimension": "nightlife",
            "text": "Manly's pubs near the wharf are lively on Friday nights",
        },
    ]

    records = []
    for idx, fx in enumerate(fixtures):
        chunks = chromadb_helpers.chunk_reddit_text(fx["text"])
        assert chunks, "Fixture text should produce at least one chunk"
        for chunk_index, chunk in enumerate(chunks):
            records.append(
                {
                    "text": chunk,
                    "metadata": {
                        "suburb": fx["suburb"],
                        "source": "reddit",
                        "dimension": fx["dimension"],
                        "chunk_index": chunk_index,
                        "post_id": f"fixture-{idx}",
                    },
                }
            )

    upserted = chromadb_helpers.upsert_chunks(records, collection_name=collection_name)
    assert upserted == len(records)

    hits = chromadb_helpers.query_chunks(
        "bus reliability",
        k=2,
        filters={"suburb": "Newtown"},
        collection_name=collection_name,
    )
    assert hits, "Expected at least one hit for the bus-reliability query"
    top = hits[0]
    assert top["metadata"]["suburb"] == "Newtown"
    assert top["metadata"]["dimension"] == "transport"
    assert "bus" in top["text"].lower()


def test_upsert_rejects_missing_required_metadata(fresh_collection) -> None:
    """Required metadata keys are enforced at the helper, not at ChromaDB write time."""
    from db import chromadb as chromadb_helpers

    collection_name, _ = fresh_collection

    bad_record = {
        "text": "Something about a place",
        "metadata": {"suburb": "Newtown", "source": "reddit", "chunk_index": 0},
    }
    with pytest.raises(ValueError, match="dimension"):
        chromadb_helpers.upsert_chunks([bad_record], collection_name=collection_name)


def test_get_collection_stats_reports_breakdown(fresh_collection) -> None:
    from db import chromadb as chromadb_helpers

    collection_name, _ = fresh_collection

    chromadb_helpers.upsert_chunks(
        [
            {
                "text": "stats fixture text",
                "metadata": {
                    "suburb": "Newtown",
                    "source": "reddit",
                    "dimension": "transport",
                    "chunk_index": 0,
                    "post_id": "stats-1",
                },
            }
        ],
        collection_name=collection_name,
    )

    stats = chromadb_helpers.get_collection_stats(collection_name=collection_name)
    assert stats["count"] >= 1
    assert "reddit" in stats["by_source"]
    assert any(suburb == "Newtown" for suburb, _ in stats["by_suburb_top_n"])
