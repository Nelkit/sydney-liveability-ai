import json
import time
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import requests

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
REQUEST_TIMEOUT_SECONDS = 120
REQUEST_PAUSE_SECONDS = 2

MVP_SUBURBS = ["Newtown", "Glebe", "Redfern", "Surry Hills", "Haymarket"]

AMENITY_CATEGORIES = [
    "cafe",
    "restaurant",
    "gym",
    "school",
    "hospital",
    "pharmacy",
    "library",
]

LEISURE_CATEGORIES = ["park", "playground", "sports_centre"]

# Team-tunable weights for POI density scoring. Must remain aligned with /api/civic.
WEIGHT_CAFE = 0.14
WEIGHT_RESTAURANT = 0.16
WEIGHT_GYM = 0.12
WEIGHT_SCHOOL = 0.10
WEIGHT_HOSPITAL = 0.06
WEIGHT_PHARMACY = 0.04
WEIGHT_LIBRARY = 0.02
WEIGHT_PARK = 0.20
WEIGHT_PLAYGROUND = 0.08
WEIGHT_SPORTS_CENTRE = 0.08

CATEGORY_WEIGHTS = {
    "cafe": WEIGHT_CAFE,
    "restaurant": WEIGHT_RESTAURANT,
    "gym": WEIGHT_GYM,
    "school": WEIGHT_SCHOOL,
    "hospital": WEIGHT_HOSPITAL,
    "pharmacy": WEIGHT_PHARMACY,
    "library": WEIGHT_LIBRARY,
    "park": WEIGHT_PARK,
    "playground": WEIGHT_PLAYGROUND,
    "sports_centre": WEIGHT_SPORTS_CENTRE,
}


def slugify(name: str) -> str:
    return name.lower().replace(" ", "_")


def strip_nsw_suffix(sal_name: str) -> str:
    if "(" in sal_name:
        return sal_name.split("(", maxsplit=1)[0].strip()
    return sal_name.strip()


def iter_positions(node: object) -> Iterable[Tuple[float, float]]:
    if isinstance(node, list):
        if len(node) >= 2 and isinstance(node[0], (int, float)) and isinstance(node[1], (int, float)):
            yield float(node[0]), float(node[1])
            return
        for child in node:
            yield from iter_positions(child)


def compute_bbox_from_geometry(geometry: Dict) -> Tuple[float, float, float, float]:
    coords = geometry.get("coordinates", [])
    points = list(iter_positions(coords))
    if not points:
        raise ValueError("Geometry has no coordinates")

    longitudes = [lon for lon, _ in points]
    latitudes = [lat for _, lat in points]
    west = min(longitudes)
    east = max(longitudes)
    south = min(latitudes)
    north = max(latitudes)
    return south, west, north, east


def load_mvp_suburb_bboxes(geojson_path: Path) -> Dict[str, Tuple[float, float, float, float]]:
    with geojson_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    bboxes: Dict[str, Tuple[float, float, float, float]] = {}
    for feature in data.get("features", []):
        properties = feature.get("properties", {})
        suburb_name = strip_nsw_suffix(properties.get("SAL_NAME21", ""))
        if suburb_name in MVP_SUBURBS:
            bboxes[suburb_name] = compute_bbox_from_geometry(feature.get("geometry", {}))

    missing = sorted(set(MVP_SUBURBS) - set(bboxes.keys()))
    if missing:
        raise RuntimeError(f"Missing suburb geometries in GeoJSON: {', '.join(missing)}")

    return bboxes


def build_overpass_query_for_sets(
    bbox: Tuple[float, float, float, float],
    amenity_values: List[str],
    leisure_values: List[str],
) -> str:
    south, west, north, east = bbox
    lines = ["[out:json][timeout:120];", "("]
    if amenity_values:
        amenity_regex = "|".join(amenity_values)
        lines.append(
            f"  node[\"amenity\"~\"^({amenity_regex})$\"]({south},{west},{north},{east});"
        )
        lines.append(
            f"  way[\"amenity\"~\"^({amenity_regex})$\"]({south},{west},{north},{east});"
        )
    if leisure_values:
        leisure_regex = "|".join(leisure_values)
        lines.append(
            f"  node[\"leisure\"~\"^({leisure_regex})$\"]({south},{west},{north},{east});"
        )
        lines.append(
            f"  way[\"leisure\"~\"^({leisure_regex})$\"]({south},{west},{north},{east});"
        )
    lines.extend([");", "out tags;"])
    return "\n".join(lines)


def build_overpass_query(bbox: Tuple[float, float, float, float]) -> str:
    return build_overpass_query_for_sets(bbox, AMENITY_CATEGORIES, LEISURE_CATEGORIES)


