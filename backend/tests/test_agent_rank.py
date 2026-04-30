"""Unit tests for backend/core/agent/nodes.py:_rank_score."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.agent.nodes import _rank_score, _surviving_dimensions  # noqa: E402


def test_rank_with_two_null_dims_skips_them():
    aspects = {
        "safety": {"score": 0.8},
        "food_and_cafe": {"score": 0.6},
        "transport": {"score": 0.4},
        "nightlife": {"score": None},
        "noise": {"score": None},
    }
    weights = {
        "safety": 0.2,
        "food_and_cafe": 0.2,
        "transport": 0.2,
        "nightlife": 0.2,
        "noise": 0.2,
    }
    rank = _rank_score(aspects, weights)
    # weights renormalise to 1/3 each over surviving dims
    expected = (0.8 + 0.6 + 0.4) / 3
    assert abs(rank - expected) < 1e-6


def test_weight_heavy_null_dim_does_not_zero_the_rank():
    aspects = {
        "safety": {"score": 0.9},
        "transport": {"score": 0.7},
        "nightlife": {"score": None},
    }
    # nightlife has 80% of the user's weight, but it's null — the rank should
    # still reflect the surviving dims rather than collapsing to ~0.
    weights = {"safety": 0.1, "transport": 0.1, "nightlife": 0.8}
    rank = _rank_score(aspects, weights)
    assert rank > 0.5


def test_all_null_returns_zero():
    aspects = {
        "safety": {"score": None},
        "transport": {"score": None},
    }
    weights = {"safety": 0.5, "transport": 0.5}
    assert _rank_score(aspects, weights) == 0.0


def test_no_null_matches_naive_dot_product():
    aspects = {
        "safety": {"score": 0.8},
        "food_and_cafe": {"score": 0.6},
    }
    weights = {"safety": 0.5, "food_and_cafe": 0.5}
    rank = _rank_score(aspects, weights)
    assert abs(rank - 0.7) < 1e-6


def test_surviving_dimensions():
    aspects = {
        "safety": {"score": 0.8},
        "nightlife": {"score": None},
        "transport": {"score": 0.4},
    }
    surviving = _surviving_dimensions(
        aspects, ["safety", "nightlife", "transport", "missing"]
    )
    assert surviving == ["safety", "transport"]
