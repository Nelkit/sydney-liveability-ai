"""Chat API endpoint that routes user intent through Query Crew."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from crews.query_crew import run_query


router = APIRouter(prefix="/api", tags=["chat"])


class ChatRequest(BaseModel):
    """Incoming user chat payload."""

    question: str | None = None
    message: str | None = None
    weights: dict[str, Any] | None = None


class EvidenceTraceSummary(BaseModel):
    """Deterministic aggregate over the sentiment agent's evidence_trace."""

    length: int = 0
    by_tool: dict[str, int] = {}
    last_action: dict[str, Any] | None = None
    no_data_count: int = 0


class QualityPayload(BaseModel):
    """Optional quality-instrumentation block on the /api/chat response."""

    evidence_trace_summary: EvidenceTraceSummary | None = None


@router.post("/chat")
def chat(payload: ChatRequest) -> dict[str, Any]:
    """Run query crew and return the stable chat response contract."""
    question = (payload.question or payload.message or "").strip()
    weights = payload.weights or {}
    if not question:
        return {
            "answer": "Please provide a question.",
            "sources": [],
            "suburb_scores": [],
            "map_state": None,
        }

    try:
        response = run_query(question, weights)
        result: dict[str, Any] = {
            "answer": response.get("answer", "I could not process that question right now."),
            "sources": response.get("sources", []),
            "suburb_scores": response.get("suburb_scores", []),
            "map_state": response.get("map_state"),
        }
        for key in (
            "router",
            "quality",
            "claims",
            "aspect_scores",
            "emotion_profile",
            "reddit_highlights",
            "crime_breakdown",
        ):
            if response.get(key) is not None:
                result[key] = response[key]
        if response.get("quality") is not None:
            result["quality"] = response["quality"]
        return result
    except Exception:
        # We keep a stable fallback shape so the frontend can fail gracefully.
        return {
            "answer": "I could not process that question right now. Please try again.",
            "sources": [],
            "suburb_scores": [],
            "map_state": None,
        }
