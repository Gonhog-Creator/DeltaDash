"""add force_newtons_5cm, elongation_error, and force_error to materials

Revision ID: 20260522_1000
Revises: 20260522_0958
Create Date: 2026-05-22 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260522_1000'
down_revision = 'a4e319b3bf94'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new columns to materials table
    op.add_column('materials', sa.Column('force_newtons_5cm', sa.Numeric(10, 2), nullable=True))
    op.add_column('materials', sa.Column('elongation_error', sa.Numeric(10, 2), nullable=True))
    op.add_column('materials', sa.Column('force_error', sa.Numeric(10, 2), nullable=True))


def downgrade() -> None:
    # Drop the new columns
    op.drop_column('materials', 'force_error')
    op.drop_column('materials', 'elongation_error')
    op.drop_column('materials', 'force_newtons_5cm')
