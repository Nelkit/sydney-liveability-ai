from typing import Any, Dict, List

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from core.osm_data import MVP_SUBURBS, SA4_MAPPING, strip_nsw_suffix


router = APIRouter(tags=["civic"])


@router.get("/api/civic")
def civic_scores(request: Request) -> Dict[str, Any]:
    try:
        osm_scores: Dict[str, Dict[str, Any]] = getattr(request.app.state, "osm_scores", {})
        suburbs_geojson: Dict[str, Any] = getattr(request.app.state, "suburbs_geojson", {})

        features: List[Dict[str, Any]] = []
        for feature in suburbs_geojson.get("features", []):
            properties = feature.get("properties", {})
            suburb_name = strip_nsw_suffix(properties.get("SAL_NAME21", ""))
            if suburb_name not in MVP_SUBURBS:
                continue

            osm_score = float(osm_scores.get(suburb_name, {}).get("osm_score", 0.0))
            lifestyle_score = osm_score
            transport_score = 0.0
            safety_score = 0.0
            liveability_score = lifestyle_score

            feature_properties = {
                "suburb": suburb_name,
                "sa4_area": SA4_MAPPING.get(suburb_name, ""),
                "liveability_score": liveability_score,
                "safety_score": safety_score,
                "transport_score": transport_score,
                "lifestyle_score": lifestyle_score,
            }

            features.append(
                {
                    "type": "Feature",
                    "properties": feature_properties,
                    "geometry": feature.get("geometry", {}),
                }
            )

        return {"type": "FeatureCollection", "features": features}
    except Exception as exc:
        return JSONResponse(
            status_code=400,
            content={"error": f"Unable to build civic response: {exc}"},
        )
