"""add file paths to materials

Revision ID: 006
Revises: 005
Create Date: 2026-05-15

"""
from alembic import op
import sqlalchemy as sa

revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('materials', sa.Column('mss_file_path', sa.String(), nullable=True))
    op.add_column('materials', sa.Column('sds_file_path', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('materials', 'sds_file_path')
    op.drop_column('materials', 'mss_file_path')
