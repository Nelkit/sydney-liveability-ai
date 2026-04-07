import json
from pathlib import Path
from typing import Dict, Any

MVP_SUBURBS = {"Newtown", "Glebe", "Redfern", "Surry Hills", "Haymarket"}

SA4_MAPPING = {
    "Newtown": "Inner West",
    "Glebe": "Inner West",
    "Redfern": "City and Inner South",
    "Surry Hills": "City and Inner South",
    "Haymarket": "City and Inner South",
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_osm_scores() -> Dict[str, Dict[str, Any]]:
    path = _repo_root() / "data" / "processed" / "osm_scores.json"
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return {name: payload for name, payload in data.items() if name in MVP_SUBURBS}


def load_suburbs_geojson() -> Dict[str, Any]:
    path = _repo_root() / "data" / "processed" / "suburbs.geojson"
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def strip_nsw_suffix(sal_name: str) -> str:
    if "(" in sal_name:
        return sal_name.split("(", maxsplit=1)[0].strip()
    return sal_name.strip()
