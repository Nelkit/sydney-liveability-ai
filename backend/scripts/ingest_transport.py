"""Ingest transport accessibility metrics into PostgreSQL transport_scores.

Reads: data/processed/transport_data.csv (TBD)
Writes: PostgreSQL table `transport_scores`
Owner: assign in team meeting
"""

from __future__ import annotations


def main() -> None:
    """Entrypoint for transport score ingestion."""
    # TODO(owner): Implement transport score ingestion pipeline.
    # 1) Read data/processed/transport_data.csv with pandas.
    # 2) Map dataset columns to TransportScore fields.
    # 3) Upsert rows by suburb through SQLAlchemy session.
    # 4) Preserve numeric precision for bike_paths_km and avg_commute_min.
    # 5) Set source explicitly (osm | gtfs | tfnsw) from the source dataset.
    # 6) Commit in transaction and emit row-level validation warnings.
    pass


if __name__ == "__main__":
    main()
