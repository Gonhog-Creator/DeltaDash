"""remove ply_orientations from vest_layers

Revision ID: 20260521_1500
Revises: 20260521_1400
Create Date: 2026-05-21 15:00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260521_1500'
down_revision = '20260521_1400'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_column('vest_layers', 'ply_orientations')
    op.drop_column('vest_layers', 'orientation_degrees')


def downgrade():
    op.add_column('vest_layers', sa.Column('orientation_degrees', sa.Numeric(precision=5, scale=2), nullable=True))
    op.add_column('vest_layers', sa.Column('ply_orientations', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
