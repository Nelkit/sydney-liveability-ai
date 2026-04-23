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
                    "gyms": o.gym,
                    "schools": o.school,
                    "hospitals": o.hospital,
                    "pharmacies": o.pharmacy,
                    "parks": o.park,
                    "playgrounds": o.playground,
                    "sports_centres": o.sports_centre,
                })
            
            context["suburbs"].append(suburb_context)
        
        return context


def _build_synthesis_prompt(
    question: str,
    context: dict[str, Any],
    agent_outputs: dict[str, Any] | None = None,
    reddit_by_suburb: dict[str, Any] | None = None,
    chromadb_chunks: list[dict[str, Any]] | None = None,
) -> str:
    """Build the LLM prompt combining question, DB context, agent outputs, and Reddit data."""
    is_general = not any(
        kw in question.lower()
        for kw in ("park", "transport", "facilities", "gym", "cafe", "walk",
                   "amenities", "safe", "crime", "feel", "vibe", "community",
                   "compare", "versus", "vs", "better")
    )

    if is_general:
        format_instruction = (
            "Write 2-3 paragraphs using ONLY the GIS & Facilities data as your primary source. "
            "Cover: facilities score, key amenities counts (cafes, restaurants, parks, schools, etc.), OSM score, and combined liveability score. "
            "At the very end, add ONE closing sentence (max 20 words) mentioning what residents value most, using the Reddit top aspect — no scores, no paragraph. "
            "STRICT RULES: Do NOT start with Reddit. Do NOT write a Reddit paragraph. Do NOT list Reddit aspect scores. "
            "Do NOT use bullet lists."
        )
    else:
        format_instruction = (
            "Answer in 2-3 focused sentences addressing exactly what was asked. "
            "Be specific with numbers. Do not list unrelated data."
        )

    sections: list[str] = []

    # GIS / facilities data
    db_suburbs = context.get("suburbs", [])
    if db_suburbs:
        sections.append(f"GIS & Facilities Data:\n{json.dumps(db_suburbs, indent=2)}")

    # Agent specialist outputs
    if agent_outputs:
        for agent_key, output in agent_outputs.items():
            if not output or not isinstance(output, dict):
                continue
            if any(isinstance(v, dict) and "combined_score" in v for v in output.values()):
                lines = [f"{agent_key.upper()} data (per suburb):"]
                for sub, sub_out in output.items():
                    lines.append(f"  {sub}: {json.dumps(sub_out, indent=2)}")
                sections.append("\n".join(lines))
            elif "pending" not in json.dumps(output):
                sections.append(f"{agent_key.upper()} data:\n{json.dumps(output, indent=2)}")

    # Reddit sentiment — secondary context, top aspect only
    if reddit_by_suburb:
        reddit_lines = ["Reddit Community Sentiment (secondary context — use sparingly):"]
        for sub, rdata in reddit_by_suburb.items():
            if not rdata:
                continue
            aspects = rdata.get("aspects", {})
            scored = [(k, v.get("score", 0)) for k, v in aspects.items() if v.get("mentions", 0) > 0]
            if scored:
                top = max(scored, key=lambda x: x[1])
                reddit_lines.append(f"  {sub}: residents rate '{top[0].replace('_', ' ')}' highest ({top[1]:.2f}).")
            else:
                reddit_lines.append(f"  {sub}: limited community data available.")
        sections.append("\n".join(reddit_lines))

    # ChromaDB community chunks — resident quotes from PDFs and Reddit
    if chromadb_chunks:
        lines = ["Relevant community context (ChromaDB):"]
        for i, chunk in enumerate(chromadb_chunks, 1):
            text = chunk["text"][:400]
            meta = chunk.get("metadata", {})
            source = meta.get("source", "unknown")
            suburb = meta.get("suburb", "unknown")
            lines.append(f'Chunk {i} [source: {source} · suburb: {suburb}]:\n"{text}"')
        sections.append("\n".join(lines))

    weights = context.get("weights") or {}
    if weights:
        sections.append(f"User Preference Weights:\n{json.dumps(weights, indent=2)}")

    data_block = "\n\n".join(sections) if sections else "No data available."

    return f"""You are a Sydney liveability expert assistant. Answer the user's question using only the data provided below.

User Question: {question}

Available Data:
{data_block}

Instructions:
- {format_instruction}
- Primary source is always GIS & Facilities data. Community context (ChromaDB) provides resident quotes to support claims.
- Use only data provided above. Do not invent figures.
- For suburbs with no data, say "I don't have data on that suburb yet."
- Cite ChromaDB chunks naturally when they support a claim — mention the source type (pdf or reddit).
"""


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

        # Load Reddit sentiment for mentioned suburbs
        reddit_by_suburb: dict[str, Any] = {}
        for sub in (suburbs_list or []):
            rdata = _get_reddit_context(sub)
            if rdata:
                reddit_by_suburb[sub] = rdata

        # Retrieve semantically relevant chunks from ChromaDB
        chromadb_chunks = _retrieve_chromadb_chunks(question, suburbs_list)

        # Build synthesis prompt including Reddit data and ChromaDB chunks
        synthesis_prompt = _build_synthesis_prompt(
            question,
            context,
            agent_outputs=outputs if isinstance(outputs, dict) and outputs else None,
            reddit_by_suburb=reddit_by_suburb if reddit_by_suburb else None,
            chromadb_chunks=chromadb_chunks if chromadb_chunks else None,
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
        for sub, rdata in reddit_by_suburb.items():
            post_count = rdata.get("post_count", 0)
            sources.append({
                "text": f"Reddit community analysis ({post_count} posts)",
                "suburb": sub,
                "source": "Reddit r/sydney",
            })

        for chunk in chromadb_chunks:
            meta = chunk.get("metadata", {})
            sources.append({
                "text": chunk["text"][:120],
                "suburb": meta.get("suburb", ""),
                "source": meta.get("source", "chromadb"),
            })

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
