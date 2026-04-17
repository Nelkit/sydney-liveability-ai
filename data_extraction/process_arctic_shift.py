"""Process Arctic Shift r/sydney dumps into per-suburb JSON files.

Downloads from https://arctic-shift.photon-reddit.com/download-tool
produce JSON (or zst-compressed JSON) files of posts and comments.

Usage:
    python -m data_extraction.process_arctic_shift \
        --submissions data/raw/arctic_shift/sydney_submissions.json \
        --comments data/raw/arctic_shift/sydney_comments.json \
        --output data/processed/reddit/ \
        --min-score 2
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from data_extraction.sydney_suburbs import (
    build_suburb_matcher,
    detect_suburbs,
)

MIN_SCORE_DEFAULT = 2


@dataclass
class RedditPost:
    """Mirrors the dataclass in extract_reddit.py."""

    text: str
    suburb: str
    score: int
    created_utc: float
    url: str
    type: str  # "post" or "comment"
    aspect_query: str


# ---------------------------------------------------------------------------
# File reading helpers
# ---------------------------------------------------------------------------

def _open_file(path: Path):
    """Open a JSON or zst-compressed file, returning a file-like object."""
    if path.suffix == ".zst":
        try:
            import zstandard as zstd
        except ImportError:
            print(
                "Error: zstandard package required for .zst files. "
                "Install with: pip install zstandard",
                file=sys.stderr,
            )
            sys.exit(1)
        fh = open(path, "rb")
        dctx = zstd.ZstdDecompressor()
        return dctx.stream_reader(fh)
    return open(path, "r", encoding="utf-8")


def _iter_records(path: Path):
    """Yield parsed JSON records from a file.

    Handles both JSON arrays and newline-delimited JSON (NDJSON).
    """
    raw = _open_file(path)

    # For zst files, read all bytes then decode
    if path.suffix == ".zst":
        content = raw.read().decode("utf-8")
        raw.close()
    else:
        content = raw.read()
        raw.close()

    content = content.strip()

    # Try JSON array first
    if content.startswith("["):
        records = json.loads(content)
        yield from records
        return

    # Fall back to newline-delimited JSON
    for line in content.split("\n"):
        line = line.strip()
        if line:
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


# ---------------------------------------------------------------------------
# Processing logic
# ---------------------------------------------------------------------------

def _permalink_to_url(record: dict) -> str:
    """Extract a Reddit URL from a record."""
    permalink = record.get("permalink", "")
    if permalink:
        return f"https://reddit.com{permalink}"
    # Fallback: construct from ID
    record_id = record.get("id", "unknown")
    return f"https://reddit.com/r/sydney/comments/{record_id}/"


def process_submissions(
    path: Path,
    pattern,
    match_to_canonical: dict[str, str],
    min_score: int,
) -> dict[str, list[dict]]:
    """Process submissions file and return per-suburb post dicts."""
    suburb_posts: dict[str, list[dict]] = defaultdict(list)
    total = 0
    matched = 0

    print(f"Processing submissions: {path}")

    for record in _iter_records(path):
        total += 1

        score = record.get("score", 0)
        if score < min_score:
            continue

        title = record.get("title", "")
        selftext = record.get("selftext", "")
        text = f"{title}\n{selftext}".strip() if selftext else title

        if not text:
            continue

        suburbs = detect_suburbs(text, pattern, match_to_canonical)
        if not suburbs:
            continue

        matched += 1
        url = _permalink_to_url(record)
        created_utc = record.get("created_utc", 0)
        if isinstance(created_utc, str):
            try:
                created_utc = float(created_utc)
            except ValueError:
                created_utc = 0

        for suburb in suburbs:
            post = RedditPost(
                text=text,
                suburb=suburb,
                score=score,
                created_utc=created_utc,
                url=url,
                type="post",
                aspect_query="bulk",
            )
            suburb_posts[suburb].append(asdict(post))

        if total % 10000 == 0:
            print(f"  ... {total:,} posts scanned, {matched:,} matched")

    print(f"  Done: {total:,} posts scanned, {matched:,} matched suburbs")
    return suburb_posts


def process_comments(
    path: Path,
    pattern,
    match_to_canonical: dict[str, str],
    min_score: int,
) -> dict[str, list[dict]]:
    """Process comments file and return per-suburb comment dicts."""
    suburb_posts: dict[str, list[dict]] = defaultdict(list)
    total = 0
    matched = 0

    print(f"Processing comments: {path}")

    for record in _iter_records(path):
        total += 1

        score = record.get("score", 0)
        if score < min_score:
            continue

        text = record.get("body", "")
        if not text or text in ("[deleted]", "[removed]"):
            continue

        suburbs = detect_suburbs(text, pattern, match_to_canonical)
        if not suburbs:
            continue

        matched += 1
        url = _permalink_to_url(record)
        created_utc = record.get("created_utc", 0)
        if isinstance(created_utc, str):
            try:
                created_utc = float(created_utc)
            except ValueError:
                created_utc = 0

        for suburb in suburbs:
            post = RedditPost(
                text=text,
                suburb=suburb,
                score=score,
                created_utc=created_utc,
                url=url,
                type="comment",
                aspect_query="bulk",
            )
            suburb_posts[suburb].append(asdict(post))

        if total % 50000 == 0:
            print(f"  ... {total:,} comments scanned, {matched:,} matched")

    print(f"  Done: {total:,} comments scanned, {matched:,} matched suburbs")
    return suburb_posts


def _merge_suburb_data(
    *sources: dict[str, list[dict]],
) -> dict[str, list[dict]]:
    """Merge multiple suburb data dicts into one."""
    merged: dict[str, list[dict]] = defaultdict(list)
    for source in sources:
        for suburb, posts in source.items():
            merged[suburb].extend(posts)
    return merged


def _suburb_slug(name: str) -> str:
    return name.lower().replace(" ", "_").replace("-", "_")


def write_output(
    suburb_data: dict[str, list[dict]],
    output_dir: Path,
) -> None:
    """Write per-suburb JSON files, index, and metadata."""
    output_dir.mkdir(parents=True, exist_ok=True)

    index: dict[str, dict] = {}
    total_posts = 0

    for suburb in sorted(suburb_data.keys()):
        posts = suburb_data[suburb]
        # Sort by score descending within each suburb
        posts.sort(key=lambda p: p["score"], reverse=True)

        slug = _suburb_slug(suburb)
        filepath = output_dir / f"{slug}.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(posts, f, indent=2, ensure_ascii=False)

        index[suburb] = {
            "file": f"{slug}.json",
            "post_count": len(posts),
        }
        total_posts += len(posts)
        print(f"  {suburb}: {len(posts):,} posts")

    # Write index
    index_path = output_dir / "_suburb_index.json"
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2, ensure_ascii=False)

    # Write metadata
    metadata = {
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "suburbs_with_data": len(index),
        "total_posts": total_posts,
    }
    metadata_path = output_dir / "_metadata.json"
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    print(f"\nSummary:")
    print(f"  Suburbs with data: {len(index)}")
    print(f"  Total posts/comments: {total_posts:,}")
    print(f"  Output directory: {output_dir}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Process Arctic Shift r/sydney data into per-suburb JSON files.",
    )
    parser.add_argument(
        "--submissions",
        type=Path,
        help="Path to submissions JSON/NDJSON/zst file.",
    )
    parser.add_argument(
        "--comments",
        type=Path,
        help="Path to comments JSON/NDJSON/zst file.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/reddit"),
        help="Output directory for per-suburb JSON files (default: data/processed/reddit).",
    )
    parser.add_argument(
        "--min-score",
        type=int,
        default=MIN_SCORE_DEFAULT,
        help=f"Minimum score filter (default: {MIN_SCORE_DEFAULT}).",
    )
    args = parser.parse_args()

    if not args.submissions and not args.comments:
        parser.error("At least one of --submissions or --comments is required.")

    # Build suburb matcher
    print("Building suburb matcher...")
    pattern, match_to_canonical = build_suburb_matcher()
    print(f"  Loaded {len(match_to_canonical)} suburb patterns\n")

    sources: list[dict[str, list[dict]]] = []

    if args.submissions:
        if not args.submissions.exists():
            print(f"Error: File not found: {args.submissions}", file=sys.stderr)
            sys.exit(1)
        sources.append(
            process_submissions(args.submissions, pattern, match_to_canonical, args.min_score)
        )
        print()

    if args.comments:
        if not args.comments.exists():
            print(f"Error: File not found: {args.comments}", file=sys.stderr)
            sys.exit(1)
        sources.append(
            process_comments(args.comments, pattern, match_to_canonical, args.min_score)
        )
        print()

    # Merge and write
    print("Writing per-suburb files...")
    merged = _merge_suburb_data(*sources)
    write_output(merged, args.output)


if __name__ == "__main__":
    main()
