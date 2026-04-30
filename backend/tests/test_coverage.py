"""Unit tests for backend/core/nlp/coverage.py.

These tests load the all-MiniLM-L6-v2 model (~80MB) on first run and are
slow on cold cache. They are skipped automatically if sentence-transformers
is unavailable.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

st = pytest.importorskip("sentence_transformers")

from core.nlp.coverage import compute_coverage  # noqa: E402


TRANSPORT_POSTS = [
    "The trains from here are surprisingly reliable in peak hour",
    "Commuting on the bus into the city takes about 45 minutes",
    "Public transport options are great, lots of train and bus services",
    "I take the metro every day, super convenient transport links",
    "Walking distance to the train station is the main reason I moved here",
    "Bus 380 runs frequently, transport here is honestly fine",
    "Commute to work via public transport is quick and easy",
    "The light rail makes getting around the area painless",
    "Train delays during rain are a regular occurrence",
    "Lots of buses, plus the train line, transport-wise it's solid",
    "You'll need a car here, public transport is sparse",
    "I bike to work, transport is mostly via cycle paths",
    "Trams and trains both stop nearby, very transport-friendly",
    "Catching the bus into the CBD is straightforward",
    "Train station is a 5 minute walk, brilliant for commuting",
] * 4  # 60 transport-themed posts to ensure top-10 mean is high


def test_strong_transport_signal():
    coverage = compute_coverage(TRANSPORT_POSTS)
    assert coverage["transport"]["tier"] == "strong"
    assert coverage["transport"]["mention_count"] >= 10


def test_empty_corpus_all_none():
    coverage = compute_coverage([])
    for name, entry in coverage.items():
        assert entry["tier"] == "none", f"{name} should be 'none' on empty corpus"
        assert entry["mention_count"] == 0
        assert entry["prototype_similarity"] == 0.0


def test_unrelated_corpus_low_signal():
    posts = [
        "I baked sourdough yesterday, it turned out great",
        "My cat keeps knocking things off the bench",
        "Watched a documentary about deep-sea exploration",
    ]
    coverage = compute_coverage(posts)
    # Transport prototype should not light up on unrelated posts
    assert coverage["transport"]["tier"] in ("none", "weak")
