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
        return {
            "answer": response.get("answer", "I could not process that question right now."),
            "sources": response.get("sources", []),
            "suburb_scores": response.get("suburb_scores", []),
            "map_state": response.get("map_state"),
        }
    except Exception:
        # We keep a stable fallback shape so the frontend can fail gracefully.
        return {
            "answer": "I could not process that question right now. Please try again.",
            "sources": [],
            "suburb_scores": [],
            "map_state": None,
        }
