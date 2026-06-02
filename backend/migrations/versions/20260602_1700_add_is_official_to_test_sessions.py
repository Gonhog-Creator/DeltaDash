"""add is_official to test sessions

Revision ID: 20260602_1700
Revises: 20260602_1427
Create Date: 2026-06-02 17:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260602_1700'
down_revision = '20260602_1427'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('test_sessions', sa.Column('is_official', sa.Boolean(), nullable=False, server_default='false'))


def downgrade() -> None:
    op.drop_column('test_sessions', 'is_official')
