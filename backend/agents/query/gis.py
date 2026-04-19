"""GIS specialist that combines facilities, OSM, and transport signals.

Inputs: suburb name
Outputs: official_facilities, osm_amenities, transport, combined_score
Owner: Nelkit Chavez, Luis Robinson, Padmasri Srinivas
"""

from __future__ import annotations

from typing import Any

from crewai import Agent, Task
from crewai.tools import tool
from sqlalchemy import select

from config import get_agent_llm
from db.models import Suburb, OsmScore, TransportScore
from db.postgres import SessionLocal


# TODO(Luis/Padmasri): Once `ingest_osm.py` and `ingest_transport.py` are finished,
# review this agent against their final ingestion outputs, adapt the query/mapping logic
# if needed, and confirm the combined GIS score still works end-to-end.

def _query_gis_impl(suburb: str) -> dict[str, Any]:
    """Internal implementation: query three tables and return combined GIS output."""
    suburb = suburb.strip()
    
    with SessionLocal() as session:
        # Query suburbs table for facilities and facilities_score
        suburb_row = session.scalar(
            select(Suburb).where(Suburb.suburb == suburb)
        )
        
        # Query OSM scores
        osm_row = session.scalar(
            select(OsmScore).where(OsmScore.suburb == suburb)
        )
        
        # Query transport scores
        transport_row = session.scalar(
            select(TransportScore).where(TransportScore.suburb == suburb)
        )
    
    # Extract facilities data
    official_facilities = {
        "car_share_bays_count": suburb_row.car_share_bays_count if suburb_row else None,
        "libraries_count": suburb_row.libraries_count if suburb_row else None,
        "mobility_parking_count": suburb_row.mobility_parking_count if suburb_row else None,
        "sports_facilities_count": suburb_row.sports_facilities_count if suburb_row else None,
        "total_facilities": suburb_row.total_facilities if suburb_row else None,
        "facilities_score": suburb_row.facilities_score if suburb_row else None,
    }
    
    # TODO(Luis): Populate the amenities values form postgres once `ingest_osm.py` is done. 
    # For now, we return None for all amenities and a dummy osm_score.
    # Extract OSM amenities
    osm_amenities = {
        "cafe": osm_row.cafe if osm_row else None,
        "restaurant": osm_row.restaurant if osm_row else None,
        "gym": osm_row.gym if osm_row else None,
        "school": osm_row.school if osm_row else None,
        "hospital": osm_row.hospital if osm_row else None,
        "pharmacy": osm_row.pharmacy if osm_row else None,
        "library": osm_row.library if osm_row else None,
        "park": osm_row.park if osm_row else None,
        "playground": osm_row.playground if osm_row else None,
        "sports_centre": osm_row.sports_centre if osm_row else None,
        "osm_score": osm_row.osm_score if osm_row else None,
    }

    # TODO(Padmasri): Populate the transport values form postgres once `ingest_transport.py` is done.
    # For now, we return None for all amenities and a dummy osm_score.
    # Extract transport details
    transport = {
        "bus_stops": transport_row.bus_stops if transport_row else None,
        "train_stations": transport_row.train_stations if transport_row else None,
        "light_rail_stops": transport_row.light_rail_stops if transport_row else None,
        "bike_paths_km": transport_row.bike_paths_km if transport_row else None,
        "avg_commute_min": transport_row.avg_commute_min if transport_row else None,
        "transport_score": transport_row.transport_score if transport_row else None,
    }
    
    # Compute combined score: 35% facilities + 35% osm + 30% transport
    facilities_contrib = 0.0
    osm_contrib = 0.0
    transport_contrib = 0.0
    
    if suburb_row and suburb_row.facilities_score is not None:
        facilities_contrib = (suburb_row.facilities_score / 100.0) * 0.35
    
    if osm_row and osm_row.osm_score is not None:
        osm_contrib = osm_row.osm_score * 0.35
    
    if transport_row and transport_row.transport_score is not None:
        transport_contrib = (transport_row.transport_score / 100.0) * 0.30
    
    combined_score = facilities_contrib + osm_contrib + transport_contrib
    
    return {
        "suburb": suburb,
        "official_facilities": official_facilities,
        "osm_amenities": osm_amenities,
        "transport": transport,
        "combined_score": round(combined_score, 3),
    }


@tool("query_gis_tool")
def query_gis_tool(suburb: str) -> dict[str, Any]:
    """Wrapper tool for CrewAI: query GIS data (facilities, OSM, transport)."""
    return _query_gis_impl(suburb)


gis_agent = Agent(
    role="Query GIS Analyst",
    goal="Explain suburb amenity and transport strength from structured GIS sources.",
    backstory="You merge official facilities, OSM amenities, and transport access signals.",
    llm=get_agent_llm("gis"),
    tools=[query_gis_tool],
    verbose=True,
)

gis_task = Task(
    description="Assemble GIS evidence for one suburb from three PostgreSQL tables.",
    expected_output="JSON: {suburb, official_facilities, osm_amenities, transport, combined_score}.",
    agent=gis_agent,
)

def run(input_data: dict[str, Any]) -> dict[str, Any]:
    """Isolated execution helper for query crew routing."""
    return _query_gis_impl(suburb=str(input_data.get("suburb", "")))


if __name__ == "__main__":
    print(run({"suburb": "Surry Hills"}))
