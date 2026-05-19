"""add timestamp defaults to shot_data

Revision ID: 20260519_1600
Revises: 20260519_1550
Create Date: 2026-05-19 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260519_1600'
down_revision = '20260519_1550'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add server_default for created_at in shot_data table
    op.alter_column('shot_data', 'created_at', server_default=sa.text('now()'))


def downgrade() -> None:
    # Remove server_default for created_at
    op.alter_column('shot_data', 'created_at', server_default=None)
