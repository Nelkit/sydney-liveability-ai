"""Ingest cleaned BOCSAR CSV into PostgreSQL bocsar table.

Reads: data/processed/bocsar_clean.csv
Writes: PostgreSQL table `bocsar`
Owner: assign in team meeting
"""

from __future__ import annotations


def main() -> None:
    """Entrypoint for BOCSAR structured ingestion."""
    # TODO(owner): Implement CSV to PostgreSQL upsert for bocsar.
    # 1) Read data/processed/bocsar_clean.csv with pandas.
    # 2) Map CSV columns to bocsar ORM fields: suburb, crime_type, year, incident_count, sa4_area.
    # 3) Open a SQLAlchemy session from db.postgres.SessionLocal.
    # 4) Upsert each row by composite key (suburb, crime_type, year).
    # 5) Commit in batches and rollback on errors with clear logging.
    pass


if __name__ == "__main__":
    main()
