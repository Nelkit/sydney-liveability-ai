"""Confidence scoring (global + per-dimension) and aspect-score shrinkage."""

from __future__ import annotations

from typing import Literal

FULL_CONFIDENCE_THRESHOLD = 30
PER_DIMENSION_FULL_CONFIDENCE_THRESHOLD = 10
NEUTRAL_SCORE = 0.5

ConfidenceTier = Literal["high", "medium", "low"]

# Fixed confidence per cross-modal data source. Used when an aspect is
# scored from a fallback handler rather than Reddit. The values reflect
# how directly each modality measures lived experience: BOCSAR is closest
# (real reported events), OSM POI counts and ArcGIS proxies progressively
# further. See design.md §4 for rationale.
MODALITY_CONFIDENCE: dict[str, float] = {
    "reddit": 1.0,  # mention-based — actual value computed per-dim
    "bocsar": 0.7,
    "osm": 0.6,
    "arcgis": 0.5,
    "none": 0.0,
}


def compute_confidence(post_count: int) -> float:
    """Return a confidence in [0, 1] derived from post volume.

    Reaches 1.0 at FULL_CONFIDENCE_THRESHOLD posts.
    """
    if post_count <= 0:
        return 0.0
    return min(1.0, post_count / FULL_CONFIDENCE_THRESHOLD)


def compute_per_dimension_confidence(mentions: int) -> float:
    """Per-dimension confidence in [0, 1] derived from mention count.

    Reaches 1.0 at PER_DIMENSION_FULL_CONFIDENCE_THRESHOLD mentions for the
    dimension. Mirrors compute_confidence's idiom at a finer grain.
    """
    if mentions <= 0:
        return 0.0
    return min(1.0, mentions / PER_DIMENSION_FULL_CONFIDENCE_THRESHOLD)


def confidence_tier(confidence: float) -> ConfidenceTier:
    """Classify a confidence value into high/medium/low."""
    if confidence >= 0.7:
        return "high"
    if confidence >= 0.4:
        return "medium"
    return "low"


def shrink_aspects(raw_aspects: dict, confidence: float) -> dict:
    """Return a new aspect dict with scores shrunk toward 0.5.

    Formula: shrunk = confidence * raw + (1 - confidence) * 0.5.
    The original raw score is preserved under `raw_score` on each entry.
    If an entry already carries `raw_score`, that value is used as the
    input instead of `score`, making the operation idempotent.
    """
    shrunk: dict = {}
    for name, entry in raw_aspects.items():
        raw = entry.get("raw_score", entry.get("score", NEUTRAL_SCORE))
        new_score = confidence * raw + (1.0 - confidence) * NEUTRAL_SCORE
        shrunk[name] = {
            **entry,
            "score": round(new_score, 3),
            "raw_score": round(raw, 3),
        }
    return shrunk
