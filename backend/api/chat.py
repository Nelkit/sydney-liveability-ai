"""Chat API endpoint that routes user intent through Query Crew."""

from __future__ import annotations

import json
import traceback
from collections.abc import Generator
from typing import Any

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from crews.query_crew import run_query, run_query_stream


router = APIRouter(prefix="/api", tags=["chat"])


class ChatRequest(BaseModel):
    """Incoming user chat payload."""

    question: str | None = None
    message: str | None = None
    weights: dict[str, Any] | None = None
    include_debug: bool = False


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
        if payload.include_debug and response.get("error") is not None:
            result["error"] = response["error"]
        return result
    except Exception as exc:
        # We keep a stable fallback shape so the frontend can fail gracefully.
        result = {
            "answer": "I could not process that question right now. Please try again.",
            "sources": [],
            "suburb_scores": [],
            "map_state": None,
        }
        if payload.include_debug:
            result["error"] = {
                "type": type(exc).__name__,
                "message": str(exc),
                "traceback": traceback.format_exc(),
            }
        return result


def _sse(event: str, data: Any) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.post("/chat/stream")
def chat_stream(payload: ChatRequest) -> StreamingResponse:
    """SSE stream: emits step events then a final done event with the full payload."""
    question = (payload.question or payload.message or "").strip()
    weights = payload.weights or {}

    def generate() -> Generator[str, None, None]:
        if not question:
            yield _sse("done", {
                "answer": "Please provide a question.",
                "sources": [],
                "suburb_scores": [],
                "map_state": None,
            })
            return

        try:
            for event_type, data in run_query_stream(question, weights):
                yield _sse(event_type, data)
        except Exception:
            yield _sse("error", {"message": "I could not process that question right now. Please try again."})

    return StreamingResponse(generate(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    })
