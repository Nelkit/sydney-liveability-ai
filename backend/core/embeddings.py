"""Shared sentence-transformer singleton.

Both the coverage-detection step (`backend/core/nlp/coverage.py`) and the
ChromaDB ingestion / retrieval helpers (`backend/db/chromadb.py`) need to
embed text with `sentence-transformers/all-MiniLM-L6-v2`. Loading the
model twice in the same process wastes ~80 MB of RAM and a few seconds of
startup. This module exposes a memoised accessor so every caller shares a
single instance.
"""

from __future__ import annotations

from functools import lru_cache

EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
from sentence_transformers import SentenceTransformer
MODEL = SentenceTransformer("all-MiniLM-L6-v2")

@lru_cache(maxsize=1)
def get_embedder():
    """Return the shared `SentenceTransformer` instance."""
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(EMBEDDING_MODEL_NAME)
