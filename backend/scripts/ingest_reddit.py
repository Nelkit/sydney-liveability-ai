"""Ingest Reddit posts and comments into the `sydney_liveability` ChromaDB collection.

Reads per-suburb JSON arrays from `data/processed/reddit/*.json` (the
arctic-shift extraction pipeline's pre-processed output, where each
record carries `text`, `suburb`, `score`, `created_utc`, `url`, `type`).
The original spec phrased the source as `data/raw/reddit/*.json`; in
this repo the raw arctic dump is one big NDJSON without per-suburb
tagging, so the pre-processed per-suburb files are the canonical
ingestion input.

For each record we chunk the text with `chunk_reddit_text` (200/20),
classify each chunk's liveability dimension via the existing BART-MNLI
zero-shot classifier (top label, threshold 0.3, else `"general"`), and
upsert into ChromaDB with `source="reddit"`.

Idempotent — chunk IDs are deterministic on `(source, post_id, chunk_index)`,
so re-running over the same input replaces rather than duplicates rows.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

# Make `core`, `db`, `config` importable when run as `python backend/scripts/ingest_reddit.py`.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.nlp.aspects import classify_aspects  # noqa: E402
from db import chromadb as chroma  # noqa: E402

# Resolve relative to repo root so the script works from either cwd
# (project root or backend/). `parents[2]` of this file points at the
# repo root: backend/scripts/ingest_reddit.py -> backend/scripts ->
# backend -> repo root.
_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT_DIR = _REPO_ROOT / "data" / "processed" / "reddit"
ASPECT_THRESHOLD = 0.3
DEFAULT_BATCH_SIZE = 64

# Skip very short texts — they don't yield useful embeddings and waste
# both classifier time and ChromaDB rows.
MIN_TEXT_LEN = 20


def _post_id_from_url(url: str, fallback_text: str) -> str:
    """Extract the Reddit thread/comment id from the URL, or hash the text."""
    if url:
        # Reddit permalinks look like .../comments/{thread_id}/{slug}/[{comment_id}/]
        parts = [p for p in url.rstrip("/").split("/") if p]
        if len(parts) >= 2 and "comments" in parts:
            idx = parts.index("comments")
            tail = parts[idx + 1 :]
            if tail:
                # thread id always present; comment id appended for comments
                return "-".join(tail[:1] + tail[2:3]) if len(tail) > 2 else tail[0]
    return hashlib.sha256(fallback_text.encode("utf-8")).hexdigest()[:16]


def _top_dimension(text: str) -> str:
    """Return the top BART-MNLI label for `text`, or 'general' below threshold."""
    classifications = classify_aspects([text], threshold=ASPECT_THRESHOLD)
    if not classifications or not classifications[0]:
        return "general"
    # classify_aspects returns {dimension: confidence}; pick the highest.
    top_dim, _ = max(classifications[0].items(), key=lambda kv: kv[1])
    return top_dim


def _build_records_for_post(post: dict) -> list[dict]:
    """Chunk + classify a single post, returning ChromaDB-ready records."""
    text = (post.get("text") or "").strip()
    if len(text) < MIN_TEXT_LEN:
        return []

    suburb = post.get("suburb") or "unknown"
    url = post.get("url") or ""
    post_id = _post_id_from_url(url, text)
    score = int(post.get("score") or 0)
    created_utc = float(post.get("created_utc") or 0.0)

    chunks = chroma.chunk_reddit_text(text)
    if not chunks:
        return []

    records: list[dict] = []
    for chunk_index, chunk in enumerate(chunks):
        dimension = _top_dimension(chunk)
        records.append(
            {
                "text": chunk,
                "metadata": {
                    "suburb": suburb,
                    "source": "reddit",
                    "dimension": dimension,
                    "chunk_index": chunk_index,
                    "post_id": post_id,
                    "post_score": score,
                    "created_utc": created_utc,
                    "url": url,
                },
            }
        )
    return records


def _iter_suburb_files(input_dir: Path):
    for path in sorted(input_dir.glob("*.json")):
        if path.name.startswith("_"):
            # Skip index files like `_suburb_index.json`.
            continue
        yield path


def _flush(buffer: list[dict]) -> int:
    """Upsert and clear the buffer, returning how many records were written."""
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
    """Ingest every per-suburb JSON file under `input_dir` into ChromaDB.

    `suburb_limit` is a debugging knob — set it small to smoke-test the
    pipeline end-to-end without waiting for the full corpus.
    """
    if not input_dir.exists():
        msg = f"Input directory not found: {input_dir}"
        raise FileNotFoundError(msg)

    files = list(_iter_suburb_files(input_dir))
    if suburb_limit is not None:
        files = files[:suburb_limit]

    total_posts = 0
    total_chunks = 0
    suburbs_seen: set[str] = set()
    buffer: list[dict] = []

    for path in files:
        with open(path, "r", encoding="utf-8") as f:
            posts = json.load(f)
        if not isinstance(posts, list):
            continue
        suburb_name = path.stem
        print(f"  • {suburb_name}: {len(posts)} posts", flush=True)

        for post in posts:
            records = _build_records_for_post(post)
            if not records:
                continue
            total_posts += 1
            suburbs_seen.add(records[0]["metadata"]["suburb"])
            buffer.extend(records)
            if len(buffer) >= batch_size:
                total_chunks += _flush(buffer)

    total_chunks += _flush(buffer)
    return {
        "posts_processed": total_posts,
        "chunks_upserted": total_chunks,
        "suburbs": len(suburbs_seen),
    }


def main() -> None:
    """Entrypoint for Reddit ingestion without LLM calls."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=DEFAULT_INPUT_DIR,
        help="Directory holding per-suburb Reddit JSON files",
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

    print(f"Ingesting Reddit chunks from {args.input_dir}", flush=True)
    summary = ingest(
        input_dir=args.input_dir,
        batch_size=args.batch_size,
        suburb_limit=args.suburb_limit,
    )
    print(
        f"Done. posts_processed={summary['posts_processed']} "
        f"chunks_upserted={summary['chunks_upserted']} suburbs={summary['suburbs']}",
        flush=True,
    )

    print("Collection stats:")
    stats = chroma.get_collection_stats()
    print(json.dumps(stats, indent=2, default=str))


if __name__ == "__main__":
    main()
