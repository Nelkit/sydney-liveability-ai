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


def _summarise_evidence_trace(specialist_outputs: dict[str, Any]) -> dict[str, Any]:
    """Aggregate sentiment specialists' `evidence_trace` into a summary dict.

    Returns the deterministic shape promised by the `quality.evidence_trace_summary`
    contract: total length, per-tool counts, the last action across all suburbs by
    max step, and a no_data count detected by substring match on `result_preview`.
    """
    sentiment_outputs = specialist_outputs.get("sentiment") if isinstance(specialist_outputs, dict) else None
    summary: dict[str, Any] = {
        "length": 0,
        "by_tool": {},
        "last_action": None,
        "no_data_count": 0,
    }
    if not isinstance(sentiment_outputs, dict):
        return summary

    last_action: dict[str, Any] | None = None
    last_step = -1
    for suburb, result in sentiment_outputs.items():
        if not isinstance(result, dict):
            continue
        for entry in result.get("evidence_trace") or []:
            if not isinstance(entry, dict):
                continue
            summary["length"] += 1
            tool_name = str(entry.get("tool") or "unknown")
            summary["by_tool"][tool_name] = summary["by_tool"].get(tool_name, 0) + 1
            preview = str(entry.get("result_preview") or "")
            if "no_data" in preview:
                summary["no_data_count"] += 1
            step = entry.get("step")
            if isinstance(step, int) and step > last_step:
                last_step = step
                args = entry.get("arguments") or {}
                last_action = {
                    "step": step,
                    "tool": tool_name,
                    "suburb": args.get("suburb") or suburb,
                    "dimension": args.get("dimension"),
                    "result_count": entry.get("result_count"),
                }
    summary["last_action"] = last_action
    return summary


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
            response = run_synthesiser(
                {
                    "question": question,
                    "router": router_output,
                    "outputs": {},
                }
            )
            response["quality"] = {"evidence_trace_summary": _summarise_evidence_trace({})}
            response["outputs"] = {}
            response["router"] = router_output
            return response

        specialist_outputs: dict[str, Any] = {}

        # Run single-suburb specialists for each suburb mentioned. The
        # sentiment agent additionally consumes the original question so
        # it can route question-driven retrieval over the Reddit index;
        # the other specialists ignore the extra key.
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
                        {"suburb": suburb, "question": question}
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
        response = run_synthesiser(synthesis_payload)
        response["quality"] = {
            "evidence_trace_summary": _summarise_evidence_trace(specialist_outputs)
        }
        # Expose specialist outputs and router for the offline eval script.
        # The /api/chat endpoint filters its response shape, so this leak is
        # internal to run_query callers (eval script) only.
        response["outputs"] = specialist_outputs
        response["router"] = router_output
        return response
    except Exception as e:
        import traceback
        print(f"ERROR in run_query: {e}")
        traceback.print_exc()
        raise


if __name__ == "__main__":
    print(run_query("Compare Newtown versus Glebe for amenities and safety"))
