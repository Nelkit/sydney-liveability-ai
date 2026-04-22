"""Crime specialist for suburb-level safety evidence.

Inputs: suburb name, optional crime_type
Outputs: suburb crime_summary and trend signal
Owner: Amanda
"""

from __future__ import annotations

from typing import Any

from crewai import Agent, Task
from crewai.tools import tool

from config import get_agent_llm


def _query_crime_impl(suburb: str, crime_type: str | None = None) -> dict[str, Any]:
    """Internal implementation: query BOCSAR crime data."""
    # TODO(Amanda): Implement SQLAlchemy query against table `bocsar`.
    # 1) Filter by suburb and optional crime_type.
    # 2) Group by crime_type and year to build crime_summary counts.
    # 3) Compute trend from latest 2 years:
    #    improving if last_year_count < prev_year_count else worsening.
    # 4) Return {suburb, crime_summary, trend} with explicit year keys.
    return {
        "suburb": suburb,
        "crime_severity": "pending for implementation",
        "crime_summary": {
            "assault": "pending for implementation",
            "theft": "pending for implementation",
            "robbery": "pending for implementation",
            "burglary": "pending for implementation",
        },
        "trend": "pending for implementation",
        "implementation_status": "BOCSAR data integration in progress",
    }


@tool("query_crime_tool")
def query_crime_tool(suburb: str, crime_type: str | None = None) -> dict[str, Any]:
    """Wrapper tool for CrewAI: query crime data."""
    return _query_crime_impl(suburb, crime_type)


crime_agent = Agent(
    role="Query Crime Analyst",
    goal="Provide structured safety signals from BOCSAR for selected suburbs.",
    backstory="You analyze offence trends and summarize risk movement by suburb.",
    llm=get_agent_llm("crime"),
    tools=[query_crime_tool],
    verbose=True,
)

crime_task = Task(
    description="Fetch crime summaries and trend labels for one suburb.",
    expected_output="JSON: {suburb, crime_summary, trend}.",
    agent=crime_agent,
)


def run(input_data: dict[str, Any]) -> dict[str, Any]:
    """Isolated execution helper for query crew routing."""
    return _query_crime_impl(
        suburb=str(input_data.get("suburb", "")),
        crime_type=input_data.get("crime_type"),
    )


if __name__ == "__main__":
    print(run({"suburb": "Newtown"}))
