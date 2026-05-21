"""add ply_orientations to materials

Revision ID: 20260521_1400
Revises: 20260521_1300
Create Date: 2026-05-21 14:00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260521_1400'
down_revision = '20260521_1300'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('materials', sa.Column('ply_orientations', postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade():
    op.drop_column('materials', 'ply_orientations')
