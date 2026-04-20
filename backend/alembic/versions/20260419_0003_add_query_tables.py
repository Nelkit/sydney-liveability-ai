"""add sentiment, narrative, osm, and transport query tables

Revision ID: 20260419_0003
Revises: 20260418_0002
Create Date: 2026-04-19 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260419_0003"
down_revision = "20260418_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sentiment_scores",
        sa.Column("suburb", sa.String(), nullable=False),
        sa.Column("aspect", sa.String(), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("mentions", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("suburb", "aspect"),
    )

    op.create_table(
        "emotion_profiles",
        sa.Column("suburb", sa.String(), nullable=False),
        sa.Column("joy", sa.Float(), nullable=True),
        sa.Column("surprise", sa.Float(), nullable=True),
        sa.Column("neutral", sa.Float(), nullable=True),
        sa.Column("sadness", sa.Float(), nullable=True),
        sa.Column("anger", sa.Float(), nullable=True),
        sa.Column("fear", sa.Float(), nullable=True),
        sa.Column("disgust", sa.Float(), nullable=True),
        sa.Column("post_count", sa.Integer(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("suburb"),
    )

    op.create_table(
        "suburb_narratives",
        sa.Column("suburb", sa.String(), nullable=False),
        sa.Column("narrative", sa.Text(), nullable=True),
        sa.Column("sources", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("suburb"),
    )

    op.create_table(
        "osm_scores",
        sa.Column("suburb", sa.String(), nullable=False),
        sa.Column("osm_score", sa.Float(), nullable=True),
        sa.Column("cafe", sa.Integer(), nullable=True),
        sa.Column("restaurant", sa.Integer(), nullable=True),
        sa.Column("gym", sa.Integer(), nullable=True),
        sa.Column("school", sa.Integer(), nullable=True),
        sa.Column("hospital", sa.Integer(), nullable=True),
        sa.Column("pharmacy", sa.Integer(), nullable=True),
        sa.Column("library", sa.Integer(), nullable=True),
        sa.Column("park", sa.Integer(), nullable=True),
        sa.Column("playground", sa.Integer(), nullable=True),
        sa.Column("sports_centre", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("suburb"),
    )

    op.create_table(
        "transport_scores",
        sa.Column("suburb", sa.String(), nullable=False),
        sa.Column("bus_stops", sa.Integer(), nullable=True),
        sa.Column("train_stations", sa.Integer(), nullable=True),
        sa.Column("light_rail_stops", sa.Integer(), nullable=True),
        sa.Column("bike_paths_km", sa.Float(), nullable=True),
        sa.Column("avg_commute_min", sa.Float(), nullable=True),
        sa.Column("transport_score", sa.Float(), nullable=True),
        sa.Column("source", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("suburb"),
    )


def downgrade() -> None:
    op.drop_table("transport_scores")
    op.drop_table("osm_scores")
    op.drop_table("suburb_narratives")
    op.drop_table("emotion_profiles")
    op.drop_table("sentiment_scores")
