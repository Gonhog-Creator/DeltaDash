"""add_training_avg_error_to_model_runs (no-op - duplicate)

Revision ID: 3f093c3babbd
Revises: 20260608_1320
Create Date: 2026-06-08 14:19:12.378985

This migration is a duplicate of 20260608_1130 and is now a no-op.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3f093c3babbd'
down_revision = '20260608_1320'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # No-op - column already added by 20260608_1130
    pass


def downgrade() -> None:
    # No-op - column already added by 20260608_1130
    pass
