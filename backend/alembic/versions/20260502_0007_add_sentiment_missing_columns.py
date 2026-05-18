"""add sentiment missing columns

Revision ID: 20260502_0007
Revises: 20260428_0006
Create Date: 2026-05-02
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260502_0007'
down_revision = '20260428_0006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('sentiment_scores', sa.Column('confidence', sa.Float(), nullable=True))
    op.add_column('sentiment_scores', sa.Column('coverage', sa.String(), nullable=True))
    op.add_column('sentiment_scores', sa.Column('source', sa.String(), nullable=True))

    op.add_column('emotion_profiles', sa.Column('confidence', sa.Float(), nullable=True))
    op.add_column('emotion_profiles', sa.Column('confidence_tier', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('emotion_profiles', 'confidence_tier')
    op.drop_column('emotion_profiles', 'confidence')

    op.drop_column('sentiment_scores', 'source')
    op.drop_column('sentiment_scores', 'coverage')
    op.drop_column('sentiment_scores', 'confidence')
