from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SUBURBS_GEOJSON = PROJECT_ROOT / "data" / "raw" / "arcgis" / "suburbs.geojson"
DEFAULT_SUBURBS_CSV = DEFAULT_SUBURBS_GEOJSON.with_suffix(".csv")


def load_suburbs_geojson(path: str | Path = DEFAULT_SUBURBS_GEOJSON) -> pd.DataFrame:
    """Load the suburbs GeoJSON and keep only the feature properties."""

    geojson_path = Path(path)
    with geojson_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    features = payload.get("features", [])
    rows = [feature.get("properties", {}) for feature in features]
    return pd.DataFrame(rows)


def suburbs_geojson_to_csv(
    geojson_path: str | Path = DEFAULT_SUBURBS_GEOJSON,
    csv_path: str | Path = DEFAULT_SUBURBS_CSV,
) -> Path:
    """Convert the suburbs GeoJSON to CSV without the geometry field."""

    frame = load_suburbs_geojson(geojson_path)
    output_path = Path(csv_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output_path, index=False)
    return output_path


if __name__ == "__main__":
    suburbs_geojson_to_csv()
