"""add gtfs columns to transport_scores

Revision ID: c74a4b2eb281
Revises: 20260419_0005
Create Date: 2026-04-28 01:44:36.310953
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa



# revision identifiers, used by Alembic.
revision = '20260428_0006'
down_revision = '20260419_0005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('transport_scores', sa.Column('avg_services_per_hour', sa.Float(), nullable=True))
    op.add_column('transport_scores', sa.Column('stop_count', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('transport_scores', 'stop_count')
    op.drop_column('transport_scores', 'avg_services_per_hour')