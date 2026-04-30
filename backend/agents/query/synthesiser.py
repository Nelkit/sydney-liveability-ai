"""Synthesis agent that composes the final chat response.

Inputs: question, router output, and activated specialist outputs
Outputs: answer, sources, suburb_scores, map_state
Owner: Nelkit Chavez

LLM Configuration:
- DEV: Uses the shared LLM_MODEL from .env (default: mistralai/mistral-7b-instruct, free on OpenRouter)
- PROD: Change LLM_MODEL in .env to anthropic/claude-3.5-sonnet, or override just this agent with LLM_AGENT_MODELS_JSON
           or use ANTHROPIC_API_KEY with anthropic/claude-3-5-sonnet-20241022
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from crewai import Agent, Task
from crewai.tools import tool
from sqlalchemy import select

from config import get_agent_llm, settings
from db.chromadb import PDF_COLLECTION, REDDIT_COLLECTION, query_chunks
from db.models import OsmScore, Suburb, TransportScore
from db.postgres import SessionLocal

_REDDIT_CACHE_DIR = Path(__file__).resolve().parents[3] / "data" / "processed" / "reddit_analyses"


def _get_reddit_context(suburb: str) -> dict[str, Any] | None:
    """Load pre-computed Reddit NLP analysis for a suburb from local file cache."""
    slug = suburb.lower().replace(" ", "_").replace("-", "_")
    path = _REDDIT_CACHE_DIR / f"{slug}.json"
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _retrieve_chromadb_chunks(
    question: str,
    suburbs_list: list[str] | None = None,
    k_per_collection: int = 3,
) -> list[dict[str, Any]]:
    """Query community_insights and reddit_posts for semantically relevant chunks."""
    suburb_filter = {"suburb": {"$in": suburbs_list}} if suburbs_list else None
    chunks: list[dict[str, Any]] = []
    for collection in (PDF_COLLECTION, REDDIT_COLLECTION):
        try:
            results = query_chunks(question, collection_name=collection, k=k_per_collection, filters=suburb_filter)
            chunks.extend(results)
        except Exception:
            pass
    return chunks


def _normalise_debug_mode() -> str:
    """Return normalized debug mode from env: off, gis, all."""
    return (settings.synthesis_debug_mode or "off").strip().lower()




def _format_debug_passthrough(agent_key: str, agent_output: dict[str, Any]) -> dict[str, Any]:
    """Render one agent output directly in chat for implementation-time debugging."""
    suburb = str(agent_output.get("suburb", ""))
    combined_score = agent_output.get("combined_score")

    # Keep response shape identical to /api/chat contract for frontend compatibility.
    return {
        "answer": (
            f"{agent_key.upper()} debug output for {suburb or 'unknown suburb'}"
            f" (combined_score={combined_score}):\n"
            f"{json.dumps(agent_output, ensure_ascii=True, indent=2)}"
        ),
        "sources": [
            {
                "text": f"Structured data returned by {agent_key} agent.",
                "suburb": suburb,
                "source": "postgresql",
            }
        ],
        "suburb_scores": [{"suburb": suburb, "score": combined_score}],
        "map_state": {
            "suburb_filter": [suburb] if suburb else [],
            "heatmap_weights": {"safety": 0.0, "transport": 1.0},
        },
    }


def _format_all_agents_debug(agent_outputs: dict[str, Any]) -> dict[str, Any]:
    """Render all agent outputs together in a consolidated debug response."""
    consolidated = "ALL AGENTS DEBUG OUTPUT:\n\n"

    suburb_scores: list[dict[str, Any]] = []

    for agent_key in ("router", "crime", "sentiment", "gis", "comparator"):
        output = agent_outputs.get(agent_key)
        if output and isinstance(output, dict):
            consolidated += f"{agent_key.upper()}:\n"

            # Handle nested structure: {suburb: result}
            if any(isinstance(v, dict) and ("combined_score" in v or "crime_severity" in v) for v in output.values()):
                for suburb, suburb_output in output.items():
                    consolidated += f"  {suburb}:\n"
                    consolidated += json.dumps(suburb_output, ensure_ascii=True, indent=4).replace("\n", "\n    ") + "\n"
                    if agent_key == "gis" and isinstance(suburb_output, dict):
                        suburb_scores.append({
                            "suburb": suburb,
                            "score": suburb_output.get("combined_score"),
                        })
            else:
                # Handle flat structure
                consolidated += json.dumps(output, ensure_ascii=True, indent=2).replace("\n", "\n  ") + "\n"

            consolidated += "\n"

    # Keep response shape identical to /api/chat contract for frontend compatibility.
    return {
        "answer": consolidated,
        "sources": [
            {
                "text": "All specialist agents debug output (placeholders + implementation status)",
                "suburb": "debug",
                "source": "query_crew",
            }
        ],
        "suburb_scores": suburb_scores,
        "map_state": None,
    }


def _build_context_from_db(suburbs_list: list[str] | None = None) -> dict[str, Any]:
    """Retrieve suburb data from DB for synthesis context.
    
    Returns dict with suburbs data including facilities, transport, OSM scores.
    Filters to requested suburbs if provided, otherwise returns top suburbs.
    """
    with SessionLocal() as session:
        suburbs_query = select(Suburb)
        if suburbs_list:
            suburbs_query = suburbs_query.where(Suburb.suburb.in_(suburbs_list))
        
        suburbs_data = session.scalars(suburbs_query).all()
        
        # Enrich with transport and OSM scores
        transport_data = {
            row.suburb: row
            for row in session.scalars(select(TransportScore)).all()
        }
        osm_data = {
            row.suburb: row
            for row in session.scalars(select(OsmScore)).all()
        }
        
        context = {"suburbs": []}
        for suburb in suburbs_data:
            suburb_context = {
                "name": suburb.suburb,
                "facilities_score": suburb.facilities_score,
                "walkability_score": suburb.walkability_score,
                "liveability_score": suburb.liveability_score,
                "total_facilities": suburb.total_facilities,
                "libraries": suburb.libraries_count,
                "car_share_bays": suburb.car_share_bays_count,
                "mobility_parking": suburb.mobility_parking_count,
                "sports_facilities": suburb.sports_facilities_count,
            }
            
            # Add transport data if available
            if suburb.suburb in transport_data:
                t = transport_data[suburb.suburb]
                suburb_context.update({
                    "bus_stops": t.bus_stops,
                    "train_stations": t.train_stations,
                    "light_rail_stops": t.light_rail_stops,
                    "bike_paths_km": t.bike_paths_km,
                    "avg_commute_min": t.avg_commute_min,
                    "transport_score": t.transport_score,
                })
            
            # Add OSM amenity data if available
            if suburb.suburb in osm_data:
                o = osm_data[suburb.suburb]
                suburb_context.update({
                    "osm_score": o.osm_score,
                    "cafes": o.cafe,
                    "restaurants": o.restaurant,
                    "schools": o.school,
                    "hospitals": o.hospital,
                    "pharmacies": o.pharmacy,
                    "parks": o.park,
                    "playgrounds": o.playground,
                    "sports_centres": o.sports_centre,
                })
            
            context["suburbs"].append(suburb_context)
        
        return context


def _format_evidence_trace_block(agent_outputs: dict[str, Any]) -> str:
    """Render the sentiment agent's evidence_trace as one line per TraceEntry.

    Empty string when no sentiment output is present or when the router
    classified the question as out_of_scope, so the prompt omits the
    section cleanly for non-spatial questions.
    """
    if not isinstance(agent_outputs, dict):
        return ""
    router_output = agent_outputs.get("router")
    if isinstance(router_output, dict):
        categories = router_output.get("categories") or []
        if list(categories) == ["out_of_scope"]:
            return ""
    sentiment = agent_outputs.get("sentiment")
    if not isinstance(sentiment, dict):
        return ""
    lines: list[str] = []
    # sentiment is {suburb: result}; flatten across suburbs for the prompt.
    for suburb, result in sentiment.items():
        if not isinstance(result, dict):
            continue
        for entry in result.get("evidence_trace") or []:
            args = json.dumps(entry.get("arguments", {}), default=str)
            preview = (entry.get("result_preview") or "").replace("\n", " ")
            lines.append(
                f"- step {entry.get('step')} [{suburb}] {entry.get('tool')}({args}) "
                f"-> n={entry.get('result_count')} | {preview}"
            )
    if not lines:
        return ""
    return "\n\nEvidence trace (every retrieval tool call this turn):\n" + "\n".join(lines)


def _build_synthesis_prompt(question: str, context: dict[str, Any], agent_outputs: dict[str, Any] | None = None) -> str:
    """Build the LLM prompt combining question, DB context, and agent outputs.

    Handles both flat (single-suburb per specialist) and nested (multi-suburb per specialist) structures.
    """
    prompt = f"""You are a Sydney liveability expert assistant. Answer the user's question about Sydney suburbs using the provided data.

