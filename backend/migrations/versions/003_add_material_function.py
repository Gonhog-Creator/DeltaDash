"""add material_function column

Revision ID: 003
Revises: 002
Create Date: 2026-05-15

"""
from alembic import op
import sqlalchemy as sa

revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('materials', sa.Column('material_function', sa.String(), nullable=True))
    op.create_index(op.f('ix_materials_material_function'), 'materials', ['material_function'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_materials_material_function'), table_name='materials')
    op.drop_column('materials', 'material_function')
