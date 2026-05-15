"""add excel_file_path to test_sessions

Revision ID: 007
Revises: 006
Create Date: 2026-05-15

"""
from alembic import op
import sqlalchemy as sa

revision = '007'
down_revision = '006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('test_sessions', sa.Column('excel_file_path', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('test_sessions', 'excel_file_path')
