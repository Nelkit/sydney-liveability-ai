---
name: ingest-script
description: >
    Standard workflow to create backend/scripts/ingest_*.py for Sydney Liveability Explorer.
  Trigger: Use when creating or updating ingestion scripts for PostgreSQL tables.
license: Apache-2.0
metadata:
  author: gentleman-programming
  version: "1.0"
---

## Purpose
Create consistent ingestion scripts for backend data pipelines using Python, SQLAlchemy, and PostgreSQL, with safe upsert behavior and clear ownership metadata.

## Scope
- Stack: Python 3.11, FastAPI, SQLAlchemy, Alembic, PostgreSQL (Supabase)
- Models source: backend/db/models.py
- Session source: backend/db/postgres.py via get_session()
- No LLM calls in ingestion scripts

## When To Use
- Creating a new backend/scripts/ingest_<name>.py file
- Extending an existing ingest script with new fields
- Refactoring ingest scripts to follow a shared team pattern

## Required Process
1. Confirm target model/table exists in backend/db/models.py.
2. If schema changed, create migration and run db upgrade before ingest.
3. Implement ingest script with module docstring (owner, reads, writes, run command, dependencies).
4. Load input data from data/processed or agreed source path.
5. Use upsert pattern per record; never delete-and-reinsert.
6. Commit once at the end of the session.
7. Print concise summary with number of written rows.

## Decision Rules
- If table is new: run migration first, then ingest.
- If row key exists: update mutable fields only.
- If row key does not exist: create row and set all required fields.
- If input row is malformed: skip and log with enough context.
- If script exceeds 150 lines: split parsing/normalization into helper functions.

## Quality Gates
- MUST use get_session() context manager.
- MUST avoid hardcoded credentials.
- MUST perform a single session.commit() at end (unless explicit chunked transactions are required).
- MUST keep idempotent behavior: rerun should not duplicate rows.
- MUST include clear errors for missing files and missing required columns.

## Script Template
```python
"""
backend/scripts/ingest_<name>.py
-------------------------
Owner: <team member name>

Reads: <describe input file and location>
Writes: <describe target PostgreSQL table(s)>

Run:
    python -m scripts.ingest_<name>

Depends on:
    - <input file> must exist
    - make db-upgrade must have been run
"""

from db.postgres import get_session
from db.models import <ModelName>


def main() -> None:
    # 1. Load input data
    # TODO: load from data/processed/<file>

    with get_session() as session:
        for item in data:
            # 2. Upsert lookup
            row = session.query(<ModelName>).filter_by(
                <pk_field>=item["<pk_field>"]
            ).first()

            if not row:
                row = <ModelName>(<pk_field>=item["<pk_field>"])
                session.add(row)

            # 3. Assign fields
            row.<field> = item["<field>"]

        session.commit()
        print(f"Done. Wrote {len(data)} rows to <table_name>.")


if __name__ == "__main__":
    main()
```

## Migration Commands
```bash
alembic revision --autogenerate -m "add <field> to <table>"
make db-upgrade
```

## Collaboration Conventions
- Add owner name in docstring for accountability.
- Keep logs deterministic and review-friendly.
- In PR description, include:
  - Input file(s)
  - Target table(s)
  - Number of ingested rows
  - How idempotency was validated

## Prompt Starters
- "Create backend/scripts/ingest_transport.py using ingest-script skill"
- "Refactor backend/scripts/ingest_reddit.py to satisfy ingest-script quality gates"
- "Add new field mapping to backend/scripts/ingest_osm.py following ingest-script"
