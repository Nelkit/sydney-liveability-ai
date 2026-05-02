"""Sentiment specialist — full agentic RAG (A-RAG style).

Inputs: suburb name, optional aspect hint, optional question.
Outputs: aspects (only those the agent queried), emotion profile,
overall sentiment label, and a `sources` list of grounded quotes.

The agent has direct access to three retrieval tools and decides
adaptively which to call, in what order, and when to stop. There is
no deterministic dimension fan-out and no question-call ceiling — the
LLM owns the strategy. This implements the "full ARAG" pattern in the
sense of Du et al. (2026): autonomous strategy, iterative execution,
interleaved tool use.

`evidence_trace` is preserved as an empty list in the output dict so
the synthesiser, the `/api/chat` quality field, and existing tests
keep their shape; the synthesiser already handles an empty trace by
omitting the trace block from its prompt.

Owner: Kai (Ying-Kai Liao)
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional

from crewai import Agent, Crew, Process, Task
from crewai.tools import tool

from config import get_agent_llm
from core.agent import tools as agent_tools

POSITIVE_THRESHOLD = 0.65
NEGATIVE_THRESHOLD = 0.45

LIVEABILITY_DIMENSIONS = [
    "safety",
    "food_and_cafe",
    "nightlife",
    "affordability",
    "transport",
    "community",
    "noise",
    "green_space",
]


@tool("get_suburb_aspect")
def _get_suburb_aspect_tool(suburb: str, dimension: str) -> dict[str, Any]:
    """Return the cached aspect score for one (suburb, dimension) pair.

    Status is `ok` with score/source/coverage, or `no_data` when the
    upstream pipeline marked the dimension null. Use this to gather
    structured signals before deciding whether to also call
    search_posts.
    """
    return agent_tools.get_suburb_aspect(suburb=suburb, dimension=dimension)


@tool("search_posts")
def _search_posts_tool(
    suburb: str,
    query: str,
    dimension: str = "",
    k: int = 5,
) -> dict[str, Any]:
    """Semantic search over Reddit chunks for one suburb.

    Filter by `dimension` (one of the eight liveability dimensions) when
    you want quotes specific to a topic; pass an empty string to search
    all dimensions. Use this to pull grounded quotes that support a
    claim about resident sentiment.
    """
    return agent_tools.search_posts(
        suburb=suburb,
        dimension=dimension or None,
        query=query,
        k=k,
    )


@tool("compare_suburbs")
def _compare_suburbs_tool(suburbs: list[str], dimension: str) -> dict[str, Any]:
    """Rank a list of suburbs descending by aspect score for one dimension.

    Refuses inputs longer than ten suburbs. Drops null-scored entries
    into a `dropped` list. Use this only for explicit comparison
    questions, not as a substitute for global ranking.
    """
    return agent_tools.compare_suburbs(suburbs=suburbs, dimension=dimension)


sentiment_agent = Agent(
    role="Query Sentiment Analyst",
    goal=(
        "Answer questions about resident sentiment in Sydney suburbs by "
        "calling retrieval tools adaptively. Refuse to fabricate when a "
        "tool returns no_data."
    ),
    backstory=(
        "You analyse Sydney suburbs by combining structured aspect scores "
        "with grounded Reddit quotes. You decide which tools to call and "
        "stop as soon as you have enough evidence to answer."
    ),
    llm=get_agent_llm("sentiment"),
    tools=[
        _get_suburb_aspect_tool,
        _search_posts_tool,
        _compare_suburbs_tool,
    ],
    verbose=True,
)


def _build_task_description(suburb: str, aspect: Optional[str], question: str) -> str:
    aspect_hint = (
        f"\nDimension hint (caller-provided, treat as guidance not a constraint): {aspect}"
        if aspect
        else ""
    )
    dims_csv = ", ".join(LIVEABILITY_DIMENSIONS)
    return f"""You are answering a question about resident sentiment in a single Sydney suburb.

Suburb: {suburb}
Question: {question}{aspect_hint}

Liveability dimensions you can query: {dims_csv}.

Decide which retrieval tools to call and in what order. Use as few tool calls as you need; stop as soon as the evidence supports a confident answer. If a tool returns status="no_data" or status="error", record the absence and do not fabricate.

Tools available (you call them by name; the framework wires the arguments):
- get_suburb_aspect(suburb, dimension)
- search_posts(suburb, query, dimension, k)
- compare_suburbs(suburbs, dimension)

