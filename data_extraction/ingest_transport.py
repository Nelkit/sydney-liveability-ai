"""
ingest_transport.py - Load GTFS-derived transport scores into PostgreSQL.

Reads data/processed/transport_scores.json (produced by extract_transport.py)
and upserts each suburb's row into the `transport_scores` table defined by
the TransportScore ORM model in backend/db/models.py.

Two columns extend the schema beyond the original spec:
- avg_services_per_hour (Float): mean peak-hour service frequency at stops in suburb
- stop_count (Integer): total GTFS stops within the suburb polygon

These require an Alembic migration (see migrations/versions/<id>_add_gtfs_columns.py).
After this script's first run, downstream agents read transport_score and
avg_services_per_hour to surface frequency information in the UI.

Usage
-----
    # First time only: apply the migration
    make db-upgrade

    # Then ingest:
    python data_extraction/ingest_transport.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from sqlalchemy.dialects.postgresql import insert as pg_insert

# Add repo root and backend/ to path so backend imports (which use bare
# imports like `from config import settings`) resolve when run as a script.
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "backend"))

from backend.db.models import TransportScore  # noqa: E402
from backend.db.postgres import SessionLocal  # noqa: E402

# ---- Configuration ----
INPUT_FILE = REPO_ROOT / "data" / "processed" / "transport_scores.json"
SOURCE_TAG = "gtfs"


def load_scores() -> dict:
    """Load the JSON output of extract_transport.py."""
    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"{INPUT_FILE} not found. "
            f"Run `python data_extraction/extract_transport.py` first."
        )
    with open(INPUT_FILE) as f:
        return json.load(f)


def upsert_scores(session, scores: dict) -> int:
    """Upsert each suburb's transport metrics into the transport_scores table.

    Uses PostgreSQL ON CONFLICT to handle reruns idempotently. Re-running this
    script after rerunning extract_transport.py is safe and overwrites prior values.
    """
    rows = []
    for suburb, metrics in scores.items():
        rows.append({
            "suburb": suburb,
            "transport_score": metrics.get("transport_score"),
            "avg_services_per_hour": metrics.get("avg_services_per_hour"),
            "stop_count": metrics.get("stop_count"),
            "source": SOURCE_TAG,
            # Other columns (bus_stops, train_stations, light_rail_stops,
            # bike_paths_km, avg_commute_min) intentionally left null. They
            # belong to other data sources and will be populated by separate
            # ingestion scripts if/when those datasets are integrated.
        })

    stmt = pg_insert(TransportScore).values(rows)
    update_cols = {
        "transport_score": stmt.excluded.transport_score,
        "avg_services_per_hour": stmt.excluded.avg_services_per_hour,
        "stop_count": stmt.excluded.stop_count,
        "source": stmt.excluded.source,
    }
    upsert_stmt = stmt.on_conflict_do_update(
        index_elements=["suburb"],
        set_=update_cols,
    )
    session.execute(upsert_stmt)
    session.commit()
    return len(rows)


def verify_ingestion(session, expected_count: int) -> None:
    """Confirm every row was written and surface a quick summary."""
    actual = (
        session.query(TransportScore)
        .filter(TransportScore.source == SOURCE_TAG)
        .count()
    )
    if actual != expected_count:
        print(
            f"WARNING: expected {expected_count} rows tagged source='{SOURCE_TAG}', "
            f"found {actual}. Investigate before downstream agents read this table."
        )
    else:
        print(f"Verified: {actual} rows in transport_scores with source='{SOURCE_TAG}'")

    top5 = (
        session.query(TransportScore)
        .filter(TransportScore.source == SOURCE_TAG)
        .order_by(TransportScore.transport_score.desc())
        .limit(5)
        .all()
    )
    print("\nTop 5 by transport_score:")
    for row in top5:
        print(
            f"  {row.suburb:30s}  score={row.transport_score:.3f}  "
            f"svc/hr={row.avg_services_per_hour:.2f}  stops={row.stop_count}"
        )


def main() -> int:
    print(f"Loading {INPUT_FILE}")
    scores = load_scores()
    print(f"  {len(scores)} suburbs to ingest")

    db = SessionLocal()
    try:
        print("Upserting to transport_scores table")
        n = upsert_scores(db, scores)
        print(f"  {n} rows upserted")
        verify_ingestion(db, expected_count=n)
    finally:
        db.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
