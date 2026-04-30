"""Ingest cleaned BOCSAR CSV into PostgreSQL bocsar table.

Reads: data/processed/bocsar_clean.csv
Writes: PostgreSQL table `bocsar`
Owner: Amanda
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from db.models import Bocsar
from db.postgres import SessionLocal


def main() -> None:
    """Entrypoint for BOCSAR structured ingestion."""

    # 1) Read CSV
    csv_path = Path(__file__).resolve().parents[2] / "data/processed/bocsar_clean.csv"
    df = pd.read_csv(csv_path, keep_default_na=False)
    print(f"Loaded {len(df)} rows from {csv_path}")

    # 2) Open session and upsert rows
    session = SessionLocal()
    try:
        count = 0
        for _, row in df.iterrows():
            record = Bocsar(
                suburb=row["suburb"],
                crime_type=row["crime_type"],
                year=int(str(row["year"]).split("-")[0]),
                incident_count=round(row["incident_count"]),
                sa4_area=row["sa4_area"],
            )
            session.add(record)
            count += 1

        session.commit()
        print(f"Successfully inserted {count} rows into bocsar table.")

    except Exception as e:
        session.rollback()
        print(f"Error: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()