"""add_geometry_model_and_material_price

Revision ID: 519b293a83f4
Revises: d1f499d789e3
Create Date: 2026-06-12 15:20:46.620680

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '519b293a83f4'
down_revision = 'd1f499d789e3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add price_per_m2 column to materials table
    op.add_column('materials', sa.Column('price_per_m2', sa.Numeric(10, 2), nullable=True))
    
    # Create geometries table
    op.create_table(
        'geometries',
        sa.Column('id', sa.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('vest_type', sa.String(), nullable=True),
        sa.Column('surface_areas', sa.JSON(), nullable=False),
        sa.Column('available_sizes', sa.JSON(), nullable=False),
        sa.Column('includes_hard_plates', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('notes', sa.String(), nullable=True),
    )
    op.create_index(op.f('ix_geometries_name'), 'geometries', ['name'], unique=False)
    op.create_index(op.f('ix_geometries_vest_type'), 'geometries', ['vest_type'], unique=False)


def downgrade() -> None:
    # Drop geometries table
    op.drop_index(op.f('ix_geometries_vest_type'), table_name='geometries')
    op.drop_index(op.f('ix_geometries_name'), table_name='geometries')
    op.drop_table('geometries')
    
    # Remove price_per_m2 column from materials table
    op.drop_column('materials', 'price_per_m2')
