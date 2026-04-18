"""Download r/sydney (or any subreddit) dumps from Arctic Shift.

Mirrors the logic of https://arctic-shift.photon-reddit.com/download-tool:
paginates through `/api/posts/search` and `/api/comments/search` using
`limit=auto&sort=asc&after=<ms>` and writes newline-delimited JSON locally.

Usage (from repo root):

    python -m data_extraction.download_arctic_shift \
        --subreddit sydney \
        --start 2024-01-01 \
        --kinds posts comments \
        --output data/raw/arctic_shift

Resumable: if the output file already exists and has data, we pick up
from the last record's timestamp.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

BASE_URL = "https://arctic-shift.photon-reddit.com/api"
USER_AGENT = "sydney-liveability-ai/0.1 (academic; bulk dump downloader)"
TIMEOUT_SECONDS = 60.0
MAX_RETRIES = 6


def _iso_to_ms(date_str: str) -> int:
    """Convert YYYY-MM-DD to Unix milliseconds at midnight UTC."""
    dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def _ms_to_iso(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat()


def _last_timestamp_ms(path: Path) -> int | None:
    """Read the last NDJSON record and return its created_utc in ms, or None."""
    if not path.exists() or path.stat().st_size == 0:
        return None
    # Read the file from the end looking for the last complete line.
    with open(path, "rb") as f:
        f.seek(0, os.SEEK_END)
        size = f.tell()
        if size == 0:
            return None
        chunk_size = 4096
        tail = b""
        while size > 0:
            read_size = min(chunk_size, size)
            size -= read_size
            f.seek(size)
            tail = f.read(read_size) + tail
            if tail.count(b"\n") >= 2:
                break
        lines = [line for line in tail.split(b"\n") if line.strip()]
        if not lines:
            return None
        try:
            last = json.loads(lines[-1])
        except json.JSONDecodeError:
            # Truncated last line - try second to last
            if len(lines) >= 2:
                try:
                    last = json.loads(lines[-2])
                except json.JSONDecodeError:
                    return None
            else:
                return None
    created = last.get("created_utc")
    if not created:
        return None
    return int(float(created) * 1000)


def _download_stream(
    kind: str,
    subreddit: str,
    start_ms: int,
    end_ms: int | None,
    output_path: Path,
    client: httpx.Client,
    min_delay: float = 0.8,
) -> dict:
    """Paginate an Arctic Shift endpoint and append NDJSON to output_path."""
    endpoint = f"{BASE_URL}/{kind}/search"

    cursor_ms = _last_timestamp_ms(output_path)
    if cursor_ms is not None:
        # Resume one millisecond past the last seen record
        cursor_ms += 1
        print(
            f"  Resuming {kind} from {_ms_to_iso(cursor_ms)} (file exists, last record found)"
        )
    else:
        cursor_ms = start_ms
        print(f"  Starting {kind} from {_ms_to_iso(cursor_ms)}")

    records_written = 0
    calls = 0
    retry_count = 0
    t0 = time.time()

    with open(output_path, "a", encoding="utf-8") as f:
        while True:
            if end_ms is not None and cursor_ms >= end_ms:
                break

            params = {
                "subreddit": subreddit,
                "limit": "auto",
                "sort": "asc",
                "after": cursor_ms,
                "meta-app": "sydney-liveability-ai",
            }
            try:
                resp = client.get(endpoint, params=params, timeout=TIMEOUT_SECONDS)
            except httpx.HTTPError as exc:
                retry_count += 1
                wait = min(30.0, 2.0 * retry_count)
                print(f"  HTTP error: {exc!r}. Retry {retry_count}/{MAX_RETRIES} in {wait}s")
                if retry_count >= MAX_RETRIES:
                    raise
                time.sleep(wait)
                continue

            if resp.status_code == 429:
                # Rate limited
                reset = resp.headers.get("x-ratelimit-reset") or "30"
                wait = float(reset)
                print(f"  Rate limited (429). Sleeping {wait}s")
                time.sleep(wait)
                continue

            if resp.status_code == 422:
                # Arctic Shift returns 422 for transient timeouts ("Timeout.
                # Maybe slow down a bit").  Back off and retry.
                retry_count += 1
                wait = min(30.0, 3.0 * retry_count)
                body = resp.text[:160]
                print(
                    f"  422 from API ({body}). Retry {retry_count}/{MAX_RETRIES} in {wait}s"
                )
                if retry_count >= MAX_RETRIES:
                    raise RuntimeError(f"Persistent 422: {body}")
                time.sleep(wait)
                continue

            if resp.status_code >= 500:
                retry_count += 1
                wait = min(30.0, 2.0 * retry_count)
                print(
                    f"  Server error {resp.status_code}. Retry {retry_count}/{MAX_RETRIES} in {wait}s"
                )
                if retry_count >= MAX_RETRIES:
                    raise RuntimeError(f"Persistent server error: {resp.status_code}")
                time.sleep(wait)
                continue

            if resp.status_code != 200:
                raise RuntimeError(
                    f"Unexpected status {resp.status_code}: {resp.text[:200]}"
                )

            retry_count = 0
            payload = resp.json()
            data = payload.get("data") or []
            error = payload.get("error")

            if error:
                raise RuntimeError(f"API error: {error}")

            if not data:
                print(f"  {kind}: reached end of stream.")
                break

            # Append NDJSON
            for record in data:
                f.write(json.dumps(record, ensure_ascii=False))
                f.write("\n")
            f.flush()

            records_written += len(data)
            calls += 1

            last_created_utc = data[-1].get("created_utc")
            if last_created_utc is None:
                print("  Warning: record missing created_utc, stopping.")
                break

            new_cursor = int(float(last_created_utc) * 1000) + 1
            if new_cursor <= cursor_ms:
                # Avoid infinite loop if timestamps don't advance
                new_cursor = cursor_ms + 1000
            cursor_ms = new_cursor

            # Log progress
            remaining_hdr = resp.headers.get("x-ratelimit-remaining")
            elapsed = time.time() - t0
            rate = records_written / elapsed if elapsed > 0 else 0
            print(
                f"  [{kind}] call #{calls}: +{len(data)} (total {records_written}) "
                f"cursor={_ms_to_iso(cursor_ms)} "
                f"rate={rate:.0f}/s rl-remaining={remaining_hdr}"
            )

            time.sleep(min_delay)

    total_elapsed = time.time() - t0
    return {
        "kind": kind,
        "records": records_written,
        "calls": calls,
        "elapsed_seconds": round(total_elapsed, 1),
    }


def download(
    subreddit: str,
    kinds: list[str],
    start: str,
    end: str | None,
    output_dir: Path,
    min_delay: float = 0.8,
) -> list[dict]:
    """Download one or more streams (posts/comments) for a subreddit."""
    output_dir.mkdir(parents=True, exist_ok=True)
    start_ms = _iso_to_ms(start)
    end_ms = _iso_to_ms(end) if end else None

    results = []
    with httpx.Client(
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
    ) as client:
        for kind in kinds:
            if kind not in ("posts", "comments"):
                raise ValueError(f"Unknown kind: {kind}")
            filename = f"{subreddit}_{kind}.ndjson"
            output_path = output_dir / filename
            print(f"\n=== Downloading {kind} to {output_path} ===")
            summary = _download_stream(
                kind=kind,
                subreddit=subreddit,
                start_ms=start_ms,
                end_ms=end_ms,
                output_path=output_path,
                client=client,
                min_delay=min_delay,
            )
            summary["output_path"] = str(output_path)
            results.append(summary)

    return results


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Download subreddit dumps from Arctic Shift.",
    )
    parser.add_argument("--subreddit", default="sydney", help="Subreddit name.")
    parser.add_argument(
        "--start",
        default="2024-01-01",
        help="Start date YYYY-MM-DD (inclusive).",
    )
    parser.add_argument(
        "--end",
        default=None,
        help="Optional end date YYYY-MM-DD. Omit to stream until now.",
    )
    parser.add_argument(
        "--kinds",
        nargs="+",
        default=["posts", "comments"],
        choices=["posts", "comments"],
        help="Which streams to download.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/raw/arctic_shift"),
        help="Output directory.",
    )
    parser.add_argument(
        "--min-delay",
        type=float,
        default=0.8,
        help="Seconds to sleep between calls (stay under rate limit).",
    )

    args = parser.parse_args()

    results = download(
        subreddit=args.subreddit,
        kinds=args.kinds,
        start=args.start,
        end=args.end,
        output_dir=args.output,
        min_delay=args.min_delay,
    )

    print("\n=== Download summary ===")
    for r in results:
        print(
            f"  {r['kind']:8s}  records={r['records']:,}  "
            f"calls={r['calls']}  elapsed={r['elapsed_seconds']}s  "
            f"file={r['output_path']}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
