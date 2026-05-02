"""Shared liveability scoring logic.

Single source of truth for the weighted liveability formula used by
both the /api/civic endpoint and the synthesiser agent.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select

from db.models import Bocsar, OsmScore, SentimentScore, Suburb, TransportScore
from db.postgres import SessionLocal


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


def compute_liveability_scores(
    weights: dict[str, float],
    suburb_filter: list[str] | None = None,
) -> dict[str, dict[str, Any]]:
    """Compute weighted liveability scores for suburbs.

    Args:
        weights: Dict with keys safety, transport, lifestyle, affordability,
                 nightlife — must sum to 1.0.
        suburb_filter: When provided, only compute scores for those suburbs.
                       Pass None to score all suburbs (used by /api/civic).

    Returns:
        Dict mapping suburb name to a score breakdown:
        {suburb: {liveability, safety, transport, lifestyle, affordability, nightlife}}
    """
    w_safety = float(weights.get("safety", 0.25))
    w_transport = float(weights.get("transport", 0.25))
    w_lifestyle = float(weights.get("lifestyle", 0.25))
    w_affordability = float(weights.get("affordability", 0.25))
    w_nightlife = float(weights.get("nightlife", 0.0))

    with SessionLocal() as session:
        suburbs_q = select(Suburb)
        if suburb_filter:
            suburbs_q = suburbs_q.where(Suburb.suburb.in_(suburb_filter))
        suburbs = session.scalars(suburbs_q).all()

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

    results: dict[str, dict[str, Any]] = {}
    for row in suburbs:
        sentiment = sentiment_by_suburb.get(row.suburb, {})
        osm_row = osm_by_suburb.get(row.suburb)
        transport_row = transport_by_suburb.get(row.suburb)

        safety_score = safety_by_suburb.get(row.suburb, 0.5)
        facilities_component = _clamp_unit(row.facilities_score)
        osm_component = _clamp_unit(osm_row.osm_score if osm_row else None)
        transport_component = _clamp_unit(transport_row.transport_score if transport_row else None)
        gis_combined = (
            (facilities_component * 0.20)
            + (osm_component * 0.20)
            + (transport_component * 0.60)
        )

        lifestyle_score = _clamp_unit(
            sentiment.get("community", sentiment.get("lifestyle", row.facilities_score))
        )
        nightlife_score = _clamp_unit(
            sentiment.get("nightlife", sentiment.get("community", row.facilities_score))
        )
        affordability_score = _clamp_unit(sentiment.get("affordability", 0.5))

        liveability_score = (
            (safety_score * w_safety)
            + (gis_combined * w_transport)
            + (lifestyle_score * w_lifestyle)
            + (affordability_score * w_affordability)
            + (nightlife_score * w_nightlife)
        )

        results[row.suburb] = {
            "liveability": round(liveability_score, 4),
            "safety": round(safety_score, 4),
            "transport": round(gis_combined, 4),
            "lifestyle": round(lifestyle_score, 4),
            "affordability": round(affordability_score, 4),
            "nightlife": round(nightlife_score, 4),
            "_row": row,
        }

    return results
