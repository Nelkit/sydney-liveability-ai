"""Civic API endpoint that serves suburb scores from PostgreSQL."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from geoalchemy2.elements import WKBElement
from geoalchemy2.shape import to_shape

from core.scoring import compute_liveability_scores


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

    weights = {
        "safety": safety,
        "transport": transport,
        "lifestyle": lifestyle,
        "affordability": affordability,
        "nightlife": nightlife,
    }
    scores = compute_liveability_scores(weights)

    ranked = sorted(scores.values(), key=lambda s: s["liveability"], reverse=True)[:5]

    features = [
        {
            "type": "Feature",
            "properties": {
                "suburb": s["_row"].suburb,
                "liveability_score": s["liveability"],
                "safety_score": s["safety"],
                "transport_score": s["transport"],
                "lifestyle_score": s["lifestyle"],
                "nightlife_score": s["nightlife"],
            },
            "geometry": _to_geojson_geometry(s["_row"].geometry),
        }
        for s in ranked
    ]
    return {"type": "FeatureCollection", "features": features}
