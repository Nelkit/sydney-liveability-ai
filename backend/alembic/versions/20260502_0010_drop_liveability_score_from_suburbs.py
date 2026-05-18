"""drop liveability_score from suburbs table

Revision ID: 20260502_0010
Revises: 20260502_0009
Create Date: 2026-05-02
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = '20260502_0010'
down_revision = '20260502_0009'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column('suburbs', 'liveability_score')


def downgrade() -> None:
    op.add_column('suburbs', sa.Column('liveability_score', sa.Float(), nullable=True))
