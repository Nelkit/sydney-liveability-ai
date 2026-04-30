"""Cross-modal fallback handlers for dimensions where Reddit is silent.

Each handler is a pure function `(suburb_name) -> {score, source,
coverage_tier, confidence}`. Handlers raise `KeyError` when the suburb
is not in their data — the orchestrator catches and falls through to a
null score.

The dispatch table FALLBACK_POLICY is the auditable contract: it is
deliberately a static per-dimension routing rather than a learned policy
so the report can show the table verbatim. See design.md §3.
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Callable, Optional

from .confidence import MODALITY_CONFIDENCE

CoverageTier = str  # "none" | "weak" | "strong"
FallbackHandler = Callable[[str], dict]

# All paths are resolved relative to the repository root (cwd of the
# backend / the precompute script). Tests can monkeypatch these constants.
DATA_ROOT = Path("data")
BOCSAR_PATH = DATA_ROOT / "processed" / "bocsar_clean.csv"
OSM_SCORES_PATH = DATA_ROOT / "processed" / "osm_scores.json"
ARCGIS_SUBURBS_PATH = DATA_ROOT / "processed" / "arcgis_suburbs.csv"


# --------------------------------------------------------------------------
# Data loaders (cached)
# --------------------------------------------------------------------------

_bocsar_totals: Optional[dict[str, float]] = None
_bocsar_percentile_anchors: Optional[list[float]] = None
_osm_scores: Optional[dict[str, dict]] = None
_arcgis_rows: Optional[dict[str, dict]] = None


def _normalise(name: str) -> str:
    return name.strip().lower()


def _load_bocsar() -> tuple[dict[str, float], list[float]]:
    global _bocsar_totals, _bocsar_percentile_anchors
    if _bocsar_totals is None or _bocsar_percentile_anchors is None:
        totals: dict[str, float] = {}
        if BOCSAR_PATH.exists():
            with open(BOCSAR_PATH, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    suburb = _normalise(row.get("suburb", ""))
                    if not suburb:
                        continue
                    try:
                        annual = float(row.get("annual_avg", 0.0) or 0.0)
                    except ValueError:
                        annual = 0.0
                    totals[suburb] = totals.get(suburb, 0.0) + annual
        _bocsar_totals = totals
        # Sorted ascending — used to map a suburb's total crime to a
        # percentile, which we then invert (more crime → lower score).
        _bocsar_percentile_anchors = sorted(totals.values()) or [0.0]
    return _bocsar_totals, _bocsar_percentile_anchors


def _load_osm_scores() -> dict[str, dict]:
    global _osm_scores
    if _osm_scores is None:
        if OSM_SCORES_PATH.exists():
            with open(OSM_SCORES_PATH, encoding="utf-8") as f:
                raw = json.load(f)
        else:
            raw = {}
        _osm_scores = {_normalise(k): v for k, v in raw.items()}
    return _osm_scores


def _load_arcgis_suburbs() -> dict[str, dict]:
    """Per-suburb facility counts from data/processed/arcgis_suburbs.csv."""
    global _arcgis_rows
    if _arcgis_rows is None:
        rows: dict[str, dict] = {}
        if ARCGIS_SUBURBS_PATH.exists():
            with open(ARCGIS_SUBURBS_PATH, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    name = _normalise(row.get("suburb", ""))
                    if not name:
                        continue

                    def _to_int(field: str) -> int:
                        try:
                            return int(float(row.get(field, 0) or 0))
                        except ValueError:
                            return 0

                    rows[name] = {
                        "car_share_bays": _to_int("car_share_bays_count"),
                        "libraries": _to_int("libraries_count"),
                        "mobility_parking": _to_int("mobility_parking_count"),
                        "sports_facilities": _to_int("sports_facilities_count"),
                    }
        _arcgis_rows = rows
    return _arcgis_rows


# --------------------------------------------------------------------------
# Score helpers
# --------------------------------------------------------------------------

def _percentile_rank(value: float, sorted_values: list[float]) -> float:
    """Fraction of `sorted_values` strictly below `value`, in [0, 1]."""
    if not sorted_values:
        return 0.5
    n = len(sorted_values)
    # Count how many anchors are below `value`. Use simple bisect-by-hand to
    # avoid importing bisect just for this.
    lo, hi = 0, n
    while lo < hi:
        mid = (lo + hi) // 2
        if sorted_values[mid] < value:
            lo = mid + 1
        else:
            hi = mid
    return lo / n


def _log_scale(count: int, ceiling: int = 200) -> float:
    """Map a non-negative count to [0, 1] via log scaling, capped at ceiling."""
    if count <= 0:
        return 0.0
    return min(1.0, math.log1p(count) / math.log1p(ceiling))


# --------------------------------------------------------------------------
# Handlers
# --------------------------------------------------------------------------

def safety_from_bocsar(suburb: str) -> dict:
    totals, anchors = _load_bocsar()
    key = _normalise(suburb)
    if key not in totals:
        raise KeyError(suburb)
    crime_total = totals[key]
    pct = _percentile_rank(crime_total, anchors)
    # Invert: higher percentile → more crime → lower safety score.
    score = round(1.0 - pct, 3)
    return {
        "score": score,
        "source": "bocsar",
        "coverage_tier": "weak",
        "confidence": MODALITY_CONFIDENCE["bocsar"],
    }


def food_from_osm(suburb: str) -> dict:
    osm = _load_osm_scores()
    key = _normalise(suburb)
    if key not in osm:
        raise KeyError(suburb)
    entry = osm[key]
    cafe = int(entry.get("cafe", 0) or 0)
    restaurant = int(entry.get("restaurant", 0) or 0)
    score = round(_log_scale(cafe + restaurant, ceiling=200), 3)
    return {
        "score": score,
        "source": "osm",
        "coverage_tier": "strong",
        "confidence": MODALITY_CONFIDENCE["osm"],
    }


def green_from_osm_arcgis(suburb: str) -> dict:
    osm = _load_osm_scores()
    arc = _load_arcgis_suburbs()
    key = _normalise(suburb)
    osm_entry = osm.get(key)
    arc_entry = arc.get(key)
    if osm_entry is None and arc_entry is None:
        raise KeyError(suburb)
    park = int((osm_entry or {}).get("park", 0) or 0)
    playground = int((osm_entry or {}).get("playground", 0) or 0)
    sports = int((arc_entry or {}).get("sports_facilities", 0) or 0)
    score = round(_log_scale(park + playground + sports, ceiling=120), 3)
    return {
        "score": score,
        "source": "osm",
        "coverage_tier": "strong",
        "confidence": MODALITY_CONFIDENCE["osm"],
    }


def transport_from_arcgis(suburb: str) -> dict:
    arc = _load_arcgis_suburbs()
    key = _normalise(suburb)
    if key not in arc:
        raise KeyError(suburb)
    entry = arc[key]
    car_share = entry.get("car_share_bays", 0)
    mobility = entry.get("mobility_parking", 0)
    # The City of Sydney ArcGIS dataset only covers inner-city suburbs;
    # outer-Sydney rows exist in the merged CSV but with all-zero counts.
    # Treat that as "no usable proxy" rather than "score 0".
    if car_share + mobility <= 0:
        raise KeyError(suburb)
    score = round(_log_scale(car_share + mobility, ceiling=200), 3)
    return {
        "score": score,
        "source": "arcgis",
        "coverage_tier": "weak",
        "confidence": MODALITY_CONFIDENCE["arcgis"],
    }


def community_from_arcgis(suburb: str) -> dict:
    arc = _load_arcgis_suburbs()
    key = _normalise(suburb)
    if key not in arc:
        raise KeyError(suburb)
    entry = arc[key]
    libraries = entry.get("libraries", 0)
    sports = entry.get("sports_facilities", 0)
    if libraries + sports <= 0:
        raise KeyError(suburb)
    score = round(_log_scale(libraries * 5 + sports, ceiling=60), 3)
    return {
        "score": score,
        "source": "arcgis",
        "coverage_tier": "weak",
        "confidence": MODALITY_CONFIDENCE["arcgis"],
    }


# --------------------------------------------------------------------------
# Dispatch table
# --------------------------------------------------------------------------

# `None` means the dimension has no defensible cross-modal proxy and the
# orchestrator should emit `score: null, source: "none"`. Order matches
# ASPECT_TAXONOMY for readability.
FALLBACK_POLICY: dict[str, Optional[FallbackHandler]] = {
    "safety": safety_from_bocsar,
    "food_and_cafe": food_from_osm,
    "nightlife": None,
    "affordability": None,
    "transport": transport_from_arcgis,
    "community": community_from_arcgis,
    "noise": None,
    "green_space": green_from_osm_arcgis,
}
