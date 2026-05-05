---
name: chromadb-embed
description: 'Embed text and write chunks to ChromaDB for the Sydney Liveability Explorer backend using MiniLM, deterministic chunk IDs, and required metadata fields. Use when creating or updating PDF/Reddit/sentiment ingestion or retrieval helpers.'
argument-hint: 'Source type and target chunks, e.g. pdf community-insights chunks'
license: Apache-2.0
metadata:
  author: gentleman-programming
  version: "1.0"
---

# ChromaDB Embed Skill

## When To Use
- You need to embed text and persist chunks to ChromaDB.
- You are building helpers for Reddit, PDF, or sentiment narrative ingestion.
- You need a repeatable chunking + metadata convention for RAG.

## Context
- ChromaDB client lives in `backend/db/chromadb.py`.
- Use the project helper that returns the persistent ChromaDB client, then access the `sydney_liveability` collection.
- Embeddings use `sentence-transformers` model `all-MiniLM-L6-v2`.
- Chunking uses LangChain `RecursiveCharacterTextSplitter(chunk_size=200, chunk_overlap=20)`.
- No LLM calls: this skill is embedding and storage only.

## Critical Patterns
- Always upsert, never blindly add duplicates.
- IDs must be deterministic: `f"{suburb}_{source}_{chunk_index}"`.
- Metadata must always include `suburb`, `source`, and `chunk_index` at minimum.
- Metadata values must be primitive types only: strings, ints, or floats.
- Keep the embedder lazy-loaded with a module-level singleton to avoid repeated startup cost.
- Keep source-specific metadata consistent because the synthesiser relies on it for citations and filtering.

## Standard Workflow
1. Split text into chunks with `RecursiveCharacterTextSplitter`.
2. Build deterministic IDs from suburb, source, and chunk index.
3. Construct metadata for each chunk.
4. Validate metadata has required fields and primitive values only.
5. Load the embedding model lazily.
6. Encode all chunks in batches.
7. Upsert into the `sydney_liveability` collection.
8. Return the number of written chunks and any skipped records.

## Source Metadata Conventions
| source | required metadata fields | notes |
| --- | --- | --- |
| `pdf` | `suburb`, `source="pdf"`, `theme`, `page_number`, `chunk_index` | preserve page citations |
| `reddit` | `suburb`, `source="reddit"`, `url`, `chunk_index` | keep permalink for retrieval |
| `sentiment` | `suburb`, `source="sentiment"`, `type="narrative"`, `chunk_index` | narrative or post-level text |

## Decision Rules
- If text is too short or empty: skip it and count it.
- If metadata is missing required keys: reject the chunk before embedding.
- If a chunk is duplicated: reuse the same deterministic ID so upsert replaces it.
- If the collection is absent: create or retrieve `sydney_liveability` before writing.
- If source-specific metadata differs from the convention above: align it before merge.

## Quality Gates
- Uses `all-MiniLM-L6-v2` for embeddings.
- Uses `RecursiveCharacterTextSplitter(chunk_size=200, chunk_overlap=20)`.
- Uses deterministic chunk IDs.
- Uses ChromaDB upsert semantics.
- Preserves metadata required for retrieval and citation.
- Does not call any LLM.

## Template
```python
from __future__ import annotations

from typing import Any

from langchain.text_splitter import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer

from db.chromadb import get_chromadb_client

EMBED_MODEL = "all-MiniLM-L6-v2"
_COLLECTION_NAME = "sydney_liveability"
_model: SentenceTransformer | None = None


def get_embed_model() -> SentenceTransformer:
    """Lazy-load the embedding model once per process."""
    global _model
    if _model is None:
        _model = SentenceTransformer(EMBED_MODEL)
    return _model


def chunk_text(text: str) -> list[str]:
    """Split text into fixed-size chunks for embedding."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=200,
        chunk_overlap=20,
    )
    return splitter.split_text(text)


def embed_and_store(texts: list[str], metadatas: list[dict[str, Any]], ids: list[str]) -> int:
    """Embed texts and upsert them into ChromaDB."""
    model = get_embed_model()
    client = get_chromadb_client()
    collection = client.get_or_create_collection(_COLLECTION_NAME)

    embeddings = model.encode(texts, show_progress_bar=False).tolist()
    collection.upsert(
        ids=ids,
        documents=texts,
        embeddings=embeddings,
        metadatas=metadatas,
    )
    return len(texts)
```

## Commands
```bash
cd backend
python -m scripts.ingest_reddit
python -m scripts.ingest_pdf
```

## Integration Notes
- Use this skill from ingestion helpers, not from query-time code.
- Keep metadata aligned with `backend/agents/query/synthesiser.py` retrieval needs.
- If you add a new source, document its metadata convention in this skill first.

## Prompt Starters
- "Use chromadb-embed skill to chunk and upsert PDF community insight text."
- "Refactor backend/scripts/ingest_reddit.py to follow chromadb-embed conventions."
- "Create a helper that embeds sentiment narratives using chromadb-embed skill."
