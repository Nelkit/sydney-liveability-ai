"""Shared liveability scoring logic.

Single source of truth for the weighted liveability formula used by
both the /api/civic endpoint and the synthesiser agent.
"""

from __future__ import annotations

import threading
from typing import Any

from geoalchemy2 import Geography
from geoalchemy2.functions import ST_Centroid, ST_Distance, ST_MakePoint, ST_SetSRID
from sqlalchemy import cast, func, select

from db.models import Bocsar, OsmScore, SentimentScore, Suburb, TransportScore
from db.postgres import SessionLocal

CBD_LAT = -33.8688
CBD_LNG = 151.2093
MAX_DIST_M = 35_000.0

# ---------------------------------------------------------------------------
# In-process cache — raw DB rows loaded once, reused across requests.
# The suburb dataset is static for this project; no TTL needed.
# _CACHE_LOCK ensures concurrent requests don't all race to populate the cache.
# ---------------------------------------------------------------------------
_RAW_CACHE: dict[str, Any] | None = None
_CACHE_LOCK = threading.Lock()


def _clamp_unit(value: float | None) -> float:
    if value is None:
        return 0.0
    numeric = float(value)
    if numeric > 1.0:
        numeric = numeric / 100.0
    return max(0.0, min(1.0, numeric))


def _inverse_normalise(values: dict[str, float]) -> dict[str, float]:
    if not values:
        return {}
    min_v = min(values.values())
    max_v = max(values.values())
    if max_v == min_v:
        return {k: 0.5 for k in values}
    return {k: 1.0 - ((v - min_v) / (max_v - min_v)) for k, v in values.items()}


def _load_raw(suburb_filter: list[str] | None = None) -> dict[str, Any]:
    """Load raw rows from DB. Returns pre-computed per-suburb component scores."""
    with SessionLocal() as session:
        cbd_point = ST_SetSRID(ST_MakePoint(CBD_LNG, CBD_LAT), 4326)
        distance_expr = ST_Distance(
            cast(ST_Centroid(Suburb.geometry), Geography),
            cast(cbd_point, Geography),
        ).label("distance_m")

        suburbs_q = select(Suburb)
        if suburb_filter:
            suburbs_q = suburbs_q.where(Suburb.suburb.in_(suburb_filter))
        suburbs = session.scalars(suburbs_q).all()

        distance_q = select(Suburb.suburb, distance_expr)
        if suburb_filter:
            distance_q = distance_q.where(Suburb.suburb.in_(suburb_filter))
        distance_rows = session.execute(distance_q).all()

        sentiment_q = select(SentimentScore)
        if suburb_filter:
            sentiment_q = sentiment_q.where(SentimentScore.suburb.in_(suburb_filter))
        sentiment_rows = session.scalars(sentiment_q).all()

        osm_q = select(OsmScore)
        if suburb_filter:
            osm_q = osm_q.where(OsmScore.suburb.in_(suburb_filter))
        osm_rows = session.scalars(osm_q).all()

        transport_q = select(TransportScore)
        if suburb_filter:
            transport_q = transport_q.where(TransportScore.suburb.in_(suburb_filter))
        transport_rows = session.scalars(transport_q).all()

        latest_crime_year = session.scalar(select(func.max(Bocsar.year)))
        crime_counts: dict[str, float] = {}
        if latest_crime_year is not None:
            crime_q = (
                select(Bocsar.suburb, func.sum(Bocsar.incident_count))
                .where(Bocsar.year == latest_crime_year)
                .group_by(Bocsar.suburb)
            )
            if suburb_filter:
                crime_q = crime_q.where(Bocsar.suburb.in_(suburb_filter))
            crime_counts = {
                str(s): float(t or 0.0)
                for s, t in session.execute(crime_q).all()
            }

    sentiment_by_suburb: dict[str, dict[str, float]] = {}
    for row in sentiment_rows:
        if row.score is not None:
            sentiment_by_suburb.setdefault(row.suburb, {})[row.aspect] = float(row.score)

    osm_by_suburb = {row.suburb: row for row in osm_rows}
    transport_by_suburb = {row.suburb: row for row in transport_rows}
    safety_by_suburb = _inverse_normalise(crime_counts)
    proximity_by_suburb = {
        str(suburb): max(0.0, 1.0 - (float(distance_m or MAX_DIST_M) / MAX_DIST_M))
        for suburb, distance_m in distance_rows
    }

    # Pre-compute the weight-independent components for each suburb
    components: dict[str, dict[str, Any]] = {}
    for row in suburbs:
        sentiment = sentiment_by_suburb.get(row.suburb, {})
        osm_row = osm_by_suburb.get(row.suburb)
        transport_row = transport_by_suburb.get(row.suburb)

        safety_score = safety_by_suburb.get(row.suburb, 0.5)
        facilities_component = _clamp_unit(row.facilities_score)
        osm_component = _clamp_unit(osm_row.osm_score if osm_row else None)
        transport_component = _clamp_unit(transport_row.transport_score if transport_row else None)
        walkability_component = _clamp_unit(row.walkability_score)
        gis_combined = (
            (transport_component * 0.50)
            + (walkability_component * 0.20)
            + (facilities_component * 0.15)
            + (osm_component * 0.15)
        )
        lifestyle_score = _clamp_unit(
            sentiment.get("community", sentiment.get("lifestyle", row.facilities_score))
        )
        nightlife_score = _clamp_unit(
            sentiment.get("nightlife", sentiment.get("community", row.facilities_score))
        )
        affordability_score = _clamp_unit(sentiment.get("affordability", 0.5))
        proximity_score = _clamp_unit(proximity_by_suburb.get(row.suburb, 0.0))

        components[row.suburb] = {
            "safety": safety_score,
            "transport": gis_combined,
            "lifestyle": lifestyle_score,
            "affordability": affordability_score,
            "nightlife": nightlife_score,
            "proximity": proximity_score,
            "_row": row,
        }

    return components


