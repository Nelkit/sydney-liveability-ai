"""Ingest sentiment JSON outputs into PostgreSQL and ChromaDB.

Reads: data/processed/sentiment/*.json
Writes: sentiment_scores, emotion_profiles, suburb_narratives, ChromaDB `sydney_liveability`
Owner: Kai (Ying-Kai Liao)
"""

from __future__ import annotations


def main() -> None:
    """Entrypoint for sentiment multi-destination ingestion."""
    # TODO(Kai): Implement complete sentiment ingestion from JSON files.
    # 1) Iterate JSON files with glob over data/processed/sentiment/*.json.
    # 2) Parse structure keys: suburb, post_count, fetched_at, aspects, emotions, narrative, sources.
    # 3) Upsert sentiment_scores rows: one row per (suburb, aspect) with score and mentions.
    # 4) Upsert emotion_profiles row per suburb with 7 emotion fields, post_count, fetched_at.
    # 5) Upsert suburb_narratives row per suburb storing narrative and sources list in JSON column.
    # 6) Embed narrative text with all-MiniLM-L6-v2 and upsert to ChromaDB `sydney_liveability`
    #    using metadata {suburb, source="sentiment", type="narrative"}.
    # 7) Embed each sources[].text and upsert with metadata
    #    {suburb, source="sentiment", type="post"}.
    # 8) Keep source URLs in ChromaDB metadata when available for traceable citations.
    # 9) Why embed sources[].text: Synthesiser retrieves real resident quotes for grounded answers.
    pass


if __name__ == "__main__":
    main()
