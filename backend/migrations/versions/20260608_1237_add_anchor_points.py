"""Add anchor_points and anchor_point_layers tables

Revision ID: 20260608_1237
Revises: 20260608_1130
Create Date: 2024-06-08 12:37:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '20260608_1237'
down_revision = '20260608_1130'
branch_labels = None
depends_on = None


def upgrade():
    # Create anchor_points table
    op.create_table(
        'anchor_points',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('ammunition_scope', sa.String(), nullable=False, server_default='specific'),
        sa.Column('ammunition_ids', postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=True),
        sa.Column('caliber_filter', sa.String(), nullable=True),
        sa.Column('expected_perforated', sa.Boolean(), nullable=False),
        sa.Column('expected_bfd_mm', sa.Numeric(10, 2), nullable=True),
        sa.Column('custom_velocity_mps', sa.Numeric(10, 2), nullable=True),
        sa.Column('created_by_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], ),
    )
    
    # Create anchor_point_layers table
    op.create_table(
        'anchor_point_layers',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('anchor_point_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('material_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('layer_count', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('layer_index', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['anchor_point_id'], ['anchor_points.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['material_id'], ['materials.id'], ),
    )


def downgrade():
    op.drop_table('anchor_point_layers')
    op.drop_table('anchor_points')
