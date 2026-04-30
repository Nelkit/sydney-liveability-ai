"""Tests for backend/crews/query_crew.py — evidence_trace summary aggregation."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _import_summariser():
    pytest.importorskip("crewai")
    from crews.query_crew import _summarise_evidence_trace

    return _summarise_evidence_trace


def _trace_entry(step: int, tool: str, suburb: str, dimension: str | None, preview: str) -> dict:
    return {
        "step": step,
        "tool": tool,
        "arguments": {"suburb": suburb, "dimension": dimension} if dimension else {"suburb": suburb},
        "reasoning": "stub",
        "result_count": 1 if "no_data" not in preview else 0,
        "result_preview": preview,
        "elapsed_ms": 0.5,
    }


def test_multi_suburb_length_and_by_tool() -> None:
    summarise = _import_summariser()
    specialist_outputs = {
        "sentiment": {
            "Newtown": {
                "evidence_trace": [
                    _trace_entry(1, "get_suburb_aspect", "Newtown", "transport", "score=0.6"),
                    _trace_entry(2, "get_suburb_aspect", "Newtown", "safety", "score=0.5"),
                    _trace_entry(3, "search_posts", "Newtown", "transport", "Newtown bus great"),
                ],
            },
            "Glebe": {
                "evidence_trace": [
                    _trace_entry(1, "get_suburb_aspect", "Glebe", "transport", "score=0.55"),
                    _trace_entry(2, "get_suburb_aspect", "Glebe", "safety", "score=0.4"),
                ],
            },
        }
    }
    summary = summarise(specialist_outputs)
    # length == sum of per-suburb traces (3 + 2)
    assert summary["length"] == 5
    assert summary["by_tool"]["get_suburb_aspect"] == 4
    assert summary["by_tool"]["search_posts"] == 1
    assert summary["last_action"] is not None
    assert summary["last_action"]["tool"] in {"get_suburb_aspect", "search_posts"}


def test_out_of_scope_summary_is_zero_length() -> None:
    """Out_of_scope produces no specialist outputs → length == 0."""
    summarise = _import_summariser()
    summary = summarise({})
    assert summary["length"] == 0
    assert summary["by_tool"] == {}
    assert summary["last_action"] is None
    assert summary["no_data_count"] == 0


def test_no_data_count_increments_on_no_data_preview() -> None:
    """Trace entries whose preview includes 'no_data' bump the counter."""
    summarise = _import_summariser()
    specialist_outputs = {
        "sentiment": {
            "Abbotsbury": {
                "evidence_trace": [
                    _trace_entry(1, "get_suburb_aspect", "Abbotsbury", "noise",
                                 "no_data: no Reddit coverage and no cross-modal proxy"),
                    _trace_entry(2, "get_suburb_aspect", "Abbotsbury", "transport", "score=0.55"),
                ],
            }
        }
    }
    summary = summarise(specialist_outputs)
    assert summary["no_data_count"] >= 1
