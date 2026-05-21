"""add ply_count to materials

Revision ID: 20260521_1200
Revises: 20260521_1100
Create Date: 2026-05-21 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260521_1200'
down_revision = '20260521_1100'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add ply_count column to materials table
    op.add_column('materials', sa.Column('ply_count', sa.Integer(), nullable=True))


def downgrade() -> None:
    # Drop ply_count column
    op.drop_column('materials', 'ply_count')
