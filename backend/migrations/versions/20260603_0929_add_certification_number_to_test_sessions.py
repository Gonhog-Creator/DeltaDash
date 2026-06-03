"""add certification_number to test sessions

Revision ID: 20260603_0929
Revises: 20260602_1700
Create Date: 2026-06-03 09:29:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260603_0929'
down_revision = '20260602_1700'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('test_sessions', sa.Column('certification_number', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('test_sessions', 'certification_number')
