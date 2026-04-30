"""Unit tests for backend/core/nlp/fallback.py."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _chdir_repo_root(monkeypatch):
    monkeypatch.chdir(REPO_ROOT)
    # Reset module-level caches so each test sees a fresh load.
    from core.nlp import fallback  # noqa: WPS433

    fallback._bocsar_totals = None
    fallback._bocsar_percentile_anchors = None
    fallback._osm_scores = None
    fallback._arcgis_rows = None


def test_safety_from_bocsar_glebe():
    from core.nlp.fallback import safety_from_bocsar

    out = safety_from_bocsar("Glebe")
    assert 0.0 <= out["score"] <= 1.0
    assert out["source"] == "bocsar"
    assert out["coverage_tier"] == "weak"
    assert out["confidence"] == 0.7


def test_safety_from_bocsar_unknown_raises():
    from core.nlp.fallback import safety_from_bocsar

    with pytest.raises(KeyError):
        safety_from_bocsar("Atlantis")


def test_food_from_osm_newtown():
    from core.nlp.fallback import food_from_osm

    out = food_from_osm("Newtown")
    assert 0.0 <= out["score"] <= 1.0
    assert out["source"] == "osm"
    assert out["coverage_tier"] == "strong"
    assert out["confidence"] == 0.6


def test_food_from_osm_unknown_raises():
    from core.nlp.fallback import food_from_osm

    with pytest.raises(KeyError):
        food_from_osm("Atlantis")


def test_green_from_osm_arcgis_newtown():
    from core.nlp.fallback import green_from_osm_arcgis

    out = green_from_osm_arcgis("Newtown")
    assert 0.0 <= out["score"] <= 1.0
    assert out["source"] == "osm"
    assert out["coverage_tier"] == "strong"


def test_transport_from_arcgis_glebe():
    from core.nlp.fallback import transport_from_arcgis

    out = transport_from_arcgis("Glebe")
    assert 0.0 <= out["score"] <= 1.0
    assert out["source"] == "arcgis"
    assert out["coverage_tier"] == "weak"
    assert out["confidence"] == 0.5


def test_community_from_arcgis_glebe():
    from core.nlp.fallback import community_from_arcgis

    out = community_from_arcgis("Glebe")
    assert 0.0 <= out["score"] <= 1.0
    assert out["source"] == "arcgis"
    assert out["coverage_tier"] == "weak"


def test_fallback_policy_none_for_nightlife_noise_affordability():
    from core.nlp.fallback import FALLBACK_POLICY

    assert FALLBACK_POLICY["nightlife"] is None
    assert FALLBACK_POLICY["noise"] is None
    assert FALLBACK_POLICY["affordability"] is None


def test_fallback_policy_covers_all_dimensions():
    from core.nlp.aspects import ASPECT_TAXONOMY
    from core.nlp.fallback import FALLBACK_POLICY

    for name in ASPECT_TAXONOMY:
        assert name in FALLBACK_POLICY, f"missing dispatch for {name}"