When you are done, output ONLY a single JSON object with this exact shape — no prose, no markdown fences, no commentary:

{{"aspects": {{"<dimension>": {{"score": <float between 0 and 1, or null>, "source": "<reddit|fallback|none>", "coverage": "<strong|weak|none>"}}}}, "sources": [{{"text": "<quote>", "suburb": "<suburb>", "dimension": "<dimension>", "url": "<url>"}}]}}

Include only the dimensions you actually queried. The "sources" array must contain only quotes returned by search_posts; leave it empty if you made no search calls or all searches were no_data."""


_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def _parse_agent_json(raw: str) -> Optional[dict[str, Any]]:
    if not raw:
        return None
    fence = _JSON_FENCE_RE.search(raw)
    if fence:
        candidate = fence.group(1)
    else:
        start = raw.find("{")
        end = raw.rfind("}")
        if start == -1 or end <= start:
            return None
        candidate = raw[start : end + 1]
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _overall_label(aspects: dict[str, Any]) -> str:
    scores = [
        float(entry["score"])
        for entry in aspects.values()
        if isinstance(entry, dict) and isinstance(entry.get("score"), (int, float))
    ]
    if not scores:
        return "no_data"
    avg = sum(scores) / len(scores)
    if avg > POSITIVE_THRESHOLD:
        return "positive"
    if avg < NEGATIVE_THRESHOLD:
        return "negative"
    return "neutral"


def _no_data_response(suburb: str, reason: Optional[str] = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "suburb": suburb,
        "status": "no_data",
        "aspects": {},
        "emotions": {},
        "overall": "no_data",
        "evidence_trace": [],
        "sources": [],
    }
    if reason:
        payload["reason"] = reason
    return payload


def _query_sentiment_impl(
    suburb: str,
    aspect: str | None = None,
    question: str | None = None,
) -> dict[str, Any]:
    """Run the full agentic RAG loop for one suburb and return its payload."""
    suburb = (suburb or "").strip()
    if not suburb:
        return _no_data_response("")

    analysis = agent_tools._load_cached_analysis(suburb)
    if not analysis:
        return _no_data_response(suburb, reason="no cached SuburbAnalysis for this suburb")

    emotions = analysis.get("emotions") or {}
    effective_question = (question or "").strip() or (
        f"Summarise resident sentiment in {suburb} across relevant liveability dimensions."
    )

    task = Task(
        description=_build_task_description(suburb, aspect, effective_question),
        expected_output="A single JSON object with keys 'aspects' and 'sources'.",
        agent=sentiment_agent,
    )
    crew = Crew(
        agents=[sentiment_agent],
        tasks=[task],
        process=Process.sequential,
        verbose=False,
    )

    try:
        crew_output = crew.kickoff()
    except Exception as exc:
        return _no_data_response(suburb, reason=f"agent execution failed: {exc}")

    raw = getattr(crew_output, "raw", None) or str(crew_output or "")
    parsed = _parse_agent_json(raw)
    if not parsed:
        return _no_data_response(suburb, reason="agent did not return parseable JSON")

    aspects = parsed.get("aspects") or {}
    if not isinstance(aspects, dict):
        aspects = {}

    sources_raw = parsed.get("sources") or []
    sources: list[dict[str, Any]] = []
    if isinstance(sources_raw, list):
        for item in sources_raw:
            if isinstance(item, dict):
                sources.append(
                    {
                        "text": str(item.get("text", "")),
                        "suburb": str(item.get("suburb", suburb)),
                        "dimension": str(item.get("dimension", "general")),
                        "url": str(item.get("url", "")),
                        "source": str(item.get("source", "reddit")),
                    }
                )

    return {
        "suburb": suburb,
        "status": "ok",
        "aspects": aspects,
        "emotions": emotions,
        "overall": _overall_label(aspects),
        "evidence_trace": [],
        "sources": sources,
    }


sentiment_task = Task(
    description="Fetch sentiment, emotion, and grounded-quote evidence for one suburb.",
    expected_output="JSON: {suburb, status, aspects, emotions, overall, evidence_trace, sources}.",
    agent=sentiment_agent,
)


def run(input_data: dict[str, Any]) -> dict[str, Any]:
    """Isolated execution helper for query crew routing."""
    return _query_sentiment_impl(
        suburb=str(input_data.get("suburb", "")),
        aspect=input_data.get("aspect"),
        question=input_data.get("question"),
    )


if __name__ == "__main__":
    print(run({"suburb": "Newtown", "question": "what's transport like in Newtown?"}))
