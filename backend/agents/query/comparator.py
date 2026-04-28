"""Comparator specialist for side-by-side suburb analysis.

Inputs: two suburbs and selected categories
Outputs: comparison dictionary and category winners
Owner: Padmasri Srinivas or Luis Robinson
"""

from __future__ import annotations

from typing import Any

from crewai import Agent, Task
from crewai.tools import tool

from agents.query.crime import _query_crime_impl
from agents.query.gis import _query_gis_impl
from agents.query.sentiment import _query_sentiment_impl
from config import get_agent_llm


_IMPL_MAP = {
    "gis": lambda suburb: _query_gis_impl(suburb),
    "crime": lambda suburb: _query_crime_impl(suburb),
    "sentiment": lambda suburb: _query_sentiment_impl(suburb),
}

_PENDING_SENTINEL = "pending for implementation"


def _is_pending(value: Any) -> bool:
    return isinstance(value, str) and _PENDING_SENTINEL in value


def _gis_winner(result_a: dict, result_b: dict, suburb_a: str, suburb_b: str) -> str:
    score_a = result_a.get("combined_score")
    score_b = result_b.get("combined_score")
    if not isinstance(score_a, (int, float)) or not isinstance(score_b, (int, float)):
        return "tie"
    if score_a > score_b:
        return suburb_a
    if score_b > score_a:
        return suburb_b
    return "tie"


def _crime_winner(result_a: dict, result_b: dict, suburb_a: str, suburb_b: str) -> str:
    sev_a = result_a.get("crime_severity")
    sev_b = result_b.get("crime_severity")
    if _is_pending(sev_a) or _is_pending(sev_b):
        return "tie"
    if not isinstance(sev_a, (int, float)) or not isinstance(sev_b, (int, float)):
        return "tie"
    # Lower crime severity is better
    if sev_a < sev_b:
        return suburb_a
    if sev_b < sev_a:
        return suburb_b
    return "tie"


def _sentiment_winner(result_a: dict, result_b: dict, suburb_a: str, suburb_b: str) -> str:
    overall_a = result_a.get("overall")
    overall_b = result_b.get("overall")
    if _is_pending(overall_a) or _is_pending(overall_b):
        return "tie"
    if not isinstance(overall_a, (int, float)) or not isinstance(overall_b, (int, float)):
        return "tie"
    if overall_a > overall_b:
        return suburb_a
    if overall_b > overall_a:
        return suburb_b
    return "tie"


_WINNER_FN = {
    "gis": _gis_winner,
    "crime": _crime_winner,
    "sentiment": _sentiment_winner,
}


def _query_comparator_impl(suburb_a: str, suburb_b: str, categories: list[str]) -> dict[str, Any]:
    """Internal implementation: compare two suburbs category by category."""
    data_categories = [c for c in categories if c in _IMPL_MAP]

    comparison: dict[str, Any] = {}
    winner: dict[str, str] = {}

    for category in data_categories:
        impl = _IMPL_MAP[category]
        try:
            result_a = impl(suburb_a)
            result_b = impl(suburb_b)
            comparison[category] = {suburb_a: result_a, suburb_b: result_b}
            winner[category] = _WINNER_FN[category](result_a, result_b, suburb_a, suburb_b)
        except Exception as exc:
            comparison[category] = {"error": str(exc)}
            winner[category] = "tie"

    return {
        "suburb_a": suburb_a,
        "suburb_b": suburb_b,
        "comparison": comparison,
        "winner": winner,
    }


@tool("query_comparator_tool")
def query_comparator_tool(suburb_a: str, suburb_b: str, categories: list[str]) -> dict[str, Any]:
    """Wrapper tool for CrewAI: compare suburbs."""
    return _query_comparator_impl(suburb_a, suburb_b, categories)


comparator_agent = Agent(
    role="Query Comparator",
    goal="Compare suburbs category-by-category using specialist tool outputs.",
    backstory="You convert multiple metrics into a balanced side-by-side decision view.",
    llm=get_agent_llm("comparator"),
    tools=[query_comparator_tool],
    verbose=True,
)

comparator_task = Task(
    description="Compare two suburbs across selected categories and choose winners.",
    expected_output="JSON: {suburb_a, suburb_b, comparison, winner}.",
    agent=comparator_agent,
)


def run(input_data: dict[str, Any]) -> dict[str, Any]:
    """Isolated execution helper for query crew routing."""
    return _query_comparator_impl(
        suburb_a=str(input_data.get("suburb_a", "")),
        suburb_b=str(input_data.get("suburb_b", "")),
        categories=list(input_data.get("categories", [])),
    )


if __name__ == "__main__":
    print(run({"suburb_a": "Newtown", "suburb_b": "Glebe", "categories": ["gis"]}))
