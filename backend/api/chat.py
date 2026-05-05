"""Chat API — routes user intent through the Query Crew multi-agent pipeline."""

from __future__ import annotations

import json
import traceback
from collections.abc import Generator
from typing import Any

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from crews.query_crew import run_query, run_query_stream


router = APIRouter(prefix="/api", tags=["chat"])


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    """Payload for a single chat turn."""

    question: str | None = Field(
        default=None,
        description="Natural-language question about a Sydney suburb. "
                    "Use `question` or `message` — both are accepted.",
        examples=["What is the vibe like in Newtown?"],
    )
    message: str | None = Field(
        default=None,
        description="Alias for `question` (accepted for frontend compatibility).",
        examples=["Compare Glebe and Surry Hills"],
    )
    weights: dict[str, Any] | None = Field(
        default=None,
        description=(
            "User preference weights applied to the liveability score. "
            "Keys: `transport`, `safety`, `lifestyle`, `affordability`, `nightlife`, `proximity`. "
            "Values must sum to 1.0. Defaults to equal weighting (0.25 each, nightlife/proximity=0)."
        ),
        examples=[{"transport": 0.4, "safety": 0.3, "lifestyle": 0.2, "affordability": 0.1, "nightlife": 0.0, "proximity": 0.0}],
    )
    include_debug: bool = False


class EvidenceTraceSummary(BaseModel):
    """Aggregate over the sentiment agent's retrieval trace."""

    length: int = Field(0, description="Total number of tool calls the sentiment agent made.")
    by_tool: dict[str, int] = Field({}, description="Call count per tool name.")
    last_action: dict[str, Any] | None = Field(None, description="Details of the last tool call.")
    no_data_count: int = Field(0, description="Number of calls that returned `status=no_data`.")


class QualityPayload(BaseModel):
    """Optional quality/instrumentation block appended to every chat response."""

    evidence_trace_summary: EvidenceTraceSummary | None = Field(
        None,
        description="Only present when the sentiment agent was invoked.",
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/chat",
    summary="Chat (blocking)",
    response_description=(
        "Full structured answer. `answer` is a markdown string. "
        "`suburb_scores` ranks matched suburbs by weighted liveability score. "
        "`sources` is a list of grounded citations. "
        "Optional keys (`router`, `quality`, `claims`, `aspect_scores`, "
        "`emotion_profile`, `reddit_highlights`, `crime_breakdown`) are present "
        "only when the relevant specialist agent was invoked."
    ),
)
def chat(payload: ChatRequest) -> dict[str, Any]:
    """Answer a natural-language question about Sydney suburbs.

    Runs the full multi-agent pipeline synchronously and returns when all
    specialist agents have finished. For live progress updates prefer
    `/api/chat/stream`.

    **Routing logic** (handled by the Router agent):

    | Intent | Specialist invoked |
    |--------|--------------------|
    | Safety / crime | Crime agent → BOCSAR data |
    | Community / vibe / sentiment | Sentiment agent → Reddit RAG |
    | Parks / transport / facilities | GIS agent → ArcGIS + OSM |
    | Suburb comparison | Comparator agent |
    | Rankings ("most parks") | GIS agent (ranking mode) |

    **Weight vector**: if omitted, equal weights are used
    (`transport=safety=lifestyle=affordability=0.25`).
    """
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


@router.post(
    "/chat/stream",
    summary="Chat (streaming SSE)",
    response_description=(
        "Server-Sent Events stream. Each frame: `event: <type>\\ndata: <json>\\n\\n`. "
        "Event types: `step` (progress label), `heartbeat` (keep-alive, no payload), "
        "`done` (full response payload — same schema as `/api/chat`), `error` (message string)."
    ),
    responses={
        200: {
            "content": {"text/event-stream": {}},
            "description": "SSE stream. Consume with `EventSource` or `fetch` + `ReadableStream`.",
        }
    },
)
def chat_stream(payload: ChatRequest) -> StreamingResponse:
    """Stream live progress for a multi-agent suburb query.

    Emits one or more `step` events as each specialist agent starts
    (e.g. `"Analysing crime data · Chippendale"`), periodic `heartbeat`
    events every ~8 seconds to prevent proxy timeouts, and a final `done`
    event whose `data` field contains the complete response (same schema
    as the blocking `/api/chat` endpoint).

    **SSE frame format**
    ```
    event: step
    data: {"label": "Searching Reddit posts · Newtown", "category": "sentiment"}

    event: heartbeat
    data: {}

    event: done
    data: {"answer": "...", "suburb_scores": [...], ...}
    ```

    **Client usage (JavaScript)**
    ```js
    const res = await fetch("/api/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: "Tell me about Newtown" }),
    });
    const reader = res.body.getReader();
    // parse frames split on "\\n\\n"
    ```
    """
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
