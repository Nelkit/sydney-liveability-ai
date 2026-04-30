"""Sentiment specialist for aspect and emotion signals.

Inputs: suburb name, optional aspect filter, optional question (for
question-driven retrieval).
Outputs: aspect scores (with explicit nulls), emotion profile, overall
sentiment label, an `evidence_trace` of tool calls, and a `sources`
list of grounded quotes for the synthesiser.

Owner: Kai (Ying-Kai Liao)

Implementation note. The original `add-agentic-rag-synthesiser` design
called for a LangGraph-style ReAct loop bounded to 5 tool calls per
turn. This repo uses CrewAI; the equivalent contract is implemented
here as a deterministic mini-pipeline over the new tool registry
(`backend/core/agent/tools.py`). The trace shape is identical
(`step, tool, arguments, reasoning, result_count, result_preview,
elapsed_ms`) so the synthesiser and report figures are unchanged.
"""

from __future__ import annotations

import json
import time
from typing import Any, Optional

from crewai import Agent, Task
from crewai.tools import tool

from config import get_agent_llm
from core.agent import tools as agent_tools
from core.nlp.aspects import ASPECT_TAXONOMY

POSITIVE_THRESHOLD = 0.65
NEGATIVE_THRESHOLD = 0.45

# Mirror the design's per-turn budget. Counted against question-driven
# calls only (search_posts and deliberate dimension routing). The bulk
# structured-aspect normalisation runs unbounded — it's a deterministic
# fan-out across the eight liveability dimensions, not a ReAct decision.
MAX_QUESTION_CALLS = 5


def _overall_label(aspect_scores: list[float]) -> str:
    """Map the mean of non-null aspect scores to a coarse label."""
    if not aspect_scores:
        return "no_data"
    avg = sum(aspect_scores) / len(aspect_scores)
    if avg > POSITIVE_THRESHOLD:
        return "positive"
    if avg < NEGATIVE_THRESHOLD:
        return "negative"
    return "neutral"


def _route_dimension(question: str, asked_aspect: Optional[str]) -> Optional[str]:
    """Pick the dimension most relevant to the question.

    If the caller passed `aspect` we honour it. Otherwise we use the
    same keyword table the extractor uses (`ASPECT_TAXONOMY`) so the
    routing here matches the rest of the pipeline.
    """
    if asked_aspect and asked_aspect in ASPECT_TAXONOMY:
        return asked_aspect
    if not question:
        return None
    lowered = question.lower()
    for dim, meta in ASPECT_TAXONOMY.items():
        for keyword in meta["search_keywords"]:
            if keyword.lower() in lowered:
                return dim
    return None


def _trace_entry(
    step: int,
    tool_name: str,
    arguments: dict[str, Any],
    reasoning: str,
    result: dict[str, Any],
    elapsed_ms: float,
) -> dict[str, Any]:
    """Build a TraceEntry matching the shape promised in the agent README."""
    if tool_name == "search_posts" and result.get("status") == "ok":
        results = result.get("results") or []
        result_count = len(results)
        first_text = (results[0].get("text") if results else "") or ""
        preview = first_text[:200]
    elif result.get("status") == "no_data":
        result_count = 0
        preview = result.get("reason") or "no_data"
    else:
        # get_suburb_aspect / compare_suburbs return a single structured dict
        result_count = 1 if result.get("status") == "ok" else 0
        preview = json.dumps(
            {k: v for k, v in result.items() if k not in {"results"}},
            default=str,
        )[:200]
    return {
        "step": step,
        "tool": tool_name,
        "arguments": arguments,
        "reasoning": reasoning,
        "result_count": result_count,
        "result_preview": preview,
        "elapsed_ms": round(elapsed_ms, 2),
    }


def _call(tool_name: str, **kwargs) -> tuple[dict[str, Any], float]:
    """Dispatch a tool call and time it. Returns (result, elapsed_ms)."""
    started = time.perf_counter()
    if tool_name == "get_suburb_aspect":
        result = agent_tools.get_suburb_aspect(**kwargs)
    elif tool_name == "search_posts":
        result = agent_tools.search_posts(**kwargs)
    elif tool_name == "compare_suburbs":
        result = agent_tools.compare_suburbs(**kwargs)
    else:
        result = {"status": "error", "reason": f"unknown tool {tool_name}"}
    return result, (time.perf_counter() - started) * 1000.0


