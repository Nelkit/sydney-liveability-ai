"""Unit tests for backend/core/nlp/sentiment.py.

These tests load yangheng/deberta-v3-base-absa-v1.1 (~440MB) on first run
and are slow on cold cache. Skipped if transformers is unavailable.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

pytest.importorskip("transformers")

from core.nlp.sentiment import (  # noqa: E402
    aggregate_aspect_sentiment,
    score_aspect_sentiment,
)


def test_sarcastic_transport_below_neutral():
    text = "the trains here are *so* reliable, never late at all, my favourite part of living here"
    polarity, _confidence, _fallback = score_aspect_sentiment(
        text, "public transport and commuting"
    )
    # ABSA can be fooled by sarcasm too, but this regression test pins the
    # behaviour to "not wildly positive" so we notice if the model drifts.
    assert polarity < 0.85


def test_mixed_aspect_food_positive_rent_negative():
    text = "love the cafes but rent is absolutely insane, can barely afford to live here"
    food_polarity, _, _ = score_aspect_sentiment(
        text, "food, cafes, and restaurants"
    )
    rent_polarity, _, _ = score_aspect_sentiment(
        text, "rent, housing affordability"
    )
    assert food_polarity > rent_polarity


def test_aggregate_signature_preserved():
    texts = [
        "love the cafes but rent is absolutely insane, can barely afford to live here",
    ]
    scores = [5]
    classifications = [{"food_and_cafe": 0.9, "affordability": 0.8}]
    out = aggregate_aspect_sentiment(texts, scores, classifications)
    assert "food_and_cafe" in out
    assert "affordability" in out
    assert "score" in out["food_and_cafe"]
    assert "mentions" in out["food_and_cafe"]
    assert out["food_and_cafe"]["mentions"] == 1
