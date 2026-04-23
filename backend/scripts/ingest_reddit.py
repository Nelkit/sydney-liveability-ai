"""Ingest Reddit JSON into ChromaDB embeddings collection.

Reads: data/processed/reddit/*.json  (one file per suburb, 563 files, ~20k records)
Writes: ChromaDB collection `reddit_posts`
Owner: Kai (Ying-Kai Liao) / Juan David Rodriguez
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from langchain_text_splitters import RecursiveCharacterTextSplitter

from db.chromadb import REDDIT_COLLECTION, embed_texts, get_chromadb_client

_REDDIT_DIR = Path(__file__).parents[2] / "data/processed/reddit"
_MIN_TEXT_LENGTH = 50
_BATCH_SIZE = 256


def chunk_text(text: str) -> list[str]:
    splitter = RecursiveCharacterTextSplitter(chunk_size=200, chunk_overlap=20)
    return splitter.split_text(text)


def _upsert_batch(
    texts: list[str],
    metadatas: list[dict[str, Any]],
    ids: list[str],
) -> None:
    collection = get_chromadb_client().get_or_create_collection(REDDIT_COLLECTION)
    collection.upsert(
        ids=ids,
        documents=texts,
        embeddings=embed_texts(texts),
        metadatas=metadatas,
    )


def main() -> None:
    suburb_files = sorted(
        f for f in _REDDIT_DIR.glob("*.json") if not f.name.startswith("_")
    )

    batch_texts: list[str] = []
    batch_metadatas: list[dict[str, Any]] = []
    batch_ids: list[str] = []
    total_written = 0
    skipped = 0

    for file in suburb_files:
        records: list[dict[str, Any]] = json.loads(file.read_text())

        for record_idx, record in enumerate(records):
            text = (record.get("text") or "").strip()

            if len(text) < _MIN_TEXT_LENGTH:
                skipped += 1
                continue

            suburb = record.get("suburb") or file.stem.replace("_", " ").title()
            url = record.get("url") or ""
            score = int(record.get("score") or 0)
            created_utc = int(record.get("created_utc") or 0)
            post_type = record.get("type") or "post"

            for chunk_idx, chunk in enumerate(chunk_text(text)):
                if not chunk.strip():
                    skipped += 1
                    continue

                batch_texts.append(chunk)
                batch_metadatas.append({
                    "suburb": suburb,
                    "source": "reddit",
                    "url": url,
                    "score": score,
                    "created_utc": created_utc,
                    "type": post_type,
                    "chunk_index": chunk_idx,
                })
                batch_ids.append(f"reddit_{file.stem}_{record_idx}_{chunk_idx}")

                if len(batch_texts) >= _BATCH_SIZE:
                    _upsert_batch(batch_texts, batch_metadatas, batch_ids)
                    total_written += len(batch_texts)
                    batch_texts, batch_metadatas, batch_ids = [], [], []

    if batch_texts:
        _upsert_batch(batch_texts, batch_metadatas, batch_ids)
        total_written += len(batch_texts)

    print(f"Ingested {total_written} chunks from {len(suburb_files)} suburb files ({skipped} records skipped).")


if __name__ == "__main__":
    main()
