"""add angle_degrees to shot_data

Revision ID: add_angle_degrees
Revises: add_trauma_qualitative
Create Date: 2026-05-15

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_angle_degrees'
down_revision = 'add_trauma_qualitative'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('shot_data', sa.Column('angle_degrees', sa.Numeric(5, 2), nullable=True))


def downgrade():
    op.drop_column('shot_data', 'angle_degrees')
