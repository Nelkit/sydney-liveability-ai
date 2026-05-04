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
import logging
import traceback
from typing import Any

logger = logging.getLogger(__name__)

from crewai import Agent, Task
from crewai.tools import tool
from sqlalchemy import select

from config import get_agent_llm, settings
from db.chromadb import REDDIT_COLLECTION, query_chunks
from db.models import OsmScore, Suburb, TransportScore
from db.postgres import SessionLocal

def _retrieve_chromadb_chunks(
    question: str,
    suburbs_list: list[str] | None = None,
    k_per_collection: int = 5,
) -> list[dict[str, Any]]:
    """Retrieve Reddit semantic chunks with fallback if suburb filter fails."""
    
    print(f"[RAG] Query: {question}")
    print(f"[RAG] Suburbs filter: {suburbs_list}")

    chunks: list[dict[str, Any]] = []

    try:
        if suburbs_list:
            for suburb in suburbs_list:
                results = query_chunks(
                    question,
                    k=k_per_collection,
                    filters={"suburb": _normalise_suburb(suburb)}
                )

                # fallback if nothing found
                if not results:
                    print(f"[RAG] No results for {suburb}, retrying without filter")
                    results = query_chunks(question, k=k_per_collection)

                chunks.extend(results)
        else:
            chunks = query_chunks(question, k=k_per_collection)

    except Exception as e:
        print(f"[RAG ERROR] {e}")

    print(f"[RAG] Retrieved {len(chunks)} chunks")
    return chunks

