"""Ingest ArcGIS facilities CSV into PostgreSQL suburbs table.

Reads: data/processed/arcgis_facilities.csv
Writes: PostgreSQL table `suburbs`
Owner: Nelkit Chavez
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import geopandas as gpd
import pandas as pd
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import OperationalError

from db.models import Suburb
from db.postgres import SessionLocal


CSV_PATH = Path("data/processed/arcgis_suburbs.csv")
GEOJSON_PATH = Path("data/raw/arcgis/suburbs.geojson")
BATCH_SIZE = 200
GEOMETRY_UPDATE_BATCH_SIZE = 50
GEOMETRY_UPDATE_RETRIES = 3
REQUIRED_COLUMNS = {
    "sal_code",
    "suburb",
    "car_share_bays_count",
    "libraries_count",
    "mobility_parking_count",
    "sports_facilities_count",
    "total_facilities",
    "facilities_score",
}


def _load_csv(csv_path: Path) -> pd.DataFrame:
    """Load ArcGIS CSV and validate mandatory schema before ingestion."""
    if not csv_path.exists():
        raise FileNotFoundError(f"ArcGIS CSV not found: {csv_path}")

    frame = pd.read_csv(csv_path)
    frame.columns = [column.strip() for column in frame.columns]
    missing_columns = sorted(REQUIRED_COLUMNS - set(frame.columns))
    if missing_columns:
        raise ValueError(f"Missing required columns: {', '.join(missing_columns)}")
    return frame


def _coerce_row(row: pd.Series) -> dict[str, Any]:
    """Convert one CSV row into a validated payload for the suburbs upsert."""
    sal_code = str(row["sal_code"]).strip()
    suburb = str(row["suburb"]).strip()
    if not sal_code or sal_code.lower() == "nan":
        raise ValueError("sal_code is empty")
    if not suburb or suburb.lower() == "nan":
        raise ValueError("suburb is empty")

    return {
        "sal_code": sal_code,
        "suburb": suburb,
        "car_share_bays_count": int(row["car_share_bays_count"]),
        "libraries_count": int(row["libraries_count"]),
        "mobility_parking_count": int(row["mobility_parking_count"]),
        "sports_facilities_count": int(row["sports_facilities_count"]),
        "total_facilities": int(row["total_facilities"]),
        # Keep source score as-is; it is pre-computed upstream.
        "facilities_score": float(row["facilities_score"]),
    }


def _upsert_batch(rows: list[dict[str, Any]]) -> int:
    """Upsert one batch into suburbs table and return number of attempted rows."""
    if not rows:
        return 0

    stmt = insert(Suburb.__table__).values(rows)
    update_map = {
        "suburb": stmt.excluded.suburb,
        "car_share_bays_count": stmt.excluded.car_share_bays_count,
        "libraries_count": stmt.excluded.libraries_count,
        "mobility_parking_count": stmt.excluded.mobility_parking_count,
        "sports_facilities_count": stmt.excluded.sports_facilities_count,
        "total_facilities": stmt.excluded.total_facilities,
        "facilities_score": stmt.excluded.facilities_score,
    }
    upsert_stmt = stmt.on_conflict_do_update(index_elements=["sal_code"], set_=update_map)

    with SessionLocal() as session:
        session.execute(upsert_stmt)
        session.commit()
    return len(rows)


def _pick_suburb_name(row: pd.Series) -> str:
    """Return best-effort suburb label from supported ArcGIS columns."""
    for key in ("suburb", "SAL_NAME21", "sal_name21", "name"):
        value = row.get(key)
        if value is None:
            continue
        suburb = str(value).strip()
        if suburb and suburb.lower() != "nan":
            return suburb
    return ""


def _pick_sal_code(row: pd.Series) -> str:
    """Return best-effort SAL code from supported ArcGIS columns."""
    for key in ("sal_code", "SAL_CODE21", "sal_code21"):
        value = row.get(key)
        if value is None:
            continue
        sal_code = str(value).strip()
        if sal_code and sal_code.lower() != "nan":
            return sal_code
    return ""


def _sync_suburb_geometry(geojson_path: Path = GEOJSON_PATH) -> dict[str, int]:
    """Update suburbs.geometry from GeoJSON polygons using PostGIS."""
    if not geojson_path.exists():
        return {"geometry_rows": 0, "geometry_updated": 0, "geometry_skipped": 0}

    gdf = gpd.read_file(geojson_path)
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    else:
        gdf = gdf.to_crs("EPSG:4326")

    total_rows = int(len(gdf))

    updated = 0
    skipped = 0

    by_code_params: list[dict[str, str]] = []
    by_name_params: list[dict[str, str]] = []

    for index, row in gdf.iterrows():
        sal_code = _pick_sal_code(row)
        suburb = _pick_suburb_name(row)
        geometry = row.get("geometry")

        progress_label = suburb or sal_code or "unknown-suburb"
        print(f"[geometry-sync] {int(index) + 1}/{total_rows}: {progress_label}")

        if geometry is None or geometry.is_empty:
            skipped += 1
            continue

        geom_wkt = geometry.wkt
        if sal_code:
            by_code_params.append({"sal_code": sal_code, "geom": geom_wkt})
            continue

        if suburb:
            by_name_params.append({"suburb": suburb, "geom": geom_wkt})
            continue

        skipped += 1

    by_code_params.sort(key=lambda item: item["sal_code"])
    by_name_params.sort(key=lambda item: item["suburb"].lower())

    with SessionLocal() as session:
        # Prevent concurrent geometry sync runs from deadlocking each other.
        session.execute(text("SELECT pg_advisory_lock(hashtext('sync_suburb_geometry'))"))
        try:
            if by_code_params:
                print(f"[geometry-sync] applying {len(by_code_params)} updates by sal_code")
                updated += _apply_geometry_updates_in_batches(
                    session=session,
                    params=by_code_params,
                    statement=text(
                        """
                        UPDATE suburbs
                        SET geometry = ST_GeomFromText(:geom, 4326)
                        WHERE sal_code = :sal_code
                        """
                    ),
                    key_name="sal_code",
                )

            if by_name_params:
                print(f"[geometry-sync] applying {len(by_name_params)} updates by suburb name")
                updated += _apply_geometry_updates_in_batches(
                    session=session,
                    params=by_name_params,
                    statement=text(
                        """
                        UPDATE suburbs
                        SET geometry = ST_GeomFromText(:geom, 4326)
                        WHERE LOWER(suburb) = LOWER(:suburb)
                        """
                    ),
                    key_name="suburb",
                )
        finally:
            session.execute(text("SELECT pg_advisory_unlock(hashtext('sync_suburb_geometry'))"))
            session.commit()

    attempted = len(by_code_params) + len(by_name_params)
    if updated < attempted:
        skipped += attempted - updated

    return {
        "geometry_rows": int(len(gdf)),
        "geometry_updated": int(updated),
        "geometry_skipped": int(skipped),
    }


def _is_deadlock_error(exc: OperationalError) -> bool:
    """Return True when DB exception corresponds to PostgreSQL deadlock."""
    orig = getattr(exc, "orig", None)
    return getattr(orig, "pgcode", None) == "40P01"


def _apply_geometry_updates_in_batches(
    session: Any,
    params: list[dict[str, str]],
    statement: Any,
    key_name: str,
) -> int:
    """Apply geometry updates in deterministic chunks with deadlock retries."""
    total_updated = 0
    for start in range(0, len(params), GEOMETRY_UPDATE_BATCH_SIZE):
        chunk = params[start : start + GEOMETRY_UPDATE_BATCH_SIZE]
        first_key = chunk[0].get(key_name, "")
        last_key = chunk[-1].get(key_name, "")

        for attempt in range(1, GEOMETRY_UPDATE_RETRIES + 1):
            try:
                result = session.execute(statement, chunk)
                session.commit()

                if result.rowcount and result.rowcount > 0:
                    total_updated += int(result.rowcount)

                print(
                    f"[geometry-sync] batch {start + 1}-{start + len(chunk)} committed "
                    f"({key_name}: {first_key} -> {last_key})"
                )
                break
            except OperationalError as exc:
                session.rollback()
                if not _is_deadlock_error(exc) or attempt == GEOMETRY_UPDATE_RETRIES:
                    raise

                backoff_seconds = 0.2 * attempt
                print(
                    f"[geometry-sync] deadlock on batch {start + 1}-{start + len(chunk)}; "
                    f"retry {attempt}/{GEOMETRY_UPDATE_RETRIES} in {backoff_seconds:.1f}s"
                )
                time.sleep(backoff_seconds)

    return total_updated


def main() -> None:
    """Entrypoint for ArcGIS facilities ingestion."""
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

    geometry_sync = _sync_suburb_geometry()

    print(
        {
            "rows_read": int(len(frame)),
            "rows_written": int(rows_written),
            "malformed_rows": malformed_rows,
            **geometry_sync,
        }
    )

if __name__ == "__main__":
    main()