User Question: {question}

Available Data:
{data_block}

Instructions:
1. Answer based ONLY on the provided data above and the evidence trace below
2. Be specific with numbers and metrics
3. For out-of-scope suburbs, respond: "I don't have data on that suburb yet"
4. If the question has spatial intent (comparing suburbs), suggest top suburbs by liveability
5. Keep answer concise (2-3 sentences max unless asking for comparison)
6. Always cite your data source (facilities, transport, amenities, or quoted Reddit chunk)
7. When the sentiment agent returned `status: "no_data"` for a dimension, say so plainly — do NOT invent a value
8. Cite at least one evidence-trace entry per named-suburb claim about resident sentiment
"""
    weights = context.get("weights")
    if weights:
        prompt += f"\nUser Preference Weights:\n{json.dumps(weights, indent=2)}\n"
    
    # Add agent outputs if available
    if agent_outputs:
        prompt += "\n\nAdditional Specialist Agent Outputs:\n"
        for agent_key, output in agent_outputs.items():
            if agent_key == "router":
                continue
            if output and isinstance(output, dict):
                # Handle nested structure: {suburb: result} for multi-suburb agents
                if any(
                    isinstance(v, dict)
                    and ("combined_score" in v or "evidence_trace" in v)
                    for v in output.values()
                ):
                    prompt += f"\n{agent_key.upper()} (multi-suburb):\n"
                    for suburb, suburb_output in output.items():
                        prompt += f"  {suburb}: {json.dumps(suburb_output, indent=2, default=str)}\n"
                else:
                    # Handle flat structure: direct result
                    prompt += f"\n{agent_key.upper()}:\n{json.dumps(output, indent=2, default=str)}\n"

    prompt += _format_evidence_trace_block(agent_outputs or {})
    return prompt


def _query_synthesiser_impl(payload: dict[str, Any]) -> dict[str, Any]:
    """Internal implementation: synthesize query response.
    
    Handles both flat (single-suburb) and nested (multi-suburb) specialist outputs.
    """
    outputs = payload.get("outputs", {})
    debug_mode = _normalise_debug_mode()
    question = str(payload.get("question", "")).strip()
    router_output = payload.get("router", {})

    if isinstance(router_output, dict) and "out_of_scope" in router_output.get("categories", []):
        return {
            "answer": (
                "This system was designed only to answer questions related to Sydney liveability. "
                "Please ask about Sydney suburbs, safety, transport, amenities, or resident sentiment."
            ),
            "sources": [],
            "suburb_scores": [],
            "map_state": None,
        }

    # Team debug mode:
    # - SYNTHESIS_DEBUG_MODE=gis -> passthrough only GIS output (first suburb if nested)
    # - SYNTHESIS_DEBUG_MODE=all -> passthrough ALL agent outputs consolidated
    # - SYNTHESIS_DEBUG_MODE=off -> standard synthesiser path
    if isinstance(outputs, dict) and debug_mode in {"gis", "all"}:
        if debug_mode == "gis":
            candidate = outputs.get("gis")
            if isinstance(candidate, dict):
                # Handle nested structure: if it's {suburb: result}, take first
                if any(isinstance(v, dict) and "combined_score" in v for v in candidate.values()):
                    first_suburb_result = next(iter(candidate.values()))
                    return _format_debug_passthrough("gis", first_suburb_result)
                else:
                    return _format_debug_passthrough("gis", candidate)
        else:  # debug_mode == "all"
            return _format_all_agents_debug(outputs)

    # Production synthesis: use LLM with DB context
    if not question:
        return {
            "answer": "Please ask a question about Sydney suburbs.",
            "sources": [],
            "suburb_scores": [],
            "map_state": None,
        }

    try:
        # Extract suburbs from nested specialist outputs (for context building)
        suburbs_from_specialists: set[str] = set()
        if isinstance(outputs, dict):
            for _agent_key, output in outputs.items():
                if isinstance(output, dict):
                    if any(isinstance(v, dict) and ("combined_score" in v or "crime_severity" in v) for v in output.values()):
                        suburbs_from_specialists.update(output.keys())
                    elif "suburb" in output:
                        suburbs_from_specialists.add(output["suburb"])

        suburbs_list = list(suburbs_from_specialists) if suburbs_from_specialists else None

        # Build context from DB (facilities, transport, OSM)
        context = _build_context_from_db(suburbs_list)
        context["weights"] = payload.get("weights") or {}
        
        # Build synthesis prompt — thread router_output through agent_outputs
        # so the prompt builder can gate the trace block on router categories.
        combined_outputs: dict[str, Any] = dict(outputs) if isinstance(outputs, dict) else {}
        if isinstance(router_output, dict) and router_output:
            combined_outputs["router"] = router_output
        synthesis_prompt = _build_synthesis_prompt(
            question,
            context,
            agent_outputs=combined_outputs if combined_outputs else None
        )

        # Call LLM using the synthesiser agent configuration.
        llm = get_agent_llm("synthesiser")
        response = llm.call(synthesis_prompt)

        answer = str(response).strip() if response else "Unable to generate response"

        # Build suburb_scores — prefer GIS combined_score, fall back to liveability_score
        gis_output = outputs.get("gis", {}) if isinstance(outputs, dict) else {}
        if isinstance(gis_output, dict) and gis_output:
            if any(isinstance(v, dict) and "combined_score" in v for v in gis_output.values()):
                suburb_scores = [
                    {"suburb": sub_name, "score": sub_data.get("combined_score")}
                    for sub_name, sub_data in gis_output.items()
                    if isinstance(sub_data, dict)
                ]
            elif "combined_score" in gis_output:
                suburb_scores = [{"suburb": gis_output.get("suburb", ""), "score": gis_output.get("combined_score")}]
            else:
                suburb_scores = []
        else:
            suburb_scores = [
                {"suburb": sub.get("name", ""), "score": sub.get("liveability_score")}
                for sub in context.get("suburbs", [])
                if sub.get("liveability_score") is not None
            ]

        # Build sources — always include GIS; add Reddit when available
        main_suburb = context["suburbs"][0]["name"] if context.get("suburbs") else (suburbs_list[0] if suburbs_list else "Sydney")
        sources: list[dict[str, Any]] = [
            {
                "text": "Facilities, transport, and amenity data",
                "suburb": main_suburb,
                "source": "City of Sydney ArcGIS + OSM + Transport API",
            }
        ]
        
        # If no suburbs in context but outputs were analyzed, mention them
        main_suburb = context["suburbs"][0]["name"] if context.get("suburbs") else "Sydney"
        
        # Citations: prefer the sentiment agent's grounded `sources`
        # (drawn from the Reddit vector index this turn). Fall back to
        # the structured-data attribution when no quote was retrieved.
        sources: list[dict[str, Any]] = []
        sentiment_outputs = outputs.get("sentiment") if isinstance(outputs, dict) else None
        if isinstance(sentiment_outputs, dict):
            for suburb_result in sentiment_outputs.values():
                if not isinstance(suburb_result, dict):
                    continue
                for src in suburb_result.get("sources") or []:
                    if isinstance(src, dict):
                        sources.append(src)
        if not sources:
            sources = [
                {
                    "text": "Facilities, transport, and amenity data",
                    "suburb": main_suburb,
                    "source": "City of Sydney ArcGIS + OSM + Transport API",
                }
            ]

        return {
            "answer": answer,
            "sources": sources,
            "suburb_scores": suburb_scores,
            "map_state": None,
        }
    except Exception as e:
        return {
            "answer": f"Error generating response: {str(e)[:100]}",
            "sources": [],
            "suburb_scores": [],
            "map_state": None,
        }



@tool("query_synthesiser_tool")
def query_synthesiser_tool(payload: dict[str, Any]) -> dict[str, Any]:
    """Wrapper tool for CrewAI: synthesize final response."""
    return _query_synthesiser_impl(payload)


synthesiser_agent = Agent(
    role="Query Synthesiser",
    goal="Compose one grounded answer from structured data and specialist outputs.",
    backstory="You merge database context and agent outputs into a concise, cited user response.",
    llm=get_agent_llm("synthesiser"),
    tools=[query_synthesiser_tool],
    verbose=True,
)

synthesiser_task = Task(
    description="Synthesize final answer from DB context and query agent outputs.",
    expected_output="JSON: {answer, sources, suburb_scores, map_state}.",
    agent=synthesiser_agent,
)


def run(input_data: dict[str, Any]) -> dict[str, Any]:
    """Isolated execution helper for query crew finalization.
    
    Input format:
    {
        "question": "user question string",
        "outputs": {
            "gis": {...},  # optional GIS agent output
            "crime": {...},  # optional crime agent output
            "sentiment": {...},  # optional sentiment agent output
            "comparator": {...},  # optional comparator agent output
        }
    }
    """
    return _query_synthesiser_impl(input_data)


if __name__ == "__main__":
    print(run({
        "question": "Tell me about transport in Newtown",
        "outputs": {}
    }))
