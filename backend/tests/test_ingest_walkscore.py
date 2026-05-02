"""Tests for backend/scripts/ingest_walkscore.py."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_BACKEND))
sys.path.insert(0, str(_BACKEND / "scripts"))


def _import_module(monkeypatch):
    import ingest_walkscore

    monkeypatch.setattr(ingest_walkscore, "_resolve_api_key", lambda: "test-key")
    return ingest_walkscore


def test_build_request_params_includes_coordinates_and_key(monkeypatch) -> None:
    ingest_walkscore = _import_module(monkeypatch)
    params = ingest_walkscore._build_request_params("Newtown", -33.9, 151.2, "abc123")
    assert params["format"] == "json"
    assert params["address"] == "Newtown, Sydney NSW, Australia"
    assert params["lat"] == "-33.900000"
    assert params["lon"] == "151.200000"
    assert params["wsapikey"] == "abc123"


def test_extract_walkscore_score_handles_missing_and_numeric_values(monkeypatch) -> None:
    ingest_walkscore = _import_module(monkeypatch)
    assert ingest_walkscore._extract_walkscore_score({"walkscore": 82}) == 82.0
    assert ingest_walkscore._extract_walkscore_score({"walkscore": "74"}) == 74.0
    assert ingest_walkscore._extract_walkscore_score({"status": 40}) is None


def test_load_targets_skips_existing_scores(monkeypatch) -> None:
    ingest_walkscore = _import_module(monkeypatch)
    monkeypatch.setattr(ingest_walkscore, "text", lambda sql: sql)

    class _Result:
        def mappings(self):
            return self

        def all(self):
            return [
                {"sal_code": "1", "suburb": "Newtown", "walkability_score": None, "lat": -33.9, "lon": 151.2},
                {"sal_code": "2", "suburb": "Glebe", "walkability_score": 77.0, "lat": -33.8, "lon": 151.1},
            ]

    class _Session:
        def execute(self, *args, **kwargs):
            return _Result()

    targets = ingest_walkscore._load_targets(_Session(), refresh_all=False)
    assert len(targets) == 1
    assert targets[0]["suburb"] == "Newtown"