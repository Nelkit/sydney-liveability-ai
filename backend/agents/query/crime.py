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
    from db.postgres import SessionLocal
    from sqlalchemy import text

    session = SessionLocal()
    try:
        # 1) Query bocsar table filtered by suburb and optional crime_type
        if crime_type:
            query = text("""
                SELECT crime_type, year, incident_count, sa4_area
                FROM bocsar
                WHERE suburb = :suburb AND crime_type = :crime_type
                ORDER BY crime_type, year
            """)
            rows = session.execute(query, {"suburb": suburb, "crime_type": crime_type}).fetchall()
        else:
            query = text("""
                SELECT crime_type, year, incident_count, sa4_area
                FROM bocsar
                WHERE suburb = :suburb
                ORDER BY crime_type, year
            """)
            rows = session.execute(query, {"suburb": suburb}).fetchall()

        if not rows:
            return {"suburb": suburb, "crime_summary": {}, "trend": "no data", "sa4_area": "N/A"}

        # 2) Build crime_summary and get sa4_area
        sa4_area = rows[0][3]
        crime_by_type: dict[str, dict[int, int]] = {}
        for crime_type_val, year, count, _ in rows:
            if crime_type_val not in crime_by_type:
                crime_by_type[crime_type_val] = {}
            crime_by_type[crime_type_val][year] = count

        crime_summary = {ct: sum(years.values()) for ct, years in crime_by_type.items()}

        # 3) Compute trend from latest 2 years
        all_years = sorted({year for years in crime_by_type.values() for year in years})
        if len(all_years) >= 2:
            last_year = all_years[-1]
            prev_year = all_years[-2]
            last_total = sum(years.get(last_year, 0) for years in crime_by_type.values())
            prev_total = sum(years.get(prev_year, 0) for years in crime_by_type.values())
            trend = "improving" if last_total < prev_total else "worsening"
        else:
            trend = "insufficient data"

        return {
            "suburb": suburb,
            "sa4_area": sa4_area,
            "crime_summary": crime_summary,
            "trend": trend,
        }

    finally:
        session.close()


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