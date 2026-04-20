"""create initial tables

Revision ID: 20260418_0001
Revises:
Create Date: 2026-04-18 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260418_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "suburbs",
        sa.Column("suburb", sa.String(length=80), nullable=False),
        sa.Column("facilities_score", sa.Float(), nullable=False),
        sa.Column("walkability_score", sa.Float(), nullable=False),
        sa.Column("liveability_score", sa.Float(), nullable=False),
        sa.Column("sa4_area", sa.String(length=80), nullable=False),
        sa.PrimaryKeyConstraint("suburb"),
    )

    op.create_table(
        "bocsar",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("suburb", sa.String(length=80), nullable=False),
        sa.Column("crime_type", sa.String(length=120), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("incident_count", sa.Integer(), nullable=False),
        sa.Column("sa4_area", sa.String(length=80), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "sentiment",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("suburb", sa.String(length=80), nullable=False),
        sa.Column("topic", sa.String(length=80), nullable=False),
        sa.Column("vader_score", sa.Float(), nullable=False),
        sa.Column("textblob_score", sa.Float(), nullable=False),
        sa.Column("subjectivity", sa.Float(), nullable=False),
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "topic_weights",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("suburb", sa.String(length=80), nullable=False),
        sa.Column("topic_label", sa.String(length=80), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False),
        sa.Column("top_terms", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("topic_weights")
    op.drop_table("sentiment")
    op.drop_table("bocsar")
    op.drop_table("suburbs")
