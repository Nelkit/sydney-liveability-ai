"""Civic API — serves suburb scores from PostgreSQL as a weighted GeoJSON ranking."""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy.exc import OperationalError
from geoalchemy2.elements import WKBElement
from geoalchemy2.shape import to_shape

from core.scoring import compute_liveability_scores


router = APIRouter(prefix="/api", tags=["civic"])
logger = logging.getLogger(__name__)


def _to_geojson_geometry(value: Any) -> dict[str, Any]:
    """Convert a PostGIS geometry value into a GeoJSON geometry dict."""
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


@router.get(
    "/civic",
    summary="Weighted suburb ranking (GeoJSON)",
    response_description=(
        "GeoJSON FeatureCollection with the top-5 suburbs ranked by the supplied "
        "weight vector. Each Feature has a `properties` object with pre-computed "
        "sub-scores and a `geometry` (MultiPolygon in WGS84) for map rendering."
    ),
    responses={
        400: {"description": "Weights do not sum to 1.0."},
        503: {"description": "PostgreSQL connection failed after 3 retries."},
    },
)
def get_civic(
    safety: float = Query(
        0.25,
        ge=0.0,
        le=1.0,
        description="Weight applied to the BOCSAR crime-safety score (0–1).",
    ),
    transport: float = Query(
        0.25,
        ge=0.0,
        le=1.0,
        description="Weight applied to the TfNSW / OSM transport score (0–1).",
    ),
    lifestyle: float = Query(
        0.25,
        ge=0.0,
        le=1.0,
        description="Weight applied to the OSM lifestyle amenities score (0–1).",
    ),
    affordability: float = Query(
        0.25,
        ge=0.0,
        le=1.0,
        description="Weight applied to the median-rent affordability score (0–1).",
    ),
    nightlife: float = Query(
        0.0,
        ge=0.0,
        le=1.0,
        description="Weight applied to the nightlife amenities score (0–1). Default 0.",
    ),
    proximity: float = Query(
        0.0,
        ge=0.0,
        le=1.0,
        description="Weight applied to the CBD proximity score (0–1). Default 0.",
    ),
) -> dict[str, Any]:
    """Return the top-5 Sydney suburbs ranked by a user-defined weight vector.

    All six weight parameters must sum to **1.0** (validated server-side;
    a 400 is returned if they don't). The frontend uses this endpoint to
    colour the choropleth map and populate the ranked sidebar.

    **Score formula**

    ```
    liveability = safety×w_s + transport×w_t + lifestyle×w_l
                + affordability×w_a + nightlife×w_n + proximity×w_p
    ```

    Scores are pre-normalised to 0–100 in the ingestion pipeline.

    **Response shape**

    ```json
    {
      "type": "FeatureCollection",
      "features": [
        {
          "type": "Feature",
          "properties": {
            "suburb": "Newtown",
            "liveability_score": 72.4,
            "safety_score": 68.1,
            "transport_score": 81.3,
            "lifestyle_score": 74.0,
            "nightlife_score": 65.2,
            "proximity_score": 55.0
          },
          "geometry": { "type": "MultiPolygon", "coordinates": [...] }
        }
      ]
    }
    ```
    """
    weight_sum = safety + transport + lifestyle + affordability + nightlife + proximity
    if abs(weight_sum - 1.0) > 0.001:
        raise HTTPException(
            status_code=400,
            detail=(
                "Weights must sum to 1.0 across safety, transport, lifestyle, "
                "affordability, nightlife, and proximity."
            ),
        )

    weights = {
        "safety": safety,
        "transport": transport,
        "lifestyle": lifestyle,
        "affordability": affordability,
        "nightlife": nightlife,
        "proximity": proximity,
    }
    max_attempts = 3
    backoff_seconds = 0.15
    last_exc: OperationalError | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            scores = compute_liveability_scores(weights)
            last_exc = None
            break
        except OperationalError as exc:
            logger.exception("Civic DB OperationalError")
            last_exc = exc
            if attempt == max_attempts:
                break
            time.sleep(backoff_seconds)
            backoff_seconds *= 2

    if last_exc is not None:
        raise HTTPException(
            status_code=503,
            detail="Database connection dropped. Please retry the request.",
        ) from last_exc

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
                "proximity_score": s["proximity"],
            },
            "geometry": _to_geojson_geometry(s["_row"].geometry),
        }
        for s in ranked
    ]
    return {"type": "FeatureCollection", "features": features}
