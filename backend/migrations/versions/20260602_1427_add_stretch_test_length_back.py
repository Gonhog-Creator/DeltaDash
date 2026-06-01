"""add stretch_test_length back

Revision ID: 20260602_1427
Revises: 20260602_1149
Create Date: 2026-06-02 14:27:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260602_1427'
down_revision = '20260602_1149'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('materials', sa.Column('stretch_test_length', sa.String(10), nullable=True))


def downgrade() -> None:
    op.drop_column('materials', 'stretch_test_length')
