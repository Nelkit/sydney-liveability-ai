"""Precompute NLP analyses for all suburbs with pre-processed Reddit data.

Reads each per-suburb JSON file under data/processed/reddit/, runs the
BART-MNLI + DistilRoBERTa + VADER + synthesis pipeline, and writes the
result to data/processed/reddit_analyses/{slug}.json.

The /api/reddit/summary and /api/reddit/{suburb} endpoints both read from
this cache, so this is the one-time step that makes the hex overview and
per-suburb pages serve instantly.

Usage (from repo root):

    python -m data_extraction.precompute_analyses
    python -m data_extraction.precompute_analyses --limit 50 --min-posts 5
    python -m data_extraction.precompute_analyses --only Newtown Glebe "Surry Hills"
    python -m data_extraction.precompute_analyses --force  # re-run even if cached
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from data_extraction.extract_reddit import (  # noqa: E402
    list_available_suburbs,
    load_suburb_posts,
)


ANALYSIS_CACHE = Path("data/processed/reddit_analyses")


def _slug(name: str) -> str:
    return name.lower().replace(" ", "_").replace("-", "_")


def _cache_path(name: str) -> Path:
    return ANALYSIS_CACHE / f"{_slug(name)}.json"


def _already_cached(name: str) -> bool:
    return _cache_path(name).exists()


def _write_cache(name: str, payload: dict) -> None:
    ANALYSIS_CACHE.mkdir(parents=True, exist_ok=True)
    path = _cache_path(name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Precompute NLP analyses for suburbs with Reddit data.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Only process this many suburbs (ordered by post count desc).",
    )
    parser.add_argument(
        "--min-posts",
        type=int,
        default=1,
        help="Skip suburbs with fewer than this many posts (default: 1).",
    )
    parser.add_argument(
        "--only",
        nargs="+",
        default=None,
        help="Process only these suburb names (overrides --limit).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-run even if a cached analysis already exists.",
    )
    args = parser.parse_args()

    # Import the pipeline lazily so --help is fast.
    from core.nlp.pipeline import analyse_suburb  # type: ignore

    if args.only:
        targets = [s for s in args.only]
    else:
        targets = list_available_suburbs()

    # Pre-load post counts so we can order by size and honour --min-posts
    index_path = Path("data/processed/reddit/_suburb_index.json")
    counts: dict[str, int] = {}
    if index_path.exists():
        with open(index_path, "r", encoding="utf-8") as f:
            idx = json.load(f)
        counts = {k: v.get("post_count", 0) for k, v in idx.items()}

    def count_for(name: str) -> int:
        return counts.get(name, 0)

    if not args.only:
        targets = [t for t in targets if count_for(t) >= args.min_posts]
        targets.sort(key=count_for, reverse=True)
        if args.limit:
            targets = targets[: args.limit]

    total = len(targets)
    print(f"Planning to precompute {total} suburb analyses")
    if not targets:
        print("Nothing to do. Run data_extraction.process_arctic_shift first?")
        return 0

    processed = 0
    skipped = 0
    failed: list[tuple[str, str]] = []
    t0 = time.time()

    for i, suburb in enumerate(targets, start=1):
        if not args.force and _already_cached(suburb):
            skipped += 1
            print(f"[{i}/{total}] {suburb}: cached, skip")
            continue

        posts = load_suburb_posts(suburb)
        if not posts:
            skipped += 1
            print(f"[{i}/{total}] {suburb}: no posts, skip")
            continue

        t_start = time.time()
        try:
            result = analyse_suburb(suburb, posts)
            payload = result.to_dict()
            _write_cache(suburb, payload)
            processed += 1
            elapsed = time.time() - t_start
            print(
                f"[{i}/{total}] {suburb}: {len(posts)} posts -> "
                f"analysis in {elapsed:.1f}s"
            )
        except Exception as exc:  # pragma: no cover - we log and continue
            failed.append((suburb, repr(exc)))
            print(f"[{i}/{total}] {suburb}: FAILED ({exc!r})")

    total_elapsed = time.time() - t0
    print("\n=== Summary ===")
    print(f"  processed: {processed}")
    print(f"  skipped:   {skipped}")
    print(f"  failed:    {len(failed)}")
    print(f"  elapsed:   {total_elapsed:.1f}s")
    if failed:
        print("\nFailures:")
        for suburb, err in failed[:10]:
            print(f"  - {suburb}: {err}")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
