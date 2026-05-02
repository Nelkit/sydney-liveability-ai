"""drop unused sentiment and topic_weights tables

Revision ID: 20260502_0008
Revises: 20260502_0007
Create Date: 2026-05-02
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = '20260502_0008'
down_revision = '20260502_0007'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table('topic_weights')
    op.drop_table('sentiment')


def downgrade() -> None:
    op.create_table(
        'sentiment',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('suburb', sa.String(length=80), nullable=False),
        sa.Column('topic', sa.String(length=80), nullable=False),
        sa.Column('vader_score', sa.Float(), nullable=False),
        sa.Column('textblob_score', sa.Float(), nullable=False),
        sa.Column('subjectivity', sa.Float(), nullable=False),
        sa.Column('source', sa.String(length=80), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'topic_weights',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('suburb', sa.String(length=80), nullable=False),
        sa.Column('topic_label', sa.String(length=80), nullable=False),
        sa.Column('weight', sa.Float(), nullable=False),
        sa.Column('top_terms', sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
