"""add batch_id to anchor_points

Revision ID: 20260608_1318
Revises: 20260608_1256
Create Date: 2026-06-08 13:18:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260608_1318'
down_revision = '20260608_1256'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('anchor_points', sa.Column('batch_id', postgresql.UUID(as_uuid=True), nullable=True))


def downgrade():
    op.drop_column('anchor_points', 'batch_id')
