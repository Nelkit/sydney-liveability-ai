"""Retrieval tools for the ReAct chat agent.

The chat agent's `retrieve_agent_node` runs a bounded ReAct loop and
selects among these three tools per iteration. Every function returns a
JSON-serialisable dict so the controller can drop the result into the
`evidence_trace` without any conversion work.

Each tool consults the cached `SuburbAnalysis` (in
`data/processed/reddit_analyses/{suburb}.json`) before doing real work.
When the upstream pipeline marked an aspect with `score: null` and
`source: "none"` (i.e. no Reddit coverage AND no cross-modal proxy), the
tool returns `{"status": "no_data", ...}` instead of querying ChromaDB.
This is the contract that lets the synthesiser verbalise absence
honestly rather than confabulate from tangentially-related chunks.

The cached-analysis loader lives here rather than in `nodes.py` because
the upstream LangGraph node module is not yet present in this repo —
keeping the helper local lets the tools stand alone.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

# Resolve relative to the repo root so tools work regardless of cwd
# (the backend is sometimes run from `backend/`, sometimes from the
# project root). `parents[3]` of this file points at the repo root:
# backend/core/agent/tools.py -> backend/core/agent -> backend/core
# -> backend -> repo root.
_REPO_ROOT = Path(__file__).resolve().parents[3]
ANALYSES_DIR = _REPO_ROOT / "data" / "processed" / "reddit_analyses"


def _query_chunks(query: str, k: int, filters: dict[str, Any]) -> list[dict]:
    """Deferred indirection over `db.chromadb.query_chunks`.

    Importing `db.chromadb` at module load would force `chromadb` and
    `sentence-transformers` to be installed even for unit tests that only
    exercise the structured-lookup paths. We import lazily and route
    through this seam so tests can monkeypatch it.
    """
    from db import chromadb as chroma_mod

    return chroma_mod.query_chunks(query=query, k=k, filters=filters)

# Hard cap on suburb-comparison input. Keeps the agent from re-running
# the global filter step under the guise of a comparison; that's
# `filter_node`'s job, not a retrieval tool's.
MAX_COMPARE_SUBURBS = 10


def _suburb_slug(name: str) -> str:
    return name.strip().lower().replace(" ", "_").replace("-", "_")


@lru_cache(maxsize=512)
def _load_cached_analysis(suburb: str) -> Optional[dict[str, Any]]:
    """Load the cached `SuburbAnalysis` for a suburb, or None if missing.

    Cached because the same suburb is hit multiple times within a single
    chat turn (one for each tool call). LRU bound is generous enough to
    cover the whole shortlist without evicting hot entries.
    """
    path = ANALYSES_DIR / f"{_suburb_slug(suburb)}.json"
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _aspect_entry(suburb: str, dimension: str) -> Optional[dict[str, Any]]:
    """Return the per-dimension aspect entry from the cached analysis."""
    analysis = _load_cached_analysis(suburb)
    if not analysis:
        return None
    aspects = analysis.get("aspects") or {}
    entry = aspects.get(dimension)
    return entry if isinstance(entry, dict) else None


def _is_null_aspect(entry: Optional[dict[str, Any]]) -> bool:
    """True when the upstream pipeline marked the dimension as no-data."""
    if not entry:
        return False
    return entry.get("score") is None and entry.get("source") in (None, "none")


def search_posts(
    suburb: str,
    dimension: Optional[str],
    query: str,
    k: int = 5,
) -> dict[str, Any]:
    """Dense semantic search over the `sydney_liveability` collection.

    Filtered by `suburb` (required) and optionally by `dimension`. When
    `dimension` is supplied and the cached analysis says that
    suburb/dimension has no data, we short-circuit with `no_data` so the
    synthesiser doesn't pretend a search returned an empty result.
    """
    if not suburb:
        return {"status": "error", "reason": "suburb is required"}
    if not query or not query.strip():
        return {"status": "error", "reason": "query is required"}

    if dimension:
        entry = _aspect_entry(suburb, dimension)
        if _is_null_aspect(entry):
            return {
                "status": "no_data",
                "reason": "no Reddit coverage and no cross-modal proxy",
                "suburb": suburb,
                "dimension": dimension,
            }

    filters: dict[str, Any] = {"suburb": suburb}
    if dimension:
        filters["dimension"] = dimension

    hits = _query_chunks(query=query, k=k, filters=filters)
    return {
        "status": "ok",
        "suburb": suburb,
        "dimension": dimension,
        "query": query,
        "k": k,
        "result_count": len(hits),
        "results": hits,
    }


def get_suburb_aspect(suburb: str, dimension: str) -> dict[str, Any]:
    """Look up `aspects[dimension]` for a suburb from the cached analysis.

    Returns the structured entry verbatim, or `{status: "no_data", ...}`
    when the dimension is null-scored.
    """
    if not suburb or not dimension:
        return {"status": "error", "reason": "suburb and dimension are required"}

    entry = _aspect_entry(suburb, dimension)
    if entry is None:
        return {"status": "no_data", "suburb": suburb, "dimension": dimension}
    if _is_null_aspect(entry):
        return {"status": "no_data", "suburb": suburb, "dimension": dimension}

    return {
        "status": "ok",
        "suburb": suburb,
        "dimension": dimension,
        "score": entry.get("score"),
        "mentions": entry.get("mentions"),
        "confidence": entry.get("confidence"),
        "coverage": entry.get("coverage"),
        "source": entry.get("source"),
    }


def compare_suburbs(suburbs: list[str], dimension: str) -> dict[str, Any]:
    """Sort the input suburbs descending by `aspects[dimension].score`.

    Drops any suburb whose dimension is null-scored, returning them in a
    `dropped` list so the synthesiser can verbalise the absence. Refuses
    inputs longer than `MAX_COMPARE_SUBURBS` — the agent must not use
    this tool to re-rank the global corpus.
    """
    if not suburbs:
        return {"status": "error", "reason": "suburbs is required"}
    if not dimension:
        return {"status": "error", "reason": "dimension is required"}
    if len(suburbs) > MAX_COMPARE_SUBURBS:
        return {
            "status": "too_many",
            "max": MAX_COMPARE_SUBURBS,
            "received": len(suburbs),
        }

    ranked: list[dict[str, Any]] = []
    dropped: list[str] = []
    for suburb in suburbs:
        entry = _aspect_entry(suburb, dimension)
        if entry is None or _is_null_aspect(entry):
            dropped.append(suburb)
            continue
        score = entry.get("score")
        if score is None:
            dropped.append(suburb)
            continue
        ranked.append(
            {
                "suburb": suburb,
                "score": float(score),
                "source": entry.get("source"),
                "coverage": entry.get("coverage"),
            }
        )

    ranked.sort(key=lambda r: r["score"], reverse=True)
    return {
        "status": "ok",
        "dimension": dimension,
        "ranked": ranked,
        "dropped": dropped,
    }
