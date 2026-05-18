"""drop sa4_area from suburbs table

Revision ID: 20260502_0009
Revises: 20260502_0008
Create Date: 2026-05-02
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = '20260502_0009'
down_revision = '20260502_0008'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column('suburbs', 'sa4_area')


def downgrade() -> None:
    op.add_column('suburbs', sa.Column('sa4_area', sa.String(), nullable=True))
