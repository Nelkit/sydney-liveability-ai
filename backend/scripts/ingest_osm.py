"""Ingest OSM feature aggregates into PostgreSQL osm_scores table.

Owner: Luis Robinson

Reads: data/processed/osm_data.csv
Writes: PostgreSQL table `osm_scores`

Run:
    python -m scripts.ingest_osm

Depends on:
    - data/processed/osm_data.csv must exist
    - make db-upgrade must have been run
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy.dialects.postgresql import insert

from db.models import OsmScore
from db.postgres import SessionLocal


CSV_PATH = Path(__file__).resolve().parents[2] / "data/processed/osm_data.csv"
BATCH_SIZE = 200
REQUIRED_COLUMNS = {"suburb"}
AMENITY_COLUMNS = (
    "cafe",
    "restaurant",
    "gym",
    "school",
    "hospital",
    "pharmacy",
    "library",
    "park",
    "playground",
    "sports_centre",
)


def _load_csv(csv_path: Path) -> pd.DataFrame:
    if not csv_path.exists():
        raise FileNotFoundError(f"OSM CSV not found: {csv_path}")

    frame = pd.read_csv(csv_path)
    frame.columns = [col.strip() for col in frame.columns]
    missing = sorted(REQUIRED_COLUMNS - set(frame.columns))
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")
    return frame


def _nullable_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        if isinstance(value, float) and math.isnan(value):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _nullable_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        if isinstance(value, float) and math.isnan(value):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_row(row: pd.Series) -> dict[str, Any]:
    suburb = str(row["suburb"]).strip()
    if not suburb or suburb.lower() == "nan":
        raise ValueError("suburb is empty")

    payload: dict[str, Any] = {
        "suburb": suburb,
        "osm_score": _nullable_float(row.get("osm_score")),
    }
    for col in AMENITY_COLUMNS:
        payload[col] = _nullable_int(row.get(col))
    return payload


def _upsert_batch(rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0

    stmt = insert(OsmScore.__table__).values(rows)
    update_map = {"osm_score": stmt.excluded.osm_score}
    for col in AMENITY_COLUMNS:
        update_map[col] = getattr(stmt.excluded, col)

    upsert_stmt = stmt.on_conflict_do_update(index_elements=["suburb"], set_=update_map)

    with SessionLocal() as session:
        session.execute(upsert_stmt)
        session.commit()
    return len(rows)


def main() -> None:
    frame = _load_csv(CSV_PATH)
    valid_rows: list[dict[str, Any]] = []
    malformed_rows: list[dict[str, Any]] = []

    for row_index, row in frame.iterrows():
        try:
            valid_rows.append(_coerce_row(row))
        except Exception as exc:
            malformed_rows.append({"row_index": int(row_index), "error": str(exc)})

    rows_written = 0
    for start in range(0, len(valid_rows), BATCH_SIZE):
        rows_written += _upsert_batch(valid_rows[start : start + BATCH_SIZE])

    print(
        {
            "rows_read": int(len(frame)),
            "rows_written": rows_written,
            "malformed_rows": malformed_rows,
        }
    )


if __name__ == "__main__":
    main()
