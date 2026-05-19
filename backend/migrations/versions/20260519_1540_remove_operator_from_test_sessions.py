"""remove operator from test sessions

Revision ID: 20260519_1540
Revises: 20260519_1230
Create Date: 2026-05-19 15:40:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260519_1540'
down_revision = '20260519_1230'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column('test_sessions', 'operator')


def downgrade() -> None:
    op.add_column('test_sessions', sa.Column('operator', sa.String(), nullable=True))