def _normalise_suburb(s: str) -> str:
    # Reddit/sentiment chunks are ingested with Title Case + spaces in the
    # `suburb` metadata. Lowercasing/snake-casing here returns 0 hits and
    # silently triggers the unfiltered fallback in _retrieve_chromadb_chunks.
    return s.replace("_", " ").replace("-", " ").strip().title()

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
        else:
            suburbs_query = suburbs_query.limit(10)

        suburbs_data = session.scalars(suburbs_query).all()
        target_suburbs = {s.suburb for s in suburbs_data}

        # Enrich with transport and OSM scores — only for suburbs in scope
        transport_data = {
            row.suburb: row
            for row in session.scalars(
                select(TransportScore).where(TransportScore.suburb.in_(target_suburbs))
            ).all()
        }
        osm_data = {
            row.suburb: row
            for row in session.scalars(
                select(OsmScore).where(OsmScore.suburb.in_(target_suburbs))
            ).all()
        }
        
        context = {"suburbs": []}
        for suburb in suburbs_data:
            suburb_context = {
                "name": suburb.suburb,
                "facilities_score": suburb.facilities_score,
                "walkability_score": suburb.walkability_score,
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


def _detect_scenario(suburbs_list: list | None, router_output: dict) -> str:
    categories = router_output.get("categories", []) if isinstance(router_output, dict) else []
    if "out_of_scope" in categories:
        return "out_of_scope"
    if len(suburbs_list or []) > 1 or "comparator" in categories:
        return "comparator"
    return "single"

def _build_synthesis_prompt(
    question: str,
    context: dict[str, Any],
    retrieved_chunks: list[dict] | None = None,
    agent_outputs: dict[str, Any] | None = None,
    router_output: dict | None = None,
    suburbs_list: list | None = None,
) -> str:
    data_block = json.dumps(context, indent=2, default=str)

    rag_block = ""
    if retrieved_chunks:
        rag_lines = []
        for c in retrieved_chunks[:8]:
            suburb = c["metadata"].get("suburb", "unknown")
            text = c["text"][:200].replace("\n", " ")
            rag_lines.append(f"- ({suburb}) {text}")
        rag_block = "\n\nRetrieved Context:\n" + "\n".join(rag_lines)

    if agent_outputs:
        agent_block = "\n\nAdditional Specialist Agent Outputs:\n"
        for agent_key, output in agent_outputs.items():
            if agent_key == "router":
                continue
            if output and isinstance(output, dict):
                # Ranking output — render as a numbered list instead of raw JSON
                if output.get("status") == "ok" and "ranking" in output:
                    field = output.get("field", "value")
                    agent_block += f"\n{agent_key.upper()} RANKING by {field}:\n"
                    for entry in output["ranking"]:
                        rank = entry.get("rank", "?")
                        suburb = entry.get("suburb", "")
                        val = entry.get(field, "")
                        agent_block += f"  {rank}. {suburb}: {val}\n"
                elif any(
                    isinstance(v, dict) and ("combined_score" in v or "evidence_trace" in v)
                    for v in output.values()
                ):
                    agent_block += f"\n{agent_key.upper()} (multi-suburb):\n"
                    for suburb, suburb_output in output.items():
                        agent_block += f"  {suburb}: {json.dumps(suburb_output, indent=2, default=str)}\n"
                else:
                    agent_block += f"\n{agent_key.upper()}:\n{json.dumps(output, indent=2, default=str)}\n"
        agent_block += _format_evidence_trace_block(agent_outputs)
    else:
        agent_block = ""

    weights = context.get("weights")
    weights_block = f"\nUser Preference Weights:\n{json.dumps(weights, indent=2)}\n" if weights else ""

    scenario = _detect_scenario(suburbs_list, router_output or {})
    suburb_name = (suburbs_list[0] if suburbs_list else context.get("suburbs", [{}])[0].get("name", "the suburb"))
    suburbs_csv = ", ".join(suburbs_list) if suburbs_list else suburb_name

    if scenario == "single":
        system = f"""You are the lead urban analyst for Sydney Liveability AI.
Write a SHORT, PUNCHY chat response (3-5 sentences MAX) about {suburb_name} using the data below.

STRUCTURE (use light markdown):
- Open with 1 sentence capturing the suburb's overall character.
- Use **bold** to highlight 1-2 key metrics or standout facts (e.g. "**walkability score of 87**").
- Add a short bullet list (2-3 items MAX) of the most relevant highlights or concerns for the user's question.
- Close with a natural 1-sentence invitation to open the full report for charts, scores, and crime data.
- Format the closing invitation as a Markdown blockquote line starting with ">".

TONE: Conversational, direct, like a knowledgeable local friend.
CRITICAL: No walls of text. No headings (###). Do NOT invent data not present below. The dashboard already has the detail — your job is to make the user WANT to open it."""

    elif scenario == "comparator":
        system = f"""You are the lead urban analyst for Sydney Liveability AI.
The user wants to compare: {suburbs_csv}.
Write a SHORT comparison (4-6 sentences MAX).

STRUCTURE (use light markdown):
- Open with 1 sentence stating which suburb "wins" overall based on the data, OR that they suit different lifestyles.
- Use **bold** to name the single biggest differentiator (e.g. "**safety**", "**transport score**").
- Add a short bullet list (one line per suburb) summarising each suburb's strongest point.
- Close with an invitation to open the Compare view for the full side-by-side breakdown.
- Format the closing invitation as a Markdown blockquote line starting with ">".

TONE: Decisive, direct, helpful.
CRITICAL: No tables. No ### headings. Do NOT invent data not present below. The Compare dashboard already exists — your message is the teaser."""

    else:  # fallback single
        system = f"""You are a Sydney liveability expert assistant. Answer the user's question about Sydney suburbs using the provided data.
Be specific with numbers and metrics. Keep the answer concise (2-3 sentences max unless asking for comparison).
Always cite your data source. Use **bold** for key metrics. Do NOT invent data."""

    prompt = f"""{system}

User question: {question}
{weights_block}
Available Data:
{data_block}
{agent_block}
{rag_block}"""

    return prompt


def _query_synthesiser_impl(payload: dict[str, Any]) -> dict[str, Any]:
    """Internal implementation: synthesize query response.
    
    Handles both flat (single-suburb) and nested (multi-suburb) specialist outputs.
    """
    outputs = payload.get("outputs", {})
    debug_mode = _normalise_debug_mode()
    question = str(payload.get("question", "")).strip()
    router_output = payload.get("router", {})
    
    # Extract suburbs FIRST
    suburbs_from_specialists: set[str] = set()

    if isinstance(outputs, dict):
        for _agent_key, output in outputs.items():
            if isinstance(output, dict):
                if any(
                    isinstance(v, dict) and ("combined_score" in v or "crime_severity" in v)
                    for v in output.values()
                ):
                    suburbs_from_specialists.update(output.keys())
                elif "suburb" in output:
                    suburbs_from_specialists.add(output["suburb"])

    # Also accept suburbs passed directly from the crew (e.g. ranking mode)
    crew_suburbs = payload.get("suburbs") or []
    suburbs_list = list(suburbs_from_specialists or crew_suburbs) or None

    # THEN retrieve chunks
    retrieved_chunks = _retrieve_chromadb_chunks(question, suburbs_list)
    
    if isinstance(router_output, dict) and "out_of_scope" in router_output.get("categories", []):
        return {
            "answer": (
                "I specialise in Sydney suburbs — try asking about safety, transport, "
                "amenities, or how two suburbs compare.\n\n"
                "For example:\n"
                "- *Is Newtown safe at night?*\n"
                "- *Compare Glebe and Surry Hills*\n"
                "- *Best suburb for families near the CBD?*"
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
            agent_outputs=combined_outputs if combined_outputs else None,
            retrieved_chunks=retrieved_chunks,
            router_output=router_output,
            suburbs_list=suburbs_list,
        )

        # Call LLM using the synthesiser agent configuration.
        llm = get_agent_llm("synthesiser")
        response = llm.call(synthesis_prompt)

        answer = str(response).strip() if response else "Unable to generate response"

        # Build suburb_scores — prefer GIS combined_score, fall back to
        # computed liveability score using the same formula as /api/civic.
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
            from core.scoring import compute_liveability_scores
            user_weights = context.get("weights") or {}
            liveability_weights = {
                "safety": float(user_weights.get("safety", 0.25)),
                "transport": float(user_weights.get("transport", 0.25)),
                "lifestyle": float(user_weights.get("lifestyle", 0.25)),
                "affordability": float(user_weights.get("affordability", 0.25)),
                "nightlife": float(user_weights.get("nightlife", 0.0)),
                "proximity": float(user_weights.get("proximity", 0.0)),
            }
            scored = compute_liveability_scores(
                weights=liveability_weights,
                suburb_filter=suburbs_list or None,
            )
            suburb_scores = [
                {"suburb": name, "score": data["liveability"]}
                for name, data in scored.items()
            ]

        # Build sources from every agent that ran this turn.
        # Each agent may return a `sources` list with dicts containing a
        # `source` key that maps to a SourceKind string the frontend knows.
        AGENT_DEFAULT_SOURCE: dict[str, str] = {
            "sentiment": "reddit",
            "crime": "bocsar",
            "gis": "arcgis",
            "transport": "tfnsw",
        }
        sources: list[dict[str, Any]] = []
        seen_kinds: set[str] = set()

        if isinstance(outputs, dict):
            for agent_key, agent_out in outputs.items():
                if not isinstance(agent_out, dict):
                    continue
                # Nested structure: {suburb: result_dict}
                results = (
                    list(agent_out.values())
                    if any(isinstance(v, dict) for v in agent_out.values())
                    else [agent_out]
                )
                for result in results:
                    if not isinstance(result, dict):
                        continue
                    for src in result.get("sources") or []:
                        if isinstance(src, dict) and src.get("source"):
                            sources.append(src)
                            seen_kinds.add(str(src.get("source")))

                # If agent ran but produced no explicit sources, add a default badge
                default_kind = AGENT_DEFAULT_SOURCE.get(agent_key)
                if default_kind and default_kind not in seen_kinds:
                    main_suburb = (
                        context["suburbs"][0]["name"]
                        if context.get("suburbs")
                        else (suburbs_list[0] if suburbs_list else "Sydney")
                    )
                    sources.append({"source": default_kind, "suburb": main_suburb})
                    seen_kinds.add(default_kind)

        return {
            "answer": answer,
            "sources": sources,
            "suburb_scores": suburb_scores,
            "map_state": None,
        }
    except Exception as e:
        logger.error("Synthesiser failed: %s\n%s", e, traceback.format_exc())
        return {
            "answer": f"Error generating response: {e}",
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
