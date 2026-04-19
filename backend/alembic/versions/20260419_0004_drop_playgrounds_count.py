"""drop playgrounds_count from suburbs

Revision ID: 20260419_0004
Revises: 20260419_0003
Create Date: 2026-04-19 00:20:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260419_0004"
down_revision = "20260419_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("suburbs", "playgrounds_count")


def downgrade() -> None:
    op.add_column("suburbs", sa.Column("playgrounds_count", sa.Integer(), nullable=True))
