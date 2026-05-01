"""ChromaDB ingestion and retrieval helpers for the `sydney_liveability` collection.

A single mixed-source collection holds Reddit posts/comments, sentiment
narratives, and sentiment quote chunks. Filtering by the `source`
metadata lets the agent's `search_posts` tool route a query at any one
modality without maintaining N parallel collections.

Embedding is via `sentence-transformers/all-MiniLM-L6-v2` (shared
singleton in `backend/core/embeddings.py`). Chunking is the default
`RecursiveCharacterTextSplitter(chunk_size=200, chunk_overlap=20)` so
short Reddit comments stay intact and long posts split on natural
boundaries.

Chunk IDs are deterministic — `{source}-{post_id_or_hash}-{chunk_index}` —
so reruns of the ingestion scripts upsert in place rather than
duplicating rows.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Optional

import chromadb
from chromadb.api import ClientAPI
from chromadb.api.models.Collection import Collection

from backend.config import settings

# Resolve `settings.chromadb_path` against the repo root rather than
# whatever cwd Python was started in. Without this, running ingestion
# from `backend/` writes to `backend/data/chromadb` while the FastAPI
# server (also started from `backend/`) reads the same dir — but the
# `openspec validate` step and any one-off scripts run from the repo
# root and write to a different `data/chromadb`. We standardise on the
# repo-root location.
_REPO_ROOT = Path(__file__).resolve().parents[2]


def _resolved_chromadb_path() -> str:
    raw = settings.chromadb_path
    p = Path(raw)
    if p.is_absolute():
        return str(p)
    # Strip a leading "./" so "./data/chromadb" and "data/chromadb" both
    # resolve to the same place.
    return str((_REPO_ROOT / p).resolve())

REDDIT_COLLECTION = "sydney_liveability"

# Required metadata keys on every chunk. Optional keys (post_id,
# post_score, created_utc, url) are kept verbatim when present.
_REQUIRED_METADATA = ("suburb", "source", "dimension", "chunk_index")

# Scrubbed from metadata before upsert because ChromaDB rejects None values.
_SENTINEL_NONE = ""


@lru_cache(maxsize=1)
def get_chromadb_client() -> ClientAPI:
    """Create a persistent ChromaDB client once to avoid repeated startup cost."""
    return chromadb.PersistentClient(path=_resolved_chromadb_path())


def initialize_collection(name: str = REDDIT_COLLECTION) -> Collection:
    """Get or create the named collection and return it.

    Idempotent — safe to call at backend startup and from each ingestion
    script. Sets distance metric to cosine (which matches normalised
    MiniLM embeddings).
    """
    client = get_chromadb_client()
    return client.get_or_create_collection(
        name=name,
        metadata={"hnsw:space": "cosine"},
    )


def chunk_reddit_text(text: str) -> list[str]:
    """Split free-text into ~200-char chunks with 20-char overlap.

    Returns an empty list for empty / whitespace-only input so callers
    can `for chunk in chunk_reddit_text(...)` without guarding.
    """
    if not text or not text.strip():
        return []
    splitter = _get_splitter()
    return [chunk for chunk in splitter.split_text(text) if chunk.strip()]


@lru_cache(maxsize=1)
def _get_splitter():
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    return RecursiveCharacterTextSplitter(chunk_size=200, chunk_overlap=20)


def embed_texts(texts: list[str], batch_size: int = 64) -> list[list[float]]:
    """Embed a list of texts with the shared MiniLM encoder.

    Batches internally so callers can pass thousands of chunks without
    blowing memory. Returns vectors normalised so cosine similarity is
    a dot product.
    """
    if not texts:
        return []
    from core.embeddings import get_embedder

    encoder = get_embedder()
    vectors = encoder.encode(
        texts,
        batch_size=batch_size,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    return [vec.tolist() for vec in vectors]


def _hash_text(text: str) -> str:
    """SHA-256 of text used as a stable fallback ID when no post_id exists."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _suburb_slug_for_id(suburb: str) -> str:
    """Slugify a suburb name for use inside a deterministic chunk ID."""
    return (
        (suburb or "unknown")
        .strip()
        .lower()
        .replace(" ", "_")
        .replace("-", "_")
    )


def _make_chunk_id(record: dict) -> str:
    """Deterministic ID: `{source}-{suburb_slug}-{post_id_or_hash}-{chunk_index}`.

    Suburb is part of the ID because the same Reddit thread can be a
    top-cited source under several suburbs' analyses; we want one
    distinct row per (suburb, post, chunk) so suburb-filtered retrieval
    finds it under each suburb it was attributed to.
    """
    meta = record["metadata"]
    source = meta["source"]
    suburb_slug = _suburb_slug_for_id(meta.get("suburb", ""))
    chunk_index = meta["chunk_index"]
    post_id = meta.get("post_id") or _hash_text(record["text"])
    return f"{source}-{suburb_slug}-{post_id}-{chunk_index}"


