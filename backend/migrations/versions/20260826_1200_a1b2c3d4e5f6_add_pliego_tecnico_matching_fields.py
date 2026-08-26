"""add_pliego_tecnico_matching_fields

Revision ID: a1b2c3d4e5f6
Revises: f8d20fa837ef
Create Date: 2026-08-26 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = 'f8d20fa837ef'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add pliego técnico matching fields to vests
    op.add_column('vests', sa.Column('weight_g', sa.Numeric(precision=10, scale=2), nullable=True))
    op.add_column('vests', sa.Column('trauma_homologation', postgresql.JSON(astext_type=sa.Text()), nullable=True))
    op.add_column('vests', sa.Column('flexibility_rating', sa.String(), nullable=True))
    op.add_column('vests', sa.Column('is_panel_sewn', sa.Boolean(), nullable=True))
    op.add_column('vests', sa.Column('size_curve', postgresql.JSON(astext_type=sa.Text()), nullable=True))

    # Add approval and size measurement fields to geometries
    op.add_column('geometries', sa.Column('is_approved', sa.Boolean(), nullable=True, server_default=sa.text('false')))
    op.add_column('geometries', sa.Column('size_measurements', postgresql.JSON(astext_type=sa.Text()), nullable=True))

    # Create covers (fundas) table
    op.create_table('covers',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('cover_code', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('geometry_id', sa.UUID(), nullable=True),
        sa.Column('fabric_type', sa.String(), nullable=True),
        sa.Column('fabric_weight_g_m2', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('layer_count', sa.Integer(), nullable=True),
        sa.Column('weight_g', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('has_molle', sa.Boolean(), nullable=True),
        sa.Column('molle_config', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('has_quick_release', sa.Boolean(), nullable=True),
        sa.Column('quick_release_type', sa.String(), nullable=True),
        sa.Column('fin_height_mm', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('fin_width_mm', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('available_sizes', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('compatible_vest_types', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('notes', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['geometry_id'], ['geometries.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_covers_cover_code'), 'covers', ['cover_code'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_covers_cover_code'), table_name='covers')
    op.drop_table('covers')

    op.drop_column('geometries', 'size_measurements')
    op.drop_column('geometries', 'is_approved')

    op.drop_column('vests', 'size_curve')
    op.drop_column('vests', 'is_panel_sewn')
    op.drop_column('vests', 'flexibility_rating')
    op.drop_column('vests', 'trauma_homologation')
    op.drop_column('vests', 'weight_g')
