"""update suburbs schema with sal_code and facility counters

Revision ID: 20260418_0002
Revises: 20260418_0001
Create Date: 2026-04-18 00:10:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260418_0002"
down_revision = "20260418_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("suburbs", sa.Column("sal_code", sa.String(), nullable=True))
    op.add_column("suburbs", sa.Column("car_share_bays_count", sa.Integer(), nullable=True))
    op.add_column("suburbs", sa.Column("libraries_count", sa.Integer(), nullable=True))
    op.add_column("suburbs", sa.Column("mobility_parking_count", sa.Integer(), nullable=True))
    op.add_column("suburbs", sa.Column("sports_facilities_count", sa.Integer(), nullable=True))
    op.add_column("suburbs", sa.Column("playgrounds_count", sa.Integer(), nullable=True))
    op.add_column("suburbs", sa.Column("total_facilities", sa.Integer(), nullable=True))

    op.alter_column("suburbs", "facilities_score", existing_type=sa.Float(), nullable=True)
    op.alter_column("suburbs", "walkability_score", existing_type=sa.Float(), nullable=True)
    op.alter_column("suburbs", "liveability_score", existing_type=sa.Float(), nullable=True)
    op.alter_column("suburbs", "sa4_area", existing_type=sa.String(length=80), nullable=True)

    op.execute("UPDATE suburbs SET sal_code = suburb WHERE sal_code IS NULL")
    op.alter_column("suburbs", "sal_code", existing_type=sa.String(), nullable=False)
    op.execute("ALTER TABLE suburbs DROP CONSTRAINT IF EXISTS suburbs_pkey")
    op.create_primary_key("pk_suburbs_sal_code", "suburbs", ["sal_code"])


def downgrade() -> None:
    op.drop_constraint("pk_suburbs_sal_code", "suburbs", type_="primary")
    op.create_primary_key("suburbs_pkey", "suburbs", ["suburb"])

    op.alter_column("suburbs", "facilities_score", existing_type=sa.Float(), nullable=False)
    op.alter_column("suburbs", "walkability_score", existing_type=sa.Float(), nullable=False)
    op.alter_column("suburbs", "liveability_score", existing_type=sa.Float(), nullable=False)
    op.alter_column("suburbs", "sa4_area", existing_type=sa.String(length=80), nullable=False)

    op.drop_column("suburbs", "total_facilities")
    op.drop_column("suburbs", "playgrounds_count")
    op.drop_column("suburbs", "sports_facilities_count")
    op.drop_column("suburbs", "mobility_parking_count")
    op.drop_column("suburbs", "libraries_count")
    op.drop_column("suburbs", "car_share_bays_count")
    op.drop_column("suburbs", "sal_code")
