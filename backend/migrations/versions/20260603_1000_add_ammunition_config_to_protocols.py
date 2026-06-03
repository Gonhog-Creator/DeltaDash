"""Add ammunition configuration to protocols

Revision ID: 20260603_1000
Revises: 20260603_0929
Create Date: 2026-06-03 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260603_1000'
down_revision = '20260603_0929'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('protocols', sa.Column('ammunition_config', postgresql.JSON(), nullable=True))
    op.add_column('protocols', sa.Column('total_shots', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('protocols', 'total_shots')
    op.drop_column('protocols', 'ammunition_config')
