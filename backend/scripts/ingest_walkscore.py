"""Populate `suburbs.walkability_score` from the Walk Score API.

Reads suburb geometries from PostgreSQL, derives a point on each suburb
polygon, and queries https://api.walkscore.com/score for the walkability
score. The script only updates the `walkability_score` column so it can be
run independently from the ArcGIS facilities ingestion.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Any

import requests

# Make `db` importable when run as `python backend/scripts/ingest_walkscore.py`.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:  # noqa: SIM105 - keep the script importable in lightweight test envs.
    from sqlalchemy import text
except ModuleNotFoundError:  # pragma: no cover - exercised when SQLAlchemy is absent.
    text = None  # type: ignore[assignment]

try:  # noqa: SIM105 - allow helper tests to import this module without DB deps.
    from db.postgres import SessionLocal
except ModuleNotFoundError:  # pragma: no cover - exercised when DB deps are absent.
    SessionLocal = None  # type: ignore[assignment]

try:  # noqa: SIM105 - allow helper tests to import this module without config.
    from config import settings
except ModuleNotFoundError:  # pragma: no cover - exercised when config deps are absent.
    settings = None  # type: ignore[assignment]


DEFAULT_LIMIT = None
DEFAULT_SLEEP_SECONDS = 1.0
DEFAULT_TIMEOUT_SECONDS = 15.0
DEFAULT_RETRIES = 2


def _resolve_api_key() -> str:
    """Return the Walk Score API key from config."""
    if settings is None:
        raise ModuleNotFoundError("config module is required to resolve API key")
    api_key = settings.walkscore_api_key.strip()
    if not api_key:
        msg = "Missing Walk Score API key. Set WALKSCORE_API_KEY in backend/.env."
        raise ValueError(msg)
    return api_key


def _load_targets(session, refresh_all: bool = False) -> list[dict[str, Any]]:
    """Load suburb points to score from PostGIS."""
    if text is None:
        raise ModuleNotFoundError("sqlalchemy is required to load Walk Score targets")
    query = text(
        """
        SELECT
            sal_code,
            suburb,
            walkability_score,
            ST_Y(ST_PointOnSurface(geometry)) AS lat,
            ST_X(ST_PointOnSurface(geometry)) AS lon
        FROM suburbs
        WHERE geometry IS NOT NULL
        ORDER BY suburb
        """
    )
    rows = session.execute(query).mappings().all()
    targets: list[dict[str, Any]] = []
    for row in rows:
        if not refresh_all and row["walkability_score"] is not None:
            continue
        if row["lat"] is None or row["lon"] is None:
            continue
        targets.append(dict(row))
    return targets


def _build_request_params(suburb: str, lat: float, lon: float, api_key: str) -> dict[str, Any]:
    """Build the query string for the Walk Score score endpoint."""
    return {
        "format": "json",
        "address": f"{suburb}, Sydney NSW, Australia",
        "lat": f"{lat:.6f}",
        "lon": f"{lon:.6f}",
        "transit": 1,
        "bike": 1,
        "wsapikey": api_key,
    }


def _extract_walkscore_score(payload: dict[str, Any]) -> float | None:
    """Extract a numeric walkability score from the API response payload."""
    score = payload.get("walkscore")
    if score is None:
        return None
    try:
        return float(score)
    except (TypeError, ValueError):
        return None


def _fetch_walkscore(client: requests.Session, suburb: str, lat: float, lon: float, api_key: str) -> dict[str, Any]:
    """Call the Walk Score API with retries and basic error handling."""
    params = _build_request_params(suburb, lat, lon, api_key)
    url = "https://api.walkscore.com/score"

    last_error: Exception | None = None
    for attempt in range(1, DEFAULT_RETRIES + 1):
        try:
            response = client.get(url, params=params, timeout=DEFAULT_TIMEOUT_SECONDS)
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            if attempt == DEFAULT_RETRIES:
                break
            time.sleep(DEFAULT_SLEEP_SECONDS * attempt)

    msg = f"Walk Score request failed for {suburb}"
    raise RuntimeError(msg) from last_error


def _update_walkability_score(session, sal_code: str, walkability_score: float | None) -> None:
    """Persist a single walkability score into the suburbs table."""
    if text is None:
        raise ModuleNotFoundError("sqlalchemy is required to update Walk Score values")
    session.execute(
        text(
            """
            UPDATE suburbs
            SET walkability_score = :walkability_score
            WHERE sal_code = :sal_code
            """
        ),
        {"sal_code": sal_code, "walkability_score": walkability_score},
    )


def ingest(refresh_all: bool = False, limit: int | None = DEFAULT_LIMIT) -> dict[str, int]:
    """Populate `walkability_score` for suburbs with geometry."""
    if SessionLocal is None:
        raise ModuleNotFoundError("database dependencies are required to run Walk Score ingestion")
    api_key = _resolve_api_key()
    client = requests.Session()

    with SessionLocal() as session:
        targets = _load_targets(session, refresh_all=refresh_all)
        if limit is not None:
            targets = targets[:limit]

        total = len(targets)
        updated = 0
        skipped = 0
        failed = 0

        for index, row in enumerate(targets, start=1):
            suburb = str(row["suburb"]).strip()
            sal_code = str(row["sal_code"]).strip()
            lat = float(row["lat"])
            lon = float(row["lon"])

            print(f"[walkscore] {index}/{total}: {suburb} ({sal_code})", flush=True)
            try:
                payload = _fetch_walkscore(client, suburb, lat, lon, api_key)
                score = _extract_walkscore_score(payload)
                if score is None:
                    skipped += 1
                    print(
                        f"[walkscore] no numeric score for {suburb}; status={payload.get('status')}",
                        flush=True,
                    )
                    continue

                _update_walkability_score(session, sal_code, score)
                session.commit()
                updated += 1
            except Exception as exc:
                session.rollback()
                failed += 1
                print(f"[walkscore] failed for {suburb}: {exc}", flush=True)

    return {"targets": total, "updated": updated, "skipped": skipped, "failed": failed}


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for Walk Score ingestion."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--refresh-all",
        action="store_true",
        help="Refresh all suburbs, even if walkability_score is already populated.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process only the first N suburbs (for smoke tests).",
    )
    args = parser.parse_args(argv)

    summary = ingest(refresh_all=args.refresh_all, limit=args.limit)
    print(
        "Done. "
        f"targets={summary['targets']} updated={summary['updated']} "
        f"skipped={summary['skipped']} failed={summary['failed']}",
        flush=True,
    )
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())