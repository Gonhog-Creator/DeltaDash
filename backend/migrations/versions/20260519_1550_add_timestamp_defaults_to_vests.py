"""add timestamp defaults to vests

Revision ID: 20260519_1550
Revises: 20260519_1540
Create Date: 2026-05-19 15:50:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260519_1550'
down_revision = '20260519_1540'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add server_default for created_at and updated_at in vests table
    op.alter_column('vests', 'created_at', server_default=sa.text('now()'))
    op.alter_column('vests', 'updated_at', server_default=sa.text('now()'))


def downgrade() -> None:
    # Remove server_default for created_at and updated_at
    op.alter_column('vests', 'created_at', server_default=None)
    op.alter_column('vests', 'updated_at', server_default=None)