def fetch_overpass_data(query: str) -> Dict:
    response = requests.post(
        OVERPASS_URL,
        data={"data": query},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    status_code = response.status_code
    if status_code == 200:
        return {"status_code": status_code, "data": response.json()}
    return {"status_code": status_code, "data": None, "text": response.text}


def fetch_with_retry(query: str, attempts: int = 4) -> Dict:
    last_payload = None
    for attempt in range(attempts):
        payload = fetch_overpass_data(query)
        last_payload = payload
        if payload["status_code"] == 200:
            return payload
        if attempt < attempts - 1:
            backoff_seconds = REQUEST_PAUSE_SECONDS * (2 ** attempt)
            time.sleep(backoff_seconds)
    return last_payload


def fetch_elements_for_suburb(
    bbox: Tuple[float, float, float, float],
) -> Tuple[List[Dict], str, List[Dict], bool]:
    combined_query = build_overpass_query(bbox)
    combined_response = fetch_with_retry(combined_query)
    responses = [combined_response]

    if combined_response["status_code"] == 200:
        elements = combined_response["data"].get("elements", [])
        return elements, combined_query, responses, False

    if combined_response["status_code"] not in (429, 504):
        raise RuntimeError(f"Overpass error {combined_response['status_code']}")

    seen = set()
    elements: List[Dict] = []

    for category in AMENITY_CATEGORIES:
        query = build_overpass_query_for_sets(bbox, [category], [])
        payload = fetch_with_retry(query)
        responses.append(payload)
        if payload["status_code"] != 200:
            raise RuntimeError(
                f"Overpass fallback failed for amenity={category} with status {payload['status_code']}"
            )
        for element in payload["data"].get("elements", []):
            key = (element.get("type"), element.get("id"))
            if key not in seen:
                seen.add(key)
                elements.append(element)
        time.sleep(REQUEST_PAUSE_SECONDS)

    for category in LEISURE_CATEGORIES:
        query = build_overpass_query_for_sets(bbox, [], [category])
        payload = fetch_with_retry(query)
        responses.append(payload)
        if payload["status_code"] != 200:
            raise RuntimeError(
                f"Overpass fallback failed for leisure={category} with status {payload['status_code']}"
            )
        for element in payload["data"].get("elements", []):
            key = (element.get("type"), element.get("id"))
            if key not in seen:
                seen.add(key)
                elements.append(element)
        time.sleep(REQUEST_PAUSE_SECONDS)

    return elements, combined_query, responses, True


def count_pois_by_category(elements: List[Dict]) -> Dict[str, int]:
    counts = {category: 0 for category in CATEGORY_WEIGHTS}

    for element in elements:
        tags = element.get("tags", {})
        amenity = tags.get("amenity")
        leisure = tags.get("leisure")

        if amenity in counts:
            counts[amenity] += 1
        if leisure in counts:
            counts[leisure] += 1

    return counts


def compute_weighted_raw_score(counts: Dict[str, int]) -> float:
    return sum(counts[category] * CATEGORY_WEIGHTS[category] for category in CATEGORY_WEIGHTS)


def min_max_normalize(values: Dict[str, float]) -> Dict[str, float]:
    min_v = min(values.values())
    max_v = max(values.values())

    if max_v == min_v:
        return {k: 0.5 for k in values}

    return {k: (v - min_v) / (max_v - min_v) for k, v in values.items()}


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    geojson_path = repo_root / "data" / "processed" / "suburbs.geojson"
    raw_osm_dir = repo_root / "data" / "raw" / "osm"
    processed_output_path = repo_root / "data" / "processed" / "osm_scores.json"

    raw_osm_dir.mkdir(parents=True, exist_ok=True)
    processed_output_path.parent.mkdir(parents=True, exist_ok=True)

    suburb_bboxes = load_mvp_suburb_bboxes(geojson_path)

    suburb_counts: Dict[str, Dict[str, int]] = {}
    suburb_weighted_scores: Dict[str, float] = {}

    for index, suburb in enumerate(MVP_SUBURBS):
        bbox = suburb_bboxes[suburb]
        elements, query, responses, fallback_used = fetch_elements_for_suburb(bbox)

        raw_path = raw_osm_dir / f"{slugify(suburb)}_pois.json"
        raw_payload = {
            "suburb": suburb,
            "bbox": {
                "south": bbox[0],
                "west": bbox[1],
                "north": bbox[2],
                "east": bbox[3],
            },
            "query": query,
            "fallback_used": fallback_used,
            "responses": responses,
        }
        raw_path.write_text(json.dumps(raw_payload, ensure_ascii=True, indent=2), encoding="utf-8")

        counts = count_pois_by_category(elements)
        suburb_counts[suburb] = counts
        suburb_weighted_scores[suburb] = compute_weighted_raw_score(counts)

        print(f"Fetched {suburb}: {len(elements)} elements")
        if index < len(MVP_SUBURBS) - 1:
            time.sleep(REQUEST_PAUSE_SECONDS)

    normalized_scores = min_max_normalize(suburb_weighted_scores)

    output = {}
    for suburb in MVP_SUBURBS:
        row = {"osm_score": round(normalized_scores[suburb], 4)}
        row.update(suburb_counts[suburb])
        output[suburb] = row

    processed_output_path.write_text(json.dumps(output, ensure_ascii=True, indent=2), encoding="utf-8")
    print(f"Saved processed score file: {processed_output_path}")


if __name__ == "__main__":
    main()

