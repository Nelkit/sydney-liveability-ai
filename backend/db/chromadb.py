"""Singleton ChromaDB client used by pipeline and query tools."""

from functools import lru_cache
from typing import Any

import chromadb
from chromadb.api import ClientAPI
from sentence_transformers import SentenceTransformer

from config import settings

REDDIT_COLLECTION = "reddit_posts"
PDF_COLLECTION = "community_insights"
UNIFIED_COLLECTION = "citizen_voices"

_EMBED_MODEL = "all-MiniLM-L6-v2"
_model: SentenceTransformer | None = None


@lru_cache(maxsize=1)
def get_chromadb_client() -> ClientAPI:
    """Create a persistent ChromaDB client once to avoid repeated startup cost."""
    return chromadb.PersistentClient(path=settings.chromadb_path)


def get_embed_model() -> SentenceTransformer:
    """Lazy-load the embedding model once per process."""
    global _model
    if _model is None:
        _model = SentenceTransformer(_EMBED_MODEL)
    return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a list of texts using all-MiniLM-L6-v2."""
    return get_embed_model().encode(texts, show_progress_bar=False).tolist()


def query_chunks(
    query: str,
    collection_name: str = UNIFIED_COLLECTION,
    k: int = 5,
    filters: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Semantic search over a ChromaDB collection.

    Returns chunks sorted by relevance, each with text, metadata, and distance.
    Supports optional filters by suburb, source, or theme.
    """
    client = get_chromadb_client()
    collection = client.get_or_create_collection(collection_name)
    query_embedding = embed_texts([query])[0]
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=k,
        where=filters or None,
        include=["documents", "metadatas", "distances"],
    )
    return [
        {"text": doc, "metadata": meta, "distance": dist}
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        )
    ]


def get_collection_stats() -> dict[str, int]:
    """Return chunk counts for all collections — useful for debugging."""
    client = get_chromadb_client()
    stats: dict[str, int] = {}
    for name in (REDDIT_COLLECTION, PDF_COLLECTION, UNIFIED_COLLECTION):
        try:
            stats[name] = client.get_collection(name).count()
        except Exception:
            stats[name] = 0
    return stats
