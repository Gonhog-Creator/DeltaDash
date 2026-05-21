"""add ply_orientations to vest_layers

Revision ID: 20260521_1300
Revises: 20260521_1200
Create Date: 2026-05-21 13:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision = '20260521_1300'
down_revision = '20260521_1200'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add ply_orientations column to vest_layers table
    op.add_column('vest_layers', sa.Column('ply_orientations', JSONB(), nullable=True))


def downgrade() -> None:
    # Drop ply_orientations column
    op.drop_column('vest_layers', 'ply_orientations')