def _get_raw(suburb_filter: list[str] | None) -> dict[str, Any]:
    """Return cached components for all suburbs; fall back to filtered DB load."""
    global _RAW_CACHE
    # Full scan (suburb_filter=None) → cache globally under lock so concurrent
    # requests don't all race to call _load_raw at the same time.
    if suburb_filter is None:
        if _RAW_CACHE is None:
            with _CACHE_LOCK:
                if _RAW_CACHE is None:  # double-checked locking
                    _RAW_CACHE = _load_raw(None)
        return _RAW_CACHE
    # Filtered scan → check if all requested suburbs are already in cache
    if _RAW_CACHE is not None:
        if all(s in _RAW_CACHE for s in suburb_filter):
            return {s: _RAW_CACHE[s] for s in suburb_filter if s in _RAW_CACHE}
    return _load_raw(suburb_filter)


def compute_liveability_scores(
    weights: dict[str, float],
    suburb_filter: list[str] | None = None,
) -> dict[str, dict[str, Any]]:
    """Compute weighted liveability scores for suburbs.

    Args:
        weights: Dict with keys safety, transport, lifestyle, affordability,
                 nightlife, proximity — must sum to 1.0.
        suburb_filter: When provided, only compute scores for those suburbs.
                       Pass None to score all suburbs (used by /api/civic).

    Returns:
        Dict mapping suburb name to a score breakdown.
    """
    w_safety = float(weights.get("safety", 0.25))
    w_transport = float(weights.get("transport", 0.25))
    w_lifestyle = float(weights.get("lifestyle", 0.25))
    w_affordability = float(weights.get("affordability", 0.25))
    w_nightlife = float(weights.get("nightlife", 0.0))
    w_proximity = float(weights.get("proximity", 0.0))

    components = _get_raw(suburb_filter)

    results: dict[str, dict[str, Any]] = {}
    for suburb, c in components.items():
        liveability_score = (
            (c["safety"] * w_safety)
            + (c["transport"] * w_transport)
            + (c["lifestyle"] * w_lifestyle)
            + (c["affordability"] * w_affordability)
            + (c["nightlife"] * w_nightlife)
            + (c["proximity"] * w_proximity)
        )
        results[suburb] = {
            "liveability": round(liveability_score, 4),
            "safety": round(c["safety"], 4),
            "transport": round(c["transport"], 4),
            "lifestyle": round(c["lifestyle"], 4),
            "affordability": round(c["affordability"], 4),
            "nightlife": round(c["nightlife"], 4),
            "proximity": round(c["proximity"], 4),
            "_row": c["_row"],
        }

    return results
