"""add created_by_username column

Revision ID: 005
Revises: 004
Create Date: 2026-05-15

"""
from alembic import op
import sqlalchemy as sa

revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('materials', sa.Column('created_by_username', sa.String(), nullable=True))
    op.create_index(op.f('ix_materials_created_by_username'), 'materials', ['created_by_username'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_materials_created_by_username'), table_name='materials')
    op.drop_column('materials', 'created_by_username')
