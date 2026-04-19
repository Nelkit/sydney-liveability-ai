"""Ingest OSM feature aggregates into PostgreSQL osm_scores table.

Reads: data/processed/osm_data.csv (or JSON, TBD)
Writes: PostgreSQL table `osm_scores`
Owner: assign in team meeting
"""

from __future__ import annotations


def main() -> None:
    """Entrypoint for OSM score ingestion."""
    # TODO(owner): Implement OSM ingestion for amenity counts and score.
    # 1) Read source dataset with pandas (CSV now, JSON fallback if defined).
    # 2) Map columns to OsmScore fields including amenity counters and osm_score.
    # 3) Upsert by suburb using SQLAlchemy session.
    # 4) Keep NULLs for unavailable counters instead of writing dummy zeros.
    # 5) Commit transaction and report inserted/updated row totals.
    pass


if __name__ == "__main__":
    main()
