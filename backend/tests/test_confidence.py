"""Unit tests for backend/core/nlp/confidence.py."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.nlp.confidence import (
    compute_confidence,
    confidence_tier,
    shrink_aspects,
)


def test_compute_confidence_below_threshold():
    assert compute_confidence(15) == 0.5


def test_compute_confidence_saturates_at_threshold():
    assert compute_confidence(30) == 1.0


def test_compute_confidence_above_threshold_stays_saturated():
    assert compute_confidence(400) == 1.0


def test_compute_confidence_empty():
    assert compute_confidence(0) == 0.0


def test_compute_confidence_negative_treated_as_zero():
    assert compute_confidence(-5) == 0.0


def test_tier_high_boundary():
    assert confidence_tier(0.70) == "high"


def test_tier_medium_boundary():
    assert confidence_tier(0.40) == "medium"


def test_tier_low_below_0_4():
    assert confidence_tier(0.39) == "low"


def test_tier_upper_range():
    assert confidence_tier(1.0) == "high"


def test_tier_just_below_high():
    assert confidence_tier(0.69) == "medium"


def test_shrink_low_confidence_pulls_toward_neutral():
    raw = {"safety": {"score": 0.95, "mentions": 3}}
    out = shrink_aspects(raw, confidence=0.2)
    # 0.2 * 0.95 + 0.8 * 0.5 = 0.19 + 0.4 = 0.59
    assert out["safety"]["score"] == 0.59
    assert out["safety"]["raw_score"] == 0.95
    assert out["safety"]["mentions"] == 3


def test_shrink_full_confidence_preserves_raw():
    raw = {"safety": {"score": 0.95, "mentions": 42}}
    out = shrink_aspects(raw, confidence=1.0)
    assert out["safety"]["score"] == 0.95
    assert out["safety"]["raw_score"] == 0.95


def test_shrink_zero_confidence_gives_neutral():
    raw = {
        "safety": {"score": 0.95, "mentions": 0},
        "food_and_cafe": {"score": 0.1, "mentions": 0},
    }
    out = shrink_aspects(raw, confidence=0.0)
    assert out["safety"]["score"] == 0.5
    assert out["food_and_cafe"]["score"] == 0.5


def test_shrink_is_idempotent_when_raw_score_present():
    raw = {"safety": {"score": 0.95, "mentions": 3}}
    first = shrink_aspects(raw, confidence=0.2)
    second = shrink_aspects(first, confidence=0.2)
    assert first["safety"]["score"] == second["safety"]["score"]
    assert first["safety"]["raw_score"] == second["safety"]["raw_score"]


def test_shrink_preserves_extra_entry_fields():
    raw = {"safety": {"score": 0.9, "mentions": 5, "notes": "anything"}}
    out = shrink_aspects(raw, confidence=0.5)
    assert out["safety"]["notes"] == "anything"
    assert out["safety"]["mentions"] == 5
