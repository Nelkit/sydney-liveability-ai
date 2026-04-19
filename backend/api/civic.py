"""Civic API endpoint that serves suburb scores from PostgreSQL."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from geoalchemy2.elements import WKBElement
from geoalchemy2.shape import to_shape
from sqlalchemy import func, select

from db.models import Bocsar, OsmScore, SentimentScore, Suburb, TransportScore
from db.postgres import SessionLocal


router = APIRouter(prefix="/api", tags=["civic"])


def _to_geojson_geometry(value: Any) -> dict[str, Any]:
    """Convert a PostGIS geometry value into GeoJSON geometry dict."""
    if value is None:
        return {}

    try:
        if isinstance(value, WKBElement):
            return to_shape(value).__geo_interface__

        if isinstance(value, (bytes, bytearray, memoryview)):
            return to_shape(WKBElement(bytes(value), srid=4326)).__geo_interface__

        if isinstance(value, str):
            stripped = value.strip()
            if stripped.startswith("{"):
                return json.loads(stripped)
            return to_shape(WKBElement(stripped, srid=4326)).__geo_interface__

        if hasattr(value, "__geo_interface__"):
            return value.__geo_interface__
    except Exception:
        return {}

    return {}


def _clamp_unit(value: float | None) -> float:
    """Clamp value to [0, 1], accepting either 0-1 or 0-100 input ranges."""
    if value is None:
        return 0.0
    numeric = float(value)
    if numeric > 1.0:
        numeric = numeric / 100.0
    if numeric < 0.0:
        return 0.0
    if numeric > 1.0:
        return 1.0
    return numeric


def _inverse_normalise(values: dict[str, float]) -> dict[str, float]:
    """Normalize a metric where lower raw value means better score (0-1)."""
    if not values:
        return {}

    min_value = min(values.values())
    max_value = max(values.values())
    if max_value == min_value:
        return {key: 0.5 for key in values}

    return {
        key: 1.0 - ((raw - min_value) / (max_value - min_value))
        for key, raw in values.items()
    }


@router.get("/civic")
def get_civic(
    safety: float = Query(0.25, ge=0.0, le=1.0),
    transport: float = Query(0.25, ge=0.0, le=1.0),
    lifestyle: float = Query(0.25, ge=0.0, le=1.0),
    affordability: float = Query(0.25, ge=0.0, le=1.0),
    nightlife: float = Query(0.0, ge=0.0, le=1.0),
) -> dict[str, Any]:
    """Return top-5 suburbs ranked by weighted liveability from structured sources."""
    weight_sum = safety + transport + lifestyle + affordability + nightlife
    if abs(weight_sum - 1.0) > 0.001:
        raise HTTPException(
            status_code=400,
            detail="Weights must sum to 1.0 across safety, transport, lifestyle, affordability, and nightlife.",
        )

    with SessionLocal() as session:
        suburbs = session.scalars(select(Suburb)).all()
        sentiment_rows = session.scalars(select(SentimentScore)).all()
        osm_rows = session.scalars(select(OsmScore)).all()
        transport_rows = session.scalars(select(TransportScore)).all()

        latest_crime_year = session.scalar(select(func.max(Bocsar.year)))
        crime_counts: dict[str, float] = {}
        if latest_crime_year is not None:
            crime_rows = session.execute(
                select(Bocsar.suburb, func.sum(Bocsar.incident_count))
                .where(Bocsar.year == latest_crime_year)
                .group_by(Bocsar.suburb)
            ).all()
            crime_counts = {
                str(suburb_name): float(total_incidents or 0.0)
                for suburb_name, total_incidents in crime_rows
            }

    sentiment_by_suburb: dict[str, dict[str, float]] = {}
    for row in sentiment_rows:
        suburb_scores = sentiment_by_suburb.setdefault(row.suburb, {})
        if row.score is not None:
            suburb_scores[row.aspect] = float(row.score)

    osm_by_suburb = {row.suburb: row for row in osm_rows}
    transport_by_suburb = {row.suburb: row for row in transport_rows}
    safety_by_suburb = _inverse_normalise(crime_counts)

    scored_rows: list[dict[str, Any]] = []
    for row in suburbs:
        sentiment = sentiment_by_suburb.get(row.suburb, {})
        osm_row = osm_by_suburb.get(row.suburb)
        transport_row = transport_by_suburb.get(row.suburb)

        safety_score = safety_by_suburb.get(row.suburb, 0.5)
        facilities_component = _clamp_unit(row.facilities_score)
        osm_component = _clamp_unit(osm_row.osm_score if osm_row else None)
        transport_component = _clamp_unit(transport_row.transport_score if transport_row else None)
        gis_combined = (facilities_component * 0.35) + (osm_component * 0.35) + (transport_component * 0.30)

        lifestyle_score = _clamp_unit(
            sentiment.get("community", sentiment.get("lifestyle", row.facilities_score))
        )
        nightlife_score = _clamp_unit(
            sentiment.get("nightlife", sentiment.get("community", row.facilities_score))
        )
        affordability_score = _clamp_unit(sentiment.get("affordability", 0.5))

        liveability_score = (
            (safety_score * safety)
            + (gis_combined * transport)
            + (lifestyle_score * lifestyle)
            + (affordability_score * affordability)
            + (nightlife_score * nightlife)
        )

        scored_rows.append(
            {
                "row": row,
                "safety_score": safety_score,
                "transport_score": gis_combined,
                "lifestyle_score": lifestyle_score,
                "nightlife_score": nightlife_score,
                "liveability_score": liveability_score,
            }
        )

    ranked_rows = sorted(scored_rows, key=lambda item: item["liveability_score"], reverse=True)[:5]

    features = [
        {
            "type": "Feature",
            "properties": {
                "suburb": item["row"].suburb,
                "sa4_area": item["row"].sa4_area,
                "liveability_score": item["liveability_score"],
                "safety_score": item["safety_score"],
                "transport_score": item["transport_score"],
                "lifestyle_score": item["lifestyle_score"],
                "nightlife_score": item["nightlife_score"],
            },
            "geometry": _to_geojson_geometry(item["row"].geometry),
        }
        for item in ranked_rows
    ]
    return {"type": "FeatureCollection", "features": features}
