"""add original filename columns

Revision ID: 20260519_1230
Revises: 20260519_1200
Create Date: 2026-05-19 12:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260519_1230'
down_revision = '20260519_1200'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('materials', sa.Column('mss_original_filename', sa.String(), nullable=True))
    op.add_column('materials', sa.Column('sds_original_filename', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('materials', 'sds_original_filename')
    op.drop_column('materials', 'mss_original_filename')
