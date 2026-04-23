"""Ingest community PDF text into ChromaDB embeddings collection.

Reads: data/processed/community_reports/community_report.json
Writes: ChromaDB collection `sydney_liveability`
Owner: Juan David Rodriguez
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from langchain_text_splitters import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer

from db.chromadb import get_chromadb_client

_JSON_PATH = Path(__file__).parents[2] / "data/processed/community_reports/community_report.json"
_COLLECTION_NAME = "sydney_liveability"
_EMBED_MODEL = "all-MiniLM-L6-v2"
_BATCH_SIZE = 256

_model: SentenceTransformer | None = None


def get_embed_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(_EMBED_MODEL)
    return _model


def chunk_text(text: str) -> list[str]:
    splitter = RecursiveCharacterTextSplitter(chunk_size=200, chunk_overlap=20)
    return splitter.split_text(text)


def _upsert_batch(
    texts: list[str],
    metadatas: list[dict[str, Any]],
    ids: list[str],
) -> None:
    model = get_embed_model()
    client = get_chromadb_client()
    collection = client.get_or_create_collection(_COLLECTION_NAME)
    embeddings = model.encode(texts, show_progress_bar=False).tolist()
    collection.upsert(ids=ids, documents=texts, embeddings=embeddings, metadatas=metadatas)


def main() -> None:
    records: list[dict[str, Any]] = json.loads(_JSON_PATH.read_text())

    batch_texts: list[str] = []
    batch_metadatas: list[dict[str, Any]] = []
    batch_ids: list[str] = []
    total_written = 0
    skipped = 0

    for record_idx, record in enumerate(records):
        text = (record.get("text") or "").strip()
        if not text:
            skipped += 1
            continue

        suburb = record.get("suburb") or "Unknown"
        theme = record.get("theme") or ""
        report = record.get("source") or ""
        page_number = int(record.get("page_number") or 0)

        for chunk_idx, chunk in enumerate(chunk_text(text)):
            if not chunk.strip():
                skipped += 1
                continue

            batch_texts.append(chunk)
            batch_metadatas.append({
                "suburb": suburb,
                "source": "pdf",
                "theme": theme,
                "report": report,
                "page_number": page_number,
                "chunk_index": chunk_idx,
            })
            batch_ids.append(f"pdf_{record_idx}_{chunk_idx}")

            if len(batch_texts) >= _BATCH_SIZE:
                _upsert_batch(batch_texts, batch_metadatas, batch_ids)
                total_written += len(batch_texts)
                batch_texts, batch_metadatas, batch_ids = [], [], []

    if batch_texts:
        _upsert_batch(batch_texts, batch_metadatas, batch_ids)
        total_written += len(batch_texts)

    print(f"Ingested {total_written} chunks from {len(records)} records ({skipped} skipped).")


if __name__ == "__main__":
    main()
