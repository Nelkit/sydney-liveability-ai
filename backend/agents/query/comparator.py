"""Comparator specialist for side-by-side suburb analysis.

Inputs: two suburbs and selected categories
Outputs: comparison dictionary and category winners
Owner: assign in team meeting
"""

from __future__ import annotations

from typing import Any

from crewai import Agent, Task
from crewai.tools import tool

from agents.query.crime import _query_crime_impl
from agents.query.gis import _query_gis_impl
from agents.query.sentiment import _query_sentiment_impl
from config import get_agent_llm


def _query_comparator_impl(suburb_a: str, suburb_b: str, categories: list[str]) -> dict[str, Any]:
    """Internal implementation: compare two suburbs."""
    # TODO(owner): Implement category-wise comparison without agent nesting.
    # 1) For each requested category call imported tools directly:
    #    query_crime_tool, query_sentiment_tool, query_gis_tool.
    # 2) Build per-category side-by-side payload for suburb_a and suburb_b.
    # 3) Compute winner logic:
    #    higher score wins for sentiment/gis; lower crime_index wins for crime.
    # 4) Return {suburb_a, suburb_b, comparison, winner}.
    return {
        "suburb_a": suburb_a,
        "suburb_b": suburb_b,
        "comparison": {category: {} for category in categories},
        "winner": {category: "tie" for category in categories},
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
