"""Query crew orchestration for per-question specialist execution."""

from __future__ import annotations

from typing import Any

from crewai import Crew, Process

from agents.query.comparator import comparator_agent, run as run_comparator
from agents.query.crime import crime_agent, run as run_crime
from agents.query.gis import gis_agent, run as run_gis
from agents.query.router import router_agent, run as run_router
from agents.query.sentiment import run as run_sentiment
from agents.query.sentiment import sentiment_agent
from agents.query.synthesiser import run as run_synthesiser
from agents.query.synthesiser import synthesiser_agent


def build_query_crew() -> Crew:
    """Return all six query agents in sequential crew order."""
    return Crew(
        agents=[
            router_agent,
            crime_agent,
            sentiment_agent,
            gis_agent,
            comparator_agent,
            synthesiser_agent,
        ],
        process=Process.sequential,
        verbose=True,
    )


def run_query(question: str, weights: dict[str, Any] | None = None) -> dict[str, Any]:
    """Run router first, then activated specialists for all suburbs, and synthesiser last."""
    try:
        router_output = run_router({"question": question})
        categories = list(router_output.get("categories", []))
        suburbs = list(router_output.get("suburbs_mentioned", []))

        if "out_of_scope" in categories:
            return run_synthesiser(
                {
                    "question": question,
                    "router": router_output,
                    "outputs": {},
                }
            )

        specialist_outputs: dict[str, Any] = {}

        # Run single-suburb specialists for each suburb mentioned
        for specialist_name in ["crime", "sentiment", "gis"]:
            if specialist_name in categories and suburbs:
                specialist_outputs[specialist_name] = {}
                run_func = {
                    "crime": run_crime,
                    "sentiment": run_sentiment,
                    "gis": run_gis,
                }[specialist_name]
                for suburb in suburbs:
                    print(f"Running {specialist_name} agent for suburb: {suburb}")
                    specialist_outputs[specialist_name][suburb] = run_func(
                        {"suburb": suburb}
                    )

        # Run comparator only if 2+ suburbs are mentioned
        if "comparator" in categories and len(suburbs) >= 2:
            print(f"Running comparator agent for suburbs: {suburbs[0]} and {suburbs[1]}")
            specialist_outputs["comparator"] = run_comparator(
                {"suburb_a": suburbs[0], "suburb_b": suburbs[1], "categories": categories}
            )

        synthesis_payload = {
            "question": question,
            "weights": weights or {},
            "router": router_output,
            "outputs": specialist_outputs,
        }
        return run_synthesiser(synthesis_payload)
    except Exception as e:
        import traceback
        print(f"ERROR in run_query: {e}")
        traceback.print_exc()
        raise


if __name__ == "__main__":
    print(run_query("Compare Newtown versus Glebe for amenities and safety"))
