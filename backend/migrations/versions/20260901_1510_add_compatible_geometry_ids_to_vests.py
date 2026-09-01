"""add_compatible_geometry_ids_to_vests

Revision ID: a1b2c3d4e5f6
Revises: 9e1f63785a9c
Create Date: 2026-09-01 15:10:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON


# revision identifiers, used by Alembic.
revision = 'f1e2d3c4b5a6'
down_revision = '9e1f63785a9c'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('vests', sa.Column('compatible_geometry_ids', JSON, nullable=True))


def downgrade() -> None:
    op.drop_column('vests', 'compatible_geometry_ids')
