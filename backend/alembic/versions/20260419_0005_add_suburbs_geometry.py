"""add geometry column and spatial index to suburbs

Revision ID: 20260419_0005
Revises: 20260419_0004
Create Date: 2026-04-19 01:25:00
"""

from __future__ import annotations

from alembic import op


revision = "20260419_0005"
down_revision = "20260419_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.execute(
        """
        ALTER TABLE suburbs
        ADD COLUMN IF NOT EXISTS geometry geometry(MultiPolygon, 4326)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_suburbs_geometry
        ON suburbs USING GIST (geometry)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_suburbs_geometry")
    op.execute("ALTER TABLE suburbs DROP COLUMN IF EXISTS geometry")
