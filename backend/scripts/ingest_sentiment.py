"""Ingest sentiment-pipeline outputs into the `sydney_liveability` ChromaDB collection.

Reads `data/processed/reddit_analyses/{suburb}.json` — the
`SuburbAnalysis` payloads produced by `backend/core/nlp/pipeline.py`.
Each file holds:
- `narrative`: a 2–4 sentence summary of the suburb's Reddit discourse
- `sources[]`: the curated top-K Reddit posts/comments (text + url + score)

We embed both into ChromaDB so the agent's `search_posts` tool can
retrieve sentiment-grade evidence (rather than just raw posts) when the
user asks "what do residents say about X".

Distinguished by `source` metadata:
- `source="sentiment_narrative"` — the LLM-summarised narrative
- `source="sentiment_quote"` — the curated source post text

Idempotent — chunk IDs are deterministic, so reruns upsert in place.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

# Make `core`, `db`, `config` importable when run as `python backend/scripts/ingest_sentiment.py`.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from db import chromadb as chroma  # noqa: E402

# Resolve relative to repo root so the script works from either cwd
# (project root or backend/).
_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT_DIR = _REPO_ROOT / "data" / "processed" / "reddit_analyses"
DEFAULT_BATCH_SIZE = 64
MIN_TEXT_LEN = 20


def _hash_id(prefix: str, text: str) -> str:
    return f"{prefix}-{hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]}"


def _post_id_from_url(url: str) -> str | None:
    if not url:
        return None
    parts = [p for p in url.rstrip("/").split("/") if p]
    if "comments" in parts:
        idx = parts.index("comments")
        tail = parts[idx + 1 :]
        if tail:
            return "-".join(tail[:1] + tail[2:3]) if len(tail) > 2 else tail[0]
    return None


def _records_for_narrative(suburb: str, narrative: str) -> list[dict]:
    if not narrative or len(narrative.strip()) < MIN_TEXT_LEN:
        return []
    chunks = chroma.chunk_reddit_text(narrative)
    if not chunks:
        return []
    post_id = _hash_id("narrative", suburb + narrative)
    return [
        {
            "text": chunk,
            "metadata": {
                "suburb": suburb,
                "source": "sentiment_narrative",
                # Narratives summarise the whole suburb across dimensions —
                # not classifying per chunk avoids spurious specificity.
                "dimension": "general",
                "chunk_index": idx,
                "post_id": post_id,
            },
        }
        for idx, chunk in enumerate(chunks)
    ]


def _records_for_quote(suburb: str, quote: dict) -> list[dict]:
    text = (quote.get("text") or "").strip()
    if len(text) < MIN_TEXT_LEN:
        return []
    chunks = chroma.chunk_reddit_text(text)
    if not chunks:
        return []
    url = quote.get("url") or ""
    score = int(quote.get("score") or 0)
    post_id = _post_id_from_url(url) or _hash_id("quote", text)
    return [
        {
            "text": chunk,
            "metadata": {
                "suburb": suburb,
                "source": "sentiment_quote",
                # The aspect/dimension a quote was selected for is not
                # stored on the source entry; leave as "general" and let
                # downstream filters rely on suburb + source instead.
                "dimension": "general",
                "chunk_index": idx,
                "post_id": post_id,
                "post_score": score,
                "url": url,
            },
        }
        for idx, chunk in enumerate(chunks)
    ]


def _flush(buffer: list[dict]) -> int:
    if not buffer:
        return 0
    written = chroma.upsert_chunks(buffer)
    buffer.clear()
    return written


def ingest(
    input_dir: Path = DEFAULT_INPUT_DIR,
    batch_size: int = DEFAULT_BATCH_SIZE,
    suburb_limit: int | None = None,
) -> dict:
    if not input_dir.exists():
        msg = f"Input directory not found: {input_dir}"
        raise FileNotFoundError(msg)

    files = sorted(p for p in input_dir.glob("*.json") if not p.name.startswith("_"))
    if suburb_limit is not None:
        files = files[:suburb_limit]

    suburbs_seen: set[str] = set()
    narrative_chunks = 0
    quote_chunks = 0
    buffer: list[dict] = []

    for path in files:
        with open(path, "r", encoding="utf-8") as f:
            try:
                analysis = json.load(f)
            except json.JSONDecodeError:
                continue
        suburb = analysis.get("suburb") or path.stem.replace("_", " ").title()
        suburbs_seen.add(suburb)

        narrative_records = _records_for_narrative(suburb, analysis.get("narrative", ""))
        narrative_chunks += len(narrative_records)
        buffer.extend(narrative_records)

        for quote in analysis.get("sources") or []:
            if not isinstance(quote, dict):
                continue
            quote_records = _records_for_quote(suburb, quote)
            quote_chunks += len(quote_records)
            buffer.extend(quote_records)

        if len(buffer) >= batch_size:
            _flush(buffer)

    _flush(buffer)
    return {
        "suburbs": len(suburbs_seen),
        "narrative_chunks": narrative_chunks,
        "quote_chunks": quote_chunks,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=DEFAULT_INPUT_DIR,
        help="Directory holding per-suburb SuburbAnalysis JSON files",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help="ChromaDB upsert batch size",
    )
    parser.add_argument(
        "--suburb-limit",
        type=int,
        default=None,
        help="Process only the first N suburb files (for smoke tests)",
    )
    args = parser.parse_args()

    print(f"Ingesting sentiment narratives + quotes from {args.input_dir}", flush=True)
    summary = ingest(
        input_dir=args.input_dir,
        batch_size=args.batch_size,
        suburb_limit=args.suburb_limit,
    )
    print(
        f"Done. suburbs={summary['suburbs']} "
        f"narrative_chunks={summary['narrative_chunks']} "
        f"quote_chunks={summary['quote_chunks']}",
        flush=True,
    )

    print("Collection stats:")
    stats = chroma.get_collection_stats()
    print(json.dumps(stats, indent=2, default=str))


if __name__ == "__main__":
    main()
