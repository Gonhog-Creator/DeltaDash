"""add areal_density_tolerance to materials

Revision ID: 20261016_1205
Revises: 20261013_1330
Create Date: 2026-10-16 12:05:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20261016_1205'
down_revision = '20261013_1330'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [c['name'] for c in inspector.get_columns('materials')]

    if 'areal_density_tolerance' not in columns:
        op.add_column('materials', sa.Column('areal_density_tolerance', sa.String(), nullable=True))


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [c['name'] for c in inspector.get_columns('materials')]

    if 'areal_density_tolerance' in columns:
        op.drop_column('materials', 'areal_density_tolerance')
