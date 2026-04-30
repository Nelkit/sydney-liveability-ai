"""Tests for backend/agents/query/synthesiser.py — prompt-builder gating.

Verifies the spatial-intent skip on the Evidence trace block: out_of_scope
router outputs must not produce a trace section, and spatial routes with
sentiment evidence must.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _import_prompt_builder():
    pytest.importorskip("crewai")
    from agents.query.synthesiser import _build_synthesis_prompt

    return _build_synthesis_prompt


def _spatial_router() -> dict:
    return {
        "categories": ["sentiment"],
        "suburbs_mentioned": ["Newtown"],
    }


def _out_of_scope_router() -> dict:
    return {
        "categories": ["out_of_scope"],
        "suburbs_mentioned": [],
    }


def _sentiment_output_with_trace() -> dict:
    return {
        "Newtown": {
            "suburb": "Newtown",
            "status": "ok",
            "evidence_trace": [
                {
                    "step": 1,
                    "tool": "get_suburb_aspect",
                    "arguments": {"suburb": "Newtown", "dimension": "transport"},
                    "reasoning": "structured-aspect lookup",
                    "result_count": 1,
                    "result_preview": "score=0.62",
                    "elapsed_ms": 1.2,
                },
                {
                    "step": 2,
                    "tool": "search_posts",
                    "arguments": {"suburb": "Newtown", "dimension": "transport", "query": "bus", "k": 3},
                    "reasoning": "pull grounded quotes",
                    "result_count": 3,
                    "result_preview": "Newtown bus is decent...",
                    "elapsed_ms": 12.3,
                },
            ],
        }
    }


def test_out_of_scope_omits_evidence_trace_block() -> None:
    build = _import_prompt_builder()
    agent_outputs = {
        "router": _out_of_scope_router(),
        "sentiment": _sentiment_output_with_trace(),  # populated, but should be ignored
    }
    prompt = build("What's the best opera house?", {"suburbs": []}, agent_outputs=agent_outputs)
    assert "Evidence trace:" not in prompt


def test_spatial_router_with_sentiment_includes_trace_block() -> None:
    build = _import_prompt_builder()
    agent_outputs = {
        "router": _spatial_router(),
        "sentiment": _sentiment_output_with_trace(),
    }
    prompt = build("How is transport in Newtown?", {"suburbs": []}, agent_outputs=agent_outputs)
    assert "Evidence trace" in prompt
    assert "- step 1" in prompt
    assert "- step 2" in prompt


def test_spatial_router_without_sentiment_omits_trace_block() -> None:
    """No sentiment output → no spurious empty Evidence trace heading."""
    build = _import_prompt_builder()
    agent_outputs = {"router": _spatial_router()}
    prompt = build("How is transport in Newtown?", {"suburbs": []}, agent_outputs=agent_outputs)
    assert "Evidence trace:" not in prompt
