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

`evidence_trace` is recovered as a side channel: each tool wrapper
appends a TraceEntry to a per-call ContextVar, and the impl drains
it after the agent stops. The trace mirrors what the agent actually
called, not what an orchestrator decided in advance, so it is an
audit surface rather than a constraint.

Owner: Kai (Ying-Kai Liao)
"""

from __future__ import annotations

import contextvars
import json
import re
import time
from typing import Any, Optional

from crewai import Agent, Crew, Process, Task
from crewai.tools import tool

from config import get_agent_llm
from core.agent import tools as agent_tools

POSITIVE_THRESHOLD = 0.65
NEGATIVE_THRESHOLD = 0.45

# Per-call trace accumulator. Set to a fresh list at the start of
# `_query_sentiment_impl`; the tool wrappers append a TraceEntry on
# every invocation. Exposing this as a side channel lets us recover
# the audit surface without re-imposing a deterministic loop on the
# agent.
_TRACE_CTX: contextvars.ContextVar[Optional[list[dict[str, Any]]]] = contextvars.ContextVar(
    "sentiment_trace_ctx", default=None
)


def _result_preview(tool_name: str, result: dict[str, Any]) -> tuple[int, str]:
    if tool_name == "search_posts" and result.get("status") == "ok":
        results = result.get("results") or []
        first_text = (results[0].get("text") if results else "") or ""
        return len(results), first_text[:200]
    if result.get("status") == "no_data":
        return 0, str(result.get("reason") or "no_data")
    if result.get("status") == "ok":
        preview = json.dumps(
            {k: v for k, v in result.items() if k not in {"results"}},
            default=str,
        )
        return 1, preview[:200]
    return 0, str(result.get("reason") or result.get("status") or "error")


def _record_call(
    tool_name: str,
    arguments: dict[str, Any],
    result: dict[str, Any],
    elapsed_ms: float,
) -> None:
    trace = _TRACE_CTX.get()
    if trace is None:
        return
    count, preview = _result_preview(tool_name, result)
    trace.append(
        {
            "step": len(trace) + 1,
            "tool": tool_name,
            "arguments": arguments,
            "reasoning": "",
            "result_count": count,
            "result_preview": preview,
            "elapsed_ms": round(elapsed_ms, 2),
        }
    )

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

_DIMENSION_KEYWORDS: dict[str, list[str]] = {
    "safety": ["safe", "crime", "dangerous", "security", "unsafe"],
    "food_and_cafe": ["food", "cafe", "coffee", "restaurant", "eat", "dining"],
    "nightlife": ["nightlife", "night", "bar", "pub", "club", "entertainment"],
    "affordability": ["afford", "cheap", "expensive", "rent", "price", "cost"],
    "transport": ["transport", "bus", "train", "commute", "transit", "walk"],
    "community": ["community", "vibe", "feel", "residents", "neighbour", "people"],
    "noise": ["noise", "quiet", "loud", "noisy"],
    "green_space": ["park", "green", "nature", "outdoor", "garden"],
}


def _relevant_dimensions(question: str) -> list[str]:
    """Return the 1-3 dimensions most relevant to the question.

    For open-ended questions ("tell me about X") return the top 3 most
    commonly asked dimensions. For specific questions return only the
    matching ones, capped at 3 to limit tool calls.
    """
    lowered = question.lower()
    matched = [
        dim for dim, keywords in _DIMENSION_KEYWORDS.items()
        if any(kw in lowered for kw in keywords)
    ]
    if matched:
        return matched[:3]
    # Generic question — return the highest-signal dimensions only
    return ["community", "safety", "transport"]


@tool("get_suburb_aspect")
def _get_suburb_aspect_tool(suburb: str, dimension: str) -> dict[str, Any]:
    """Return the cached aspect score for one (suburb, dimension) pair.

    Status is `ok` with score/source/coverage, or `no_data` when the
    upstream pipeline marked the dimension null. Use this to gather
    structured signals before deciding whether to also call
    search_posts.
    """
    started = time.perf_counter()
    result = agent_tools.get_suburb_aspect(suburb=suburb, dimension=dimension)
    elapsed = (time.perf_counter() - started) * 1000.0
    _record_call(
        "get_suburb_aspect",
        {"suburb": suburb, "dimension": dimension},
        result,
        elapsed,
    )
    return result


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
    started = time.perf_counter()
    result = agent_tools.search_posts(
        suburb=suburb,
        dimension=dimension or None,
        query=query,
        k=k,
    )
    elapsed = (time.perf_counter() - started) * 1000.0
    _record_call(
        "search_posts",
        {"suburb": suburb, "dimension": dimension, "query": query, "k": k},
        result,
        elapsed,
    )
    return result


@tool("compare_suburbs")
def _compare_suburbs_tool(suburbs: list[str], dimension: str) -> dict[str, Any]:
    """Rank a list of suburbs descending by aspect score for one dimension.

    Refuses inputs longer than ten suburbs. Drops null-scored entries
    into a `dropped` list. Use this only for explicit comparison
    questions, not as a substitute for global ranking.
    """
    started = time.perf_counter()
    result = agent_tools.compare_suburbs(suburbs=suburbs, dimension=dimension)
    elapsed = (time.perf_counter() - started) * 1000.0
    _record_call(
        "compare_suburbs",
        {"suburbs": suburbs, "dimension": dimension},
        result,
        elapsed,
    )
    return result


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
    max_iter=4,
)


def _build_task_description(suburb: str, aspect: Optional[str], question: str) -> str:
    if aspect:
        dims_to_query = [aspect] if aspect in LIVEABILITY_DIMENSIONS else _relevant_dimensions(question)
    else:
        dims_to_query = _relevant_dimensions(question)
    dims_csv = ", ".join(dims_to_query)

    return f"""You are answering a question about resident sentiment in a single Sydney suburb.

Suburb: {suburb}
Question: {question}

IMPORTANT — tool call budget: you have at most 4 tool calls total. Query ONLY these dimensions: {dims_csv}.
Do NOT query dimensions outside this list. Stop as soon as you have scores for all listed dimensions.

Tools available:
- get_suburb_aspect(suburb, dimension)
- search_posts(suburb, query, dimension, k)
- compare_suburbs(suburbs, dimension)

Grounding rule: for qualitative questions call search_posts once on the most relevant dimension. For score lookups get_suburb_aspect alone is fine. If get_suburb_aspect returns status="no_data", skip search_posts for that dimension.

When done, output ONLY a single JSON object — no prose, no markdown fences:

{{"aspects": {{"<dimension>": {{"score": <float 0-1 or null>, "source": "<reddit|fallback|none>", "coverage": "<strong|weak|none>"}}}}, "sources": [{{"text": "<quote>", "suburb": "<suburb>", "dimension": "<dimension>", "url": "<url>"}}]}}

Include only queried dimensions. "sources" must contain only quotes from search_posts calls."""


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

    trace: list[dict[str, Any]] = []
    token = _TRACE_CTX.set(trace)
    try:
        try:
            crew_output = crew.kickoff()
        except Exception as exc:
            return _no_data_response(suburb, reason=f"agent execution failed: {exc}")
    finally:
        _TRACE_CTX.reset(token)

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
        "evidence_trace": trace,
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
