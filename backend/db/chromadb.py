"""Singleton ChromaDB client used by pipeline and query tools."""

from functools import lru_cache
from typing import Any

import chromadb
from chromadb.api import ClientAPI

from config import settings

# TODO(rag): Define collection names as constants.
# - REDDIT_COLLECTION = "reddit_posts"
# - PDF_COLLECTION = "community_insights"
# - UNIFIED_COLLECTION = "citizen_voices"
#
# TODO(rag): Add `initialize_collections()`.
# - Create/get all required collections at startup.
# - Set collection metadata (source, description, schema version).
# - Ensure idempotent startup behavior.
#
# TODO(rag): Add chunking helpers.
# - `chunk_reddit_text(text: str) -> list[str]`
# - `chunk_pdf_text(text: str) -> list[str]`
# - Keep chunk size and overlap configurable from settings.
#
# TODO(rag): Add embedding provider wrapper.
# - `embed_texts(texts: list[str]) -> list[list[float]]`
# - Keep provider/model configurable (sentence-transformers or API-based).
# - Cache/embed in batches to reduce latency.
#
# TODO(rag): Add ingestion APIs.
# - `upsert_reddit_chunks(records: list[dict[str, Any]])`
# - `upsert_pdf_chunks(records: list[dict[str, Any]])`
# - Enforce required metadata: suburb, source, theme.
# - Include optional metadata: post_id, score, created_utc, page_number.
#
# TODO(rag): Add semantic retrieval API.
# - `query_chunks(query: str, k: int = 5, filters: dict[str, Any] | None = None)`
# - Support filters by suburb/source/theme.
# - Return text + metadata + distance for citations.
#
# TODO(rag): Add maintenance APIs.
# - `get_collection_stats()` for observability.
# - `reset_collections()` for local development/testing.
# - `delete_by_source(source: str)` for partial re-indexing.
#
# TODO(rag): Add validation safeguards.
# - Skip empty/short chunks.
# - De-duplicate by deterministic chunk id.
# - Log failed embeddings/upserts with enough context for retries.
@lru_cache(maxsize=1)
def get_chromadb_client() -> ClientAPI:
    """Create a persistent ChromaDB client once to avoid repeated startup cost."""
    return chromadb.PersistentClient(path=settings.chromadb_path)