def _scrub_metadata(meta: dict[str, Any]) -> dict[str, Any]:
    """Drop None values; ChromaDB metadata only accepts str/int/float/bool."""
    return {k: (_SENTINEL_NONE if v is None else v) for k, v in meta.items()}


def upsert_chunks(records: list[dict], collection_name: str = REDDIT_COLLECTION) -> int:
    """Upsert a batch of chunk records into the collection.

    Each record SHALL be `{"text": str, "metadata": {...}}` with all four
    required metadata keys present (`suburb`, `source`, `dimension`,
    `chunk_index`). Optional metadata is preserved as-is.

    Embeds in one shot, computes deterministic IDs, then calls
    `collection.upsert`. Returns the number of records upserted.

    Empty `records` is a no-op returning 0.
    """
    if not records:
        return 0

    for record in records:
        meta = record.get("metadata", {})
        missing = [k for k in _REQUIRED_METADATA if k not in meta]
        if missing:
            msg = f"Chunk record missing required metadata: {missing}"
            raise ValueError(msg)

    # Dedupe inside the batch — chromadb's `upsert` rejects duplicate
    # IDs within a single call (it would gladly replace existing rows
    # against the persisted store, but not within one batch). Last write
    # wins, which is fine because identical IDs mean identical content
    # by construction.
    by_id: dict[str, dict] = {}
    for r in records:
        by_id[_make_chunk_id(r)] = r
    deduped = list(by_id.items())

    texts = [r["text"] for _, r in deduped]
    embeddings = embed_texts(texts)
    ids = [chunk_id for chunk_id, _ in deduped]
    metadatas = [_scrub_metadata(r["metadata"]) for _, r in deduped]

    collection = initialize_collection(collection_name)
    collection.upsert(
        ids=ids,
        embeddings=embeddings,
        documents=texts,
        metadatas=metadatas,
    )
    return len(deduped)


def _filters_to_where(filters: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    """Translate `{key: value}` filters into ChromaDB's `where` syntax.

    A single filter passes through as `{key: value}`; multiple are
    wrapped in `$and` to satisfy ChromaDB's operator requirement.
    """
    if not filters:
        return None
    cleaned = {k: v for k, v in filters.items() if v is not None}
    if not cleaned:
        return None
    if len(cleaned) == 1:
        return cleaned
    return {"$and": [{k: v} for k, v in cleaned.items()]}


def query_chunks(
    query: str,
    k: int = 5,
    filters: Optional[dict[str, Any]] = None,
    collection_name: str = REDDIT_COLLECTION,
) -> list[dict]:
    """Dense semantic search over the collection.

    Embeds `query` with MiniLM (same encoder used at ingestion so vectors
    are comparable), runs a filtered nearest-neighbour search, and
    returns up to `k` hits as `{text, metadata, distance}` tuples
    (lowest distance = most similar).
    """
    collection = initialize_collection(collection_name)
    query_embedding = embed_texts([query])[0]
    where = _filters_to_where(filters)

    raw = collection.query(
        query_embeddings=[query_embedding],
        n_results=k,
        where=where,
        include=["documents", "metadatas", "distances"],
    )

    results: list[dict] = []
    documents = (raw.get("documents") or [[]])[0]
    metadatas = (raw.get("metadatas") or [[]])[0]
    distances = (raw.get("distances") or [[]])[0]
    for doc, meta, dist in zip(documents, metadatas, distances):
        results.append(
            {
                "text": doc,
                "metadata": dict(meta) if meta else {},
                "distance": float(dist),
            }
        )
    return results


def get_collection_stats(
    top_n_suburbs: int = 10,
    collection_name: str = REDDIT_COLLECTION,
) -> dict[str, Any]:
    """Return summary stats for ingestion sanity-checking.

    Counts total chunks, breakdown by `source`, and the top-N suburbs by
    chunk count. Cheap on small collections; calls `collection.get` once
    for metadata only (no embeddings shipped over the wire).
    """
    collection = initialize_collection(collection_name)
    total = collection.count()
    if total == 0:
        return {"count": 0, "by_source": {}, "by_suburb_top_n": []}

    raw = collection.get(include=["metadatas"])
    metadatas: Iterable[dict] = raw.get("metadatas") or []
    by_source: Counter[str] = Counter()
    by_suburb: Counter[str] = Counter()
    for meta in metadatas:
        if not meta:
            continue
        by_source[str(meta.get("source", "unknown"))] += 1
        by_suburb[str(meta.get("suburb", "unknown"))] += 1

    return {
        "count": total,
        "by_source": dict(by_source),
        "by_suburb_top_n": by_suburb.most_common(top_n_suburbs),
    }
