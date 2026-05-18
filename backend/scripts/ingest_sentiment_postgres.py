"""Ingest reddit_analyses JSON files into PostgreSQL sentiment tables.

Reads: data/processed/reddit_analyses/{suburb}.json
Writes: PostgreSQL tables sentiment_scores, emotion_profiles, suburb_narratives

Run:
    python -m scripts.ingest_sentiment_postgres
    python -m scripts.ingest_sentiment_postgres --suburb-limit 5   # smoke test

Depends on:
    - data/processed/reddit_analyses/ must exist
    - make db-upgrade must have been run
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy.dialects.postgresql import insert

from db.models import EmotionProfile, SentimentScore, SuburbNarrative
from db.postgres import SessionLocal

_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT_DIR = _REPO_ROOT / "data" / "processed" / "reddit_analyses"
BATCH_SIZE = 100


def _parse_fetched_at(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
        return dt.replace(tzinfo=None)
    except (ValueError, TypeError):
        return None


def _coerce_file(
    path: Path,
) -> tuple[list[dict], dict, dict] | None:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        print(f"  [WARN] Skipping {path.name} — unreadable")
        return None

    suburb = data.get("suburb") or path.stem.replace("_", " ").title()
    aspects: dict[str, Any] = data.get("aspects") or {}
    emotions: dict[str, Any] = data.get("emotions") or {}

    aspect_rows = [
        {
            "suburb": suburb,
            "aspect": aspect_name,
            "score": entry.get("score"),
            "mentions": entry.get("mentions"),
            "confidence": entry.get("confidence"),
            "coverage": entry.get("coverage"),
            "source": entry.get("source"),
        }
        for aspect_name, entry in aspects.items()
        if isinstance(entry, dict)
    ]

    emotion_row = {
        "suburb": suburb,
        "joy": emotions.get("joy"),
        "surprise": emotions.get("surprise"),
        "neutral": emotions.get("neutral"),
        "sadness": emotions.get("sadness"),
        "anger": emotions.get("anger"),
        "fear": emotions.get("fear"),
        "disgust": emotions.get("disgust"),
        "post_count": data.get("post_count"),
        "fetched_at": _parse_fetched_at(data.get("fetched_at")),
        "confidence": data.get("confidence"),
        "confidence_tier": data.get("confidence_tier"),
    }

    narrative_row = {
        "suburb": suburb,
        "narrative": data.get("narrative"),
        "sources": data.get("sources"),
    }

    return aspect_rows, emotion_row, narrative_row


def _upsert_aspects(rows: list[dict]) -> None:
    if not rows:
        return
    stmt = insert(SentimentScore.__table__).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["suburb", "aspect"],
        set_={
            col: stmt.excluded[col]
            for col in ["score", "mentions", "confidence", "coverage", "source"]
        },
    )
    with SessionLocal() as session:
        session.execute(stmt)
        session.commit()


def _upsert_emotions(rows: list[dict]) -> None:
    if not rows:
        return
    stmt = insert(EmotionProfile.__table__).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["suburb"],
        set_={
            col: stmt.excluded[col]
            for col in [
                "joy", "surprise", "neutral", "sadness",
                "anger", "fear", "disgust",
                "post_count", "fetched_at", "confidence", "confidence_tier",
            ]
        },
    )
    with SessionLocal() as session:
        session.execute(stmt)
        session.commit()


def _upsert_narratives(rows: list[dict]) -> None:
    if not rows:
        return
    stmt = insert(SuburbNarrative.__table__).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["suburb"],
        set_={col: stmt.excluded[col] for col in ["narrative", "sources"]},
    )
    with SessionLocal() as session:
        session.execute(stmt)
        session.commit()


def ingest(
    input_dir: Path = DEFAULT_INPUT_DIR,
    batch_size: int = BATCH_SIZE,
    suburb_limit: int | None = None,
) -> dict:
    files = sorted(p for p in input_dir.glob("*.json") if not p.name.startswith("_"))
    if suburb_limit is not None:
        files = files[:suburb_limit]

    aspect_buf: list[dict] = []
    emotion_buf: list[dict] = []
    narrative_buf: list[dict] = []
    files_read = 0
    errors = 0

    for path in files:
        result = _coerce_file(path)
        if result is None:
            errors += 1
            continue

        aspect_rows, emotion_row, narrative_row = result
        aspect_buf.extend(aspect_rows)
        emotion_buf.append(emotion_row)
        narrative_buf.append(narrative_row)
        files_read += 1

        if len(emotion_buf) >= batch_size:
            _upsert_aspects(aspect_buf)
            _upsert_emotions(emotion_buf)
            _upsert_narratives(narrative_buf)
            aspect_buf.clear()
            emotion_buf.clear()
            narrative_buf.clear()
            print(f"  flushed {files_read} suburbs...", flush=True)

    _upsert_aspects(aspect_buf)
    _upsert_emotions(emotion_buf)
    _upsert_narratives(narrative_buf)

    return {
        "files_read": files_read,
        "suburbs_written": files_read,
        "aspect_rows": files_read * 8,
        "errors": errors,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    parser.add_argument("--suburb-limit", type=int, default=None)
    args = parser.parse_args()

    print(f"Ingesting from {args.input_dir}", flush=True)
    summary = ingest(
        input_dir=args.input_dir,
        batch_size=args.batch_size,
        suburb_limit=args.suburb_limit,
    )
    print(summary)


if __name__ == "__main__":
    main()
