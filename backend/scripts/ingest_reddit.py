"""Ingest Reddit JSON into ChromaDB embeddings collection.

Reads: data/raw/reddit/*.json
Writes: ChromaDB collection `sydney_liveability`
Owner: assign in team meeting
"""

from __future__ import annotations


def main() -> None:
    """Entrypoint for Reddit ingestion without LLM calls."""
    # TODO(owner): Implement the Reddit ingestion flow end-to-end.
    # 1) Use glob to load every JSON file from data/raw/reddit/.
    # 2) Parse each record and keep suburb, URL, and source text.
    # 3) Chunk text with RecursiveCharacterTextSplitter(chunk_size=200, chunk_overlap=20).
    # 4) Embed chunks using sentence-transformers all-MiniLM-L6-v2.
    # 5) Upsert into ChromaDB collection `sydney_liveability`.
    # 6) Write metadata per chunk: {suburb, source="reddit", chunk_index, url}.
    # 7) Ensure deterministic IDs so reruns update instead of duplicating chunks.
    pass


if __name__ == "__main__":
    main()
