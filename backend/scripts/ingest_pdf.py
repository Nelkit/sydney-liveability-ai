"""Ingest community PDF text into ChromaDB embeddings collection.

Reads: data/raw/community_report.pdf
Writes: ChromaDB collection `sydney_liveability`
Owner: Juan David Rodriguez
"""

from __future__ import annotations


def main() -> None:
    """Entrypoint for PDF ingestion without LLM calls."""
    # TODO(Juan David): Implement PDF ingestion with page-aware metadata.
    # 1) Read data/raw/community_report.pdf using pypdf PdfReader.
    # 2) Extract text page by page and skip empty pages.
    # 3) Infer suburb from page text when possible; fallback to "Unknown".
    # 4) Chunk extracted text with RecursiveCharacterTextSplitter(200, 20).
    # 5) Embed chunks with all-MiniLM-L6-v2 sentence-transformers model.
    # 6) Upsert to `sydney_liveability` in ChromaDB.
    # 7) Store metadata: {suburb, source="pdf", chunk_index, page_number}.
    pass


if __name__ == "__main__":
    main()