def _query_sentiment_impl(
    suburb: str,
    aspect: str | None = None,
    question: str | None = None,
) -> dict[str, Any]:
    """Return aspects, emotions, overall label, evidence trace, and sources.

    The cached `SuburbAnalysis` is the source of structured aspect
    scores and the emotion profile. When `question` is provided, we
    additionally call `search_posts` to pull grounded quotes for the
    synthesiser to cite.
    """
    suburb = (suburb or "").strip()
    if not suburb:
        return {
            "suburb": "",
            "status": "no_data",
            "aspects": {},
            "emotions": {},
            "overall": "no_data",
            "evidence_trace": [],
            "sources": [],
        }

    analysis = agent_tools._load_cached_analysis(suburb)
    if not analysis:
        return {
            "suburb": suburb,
            "status": "no_data",
            "reason": "no cached SuburbAnalysis for this suburb",
            "aspects": {},
            "emotions": {},
            "overall": "no_data",
            "evidence_trace": [],
            "sources": [],
        }

    aspects_raw = analysis.get("aspects") or {}
    emotions = analysis.get("emotions") or {}

    # Build the structured aspects payload via get_suburb_aspect so each
    # entry carries the same status/no_data shape the design specifies,
    # not a free-form dict from the JSON file. The bulk fan-out is not
    # counted against MAX_QUESTION_CALLS — that budget is reserved for
    # question-driven retrieval below.
    evidence_trace: list[dict[str, Any]] = []
    aspects: dict[str, Any] = {}
    non_null_scores: list[float] = []
    step = 0
    question_calls_used = 0

    for dim in aspects_raw.keys():
        step += 1
        result, elapsed = _call("get_suburb_aspect", suburb=suburb, dimension=dim)
        evidence_trace.append(
            _trace_entry(
                step=step,
                tool_name="get_suburb_aspect",
                arguments={"suburb": suburb, "dimension": dim},
                reasoning="structured-aspect lookup for sentiment payload",
                result=result,
                elapsed_ms=elapsed,
            )
        )
        if result.get("status") == "ok":
            aspects[dim] = {
                "score": result["score"],
                "mentions": result["mentions"],
                "confidence": result["confidence"],
                "coverage": result["coverage"],
                "source": result["source"],
            }
            score = result.get("score")
            if isinstance(score, (int, float)):
                non_null_scores.append(float(score))
        else:
            aspects[dim] = {
                "status": "no_data",
                "reason": "no Reddit coverage and no cross-modal proxy",
            }

    # Question-driven retrieval. We pick the most relevant dimension and
    # pull up to 3 grounded chunks. If the dimension is null-scored,
    # search_posts short-circuits with no_data and the synthesiser can
    # verbalise the absence honestly. ChromaDB import is deferred inside
    # the tool, so this whole block is a no-op when the index isn't
    # populated (the search returns empty).
    sources: list[dict[str, Any]] = []
    routed_dim = _route_dimension(question or "", aspect)
    if question and routed_dim and question_calls_used < MAX_QUESTION_CALLS:
        step += 1
        question_calls_used += 1
        result, elapsed = _call(
            "search_posts",
            suburb=suburb,
            dimension=routed_dim,
            query=question,
            k=3,
        )
        evidence_trace.append(
            _trace_entry(
                step=step,
                tool_name="search_posts",
                arguments={
                    "suburb": suburb,
                    "dimension": routed_dim,
                    "query": question,
                    "k": 3,
                },
                reasoning=f"pull grounded quotes for question-relevant dimension '{routed_dim}'",
                result=result,
                elapsed_ms=elapsed,
            )
        )
        if result.get("status") == "ok":
            for hit in result.get("results") or []:
                meta = hit.get("metadata") or {}
                sources.append(
                    {
                        "text": hit.get("text", ""),
                        "suburb": meta.get("suburb") or suburb,
                        "source": meta.get("source") or "reddit",
                        "url": meta.get("url") or "",
                        "dimension": meta.get("dimension") or routed_dim,
                        "distance": hit.get("distance"),
                    }
                )

    # Fallback citations: when no question-driven results, fall back to
    # the curated `sources[]` from the cached analysis so the synthesiser
    # always has something to cite for known suburbs.
    if not sources:
        for quote in (analysis.get("sources") or [])[:3]:
            if not isinstance(quote, dict):
                continue
            sources.append(
                {
                    "text": quote.get("text", ""),
                    "suburb": suburb,
                    "source": "sentiment_quote",
                    "url": quote.get("url", ""),
                    "dimension": "general",
                }
            )

    return {
        "suburb": suburb,
        "status": "ok",
        "aspects": aspects,
        "emotions": emotions,
        "overall": _overall_label(non_null_scores),
        "evidence_trace": evidence_trace,
        "sources": sources,
    }


@tool("query_sentiment_tool")
def query_sentiment_tool(
    suburb: str,
    aspect: str | None = None,
    question: str | None = None,
) -> dict[str, Any]:
    """Wrapper tool for CrewAI: query sentiment data with optional question-driven retrieval."""
    return _query_sentiment_impl(suburb, aspect, question)


sentiment_agent = Agent(
    role="Query Sentiment Analyst",
    goal="Explain local sentiment using aspect scores, emotion distributions, and grounded quotes.",
    backstory=(
        "You transform structured sentiment tables and a Reddit vector index into "
        "clear suburb-level signals. You refuse to fabricate signals for "
        "dimensions the upstream pipeline marked no-data."
    ),
    llm=get_agent_llm("sentiment"),
    tools=[query_sentiment_tool],
    verbose=True,
)

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
