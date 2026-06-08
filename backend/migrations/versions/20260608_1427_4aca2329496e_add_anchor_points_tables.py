"""add_anchor_points_tables

Revision ID: 4aca2329496e
Revises: 3f093c3babbd
Create Date: 2026-06-08 14:27:06.888058

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4aca2329496e'
down_revision = '3f093c3babbd'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('''
        CREATE TABLE IF NOT EXISTS anchor_points (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR NOT NULL,
            description VARCHAR,
            ammunition_scope VARCHAR NOT NULL DEFAULT 'all',
            caliber_ids VARCHAR[],
            expected_perforated BOOLEAN NOT NULL,
            expected_bfd_mm NUMERIC(10,2),
            custom_velocity_mps NUMERIC(10,2),
            created_by_id UUID NOT NULL REFERENCES users(id),
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            batch_id UUID
        )
    ''')
    op.execute('''
        CREATE TABLE IF NOT EXISTS anchor_point_layers (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            anchor_point_id UUID NOT NULL REFERENCES anchor_points(id) ON DELETE CASCADE,
            material_id UUID NOT NULL REFERENCES materials(id),
            layer_count INTEGER NOT NULL DEFAULT 1,
            layer_index INTEGER NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    ''')


def downgrade() -> None:
    op.execute('DROP TABLE IF EXISTS anchor_point_layers CASCADE')
    op.execute('DROP TABLE IF EXISTS anchor_points CASCADE')
