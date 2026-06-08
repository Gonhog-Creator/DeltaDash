"""Update anchor points ammunition scope to use calibers instead of specific ammo

Revision ID: 20260608_1256
Revises: 20260608_1237
Create Date: 2024-06-08 12:56:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '20260608_1256'
down_revision = '20260608_1237'
branch_labels = None
depends_on = None


def upgrade():
    # Add caliber_ids column
    op.add_column('anchor_points', sa.Column('caliber_ids', postgresql.ARRAY(sa.String()), nullable=True))
    
    # Update existing data: convert caliber_filter to caliber_ids if present
    op.execute("""
        UPDATE anchor_points
        SET caliber_ids = ARRAY[caliber_filter]
        WHERE caliber_filter IS NOT NULL
    """)
    
    # Update ammunition_scope values from 'specific' to 'all'
    op.execute("""
        UPDATE anchor_points
        SET ammunition_scope = 'all'
        WHERE ammunition_scope = 'specific'
    """)
    
    # Drop old columns
    op.drop_column('anchor_points', 'ammunition_ids')
    op.drop_column('anchor_points', 'caliber_filter')


def downgrade():
    # Add back old columns
    op.add_column('anchor_points', sa.Column('ammunition_ids', postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=True))
    op.add_column('anchor_points', sa.Column('caliber_filter', sa.String(), nullable=True))
    
    # Revert data: convert caliber_ids back to caliber_filter (take first if multiple)
    op.execute("""
        UPDATE anchor_points
        SET caliber_filter = caliber_ids[1]
        WHERE cardinality(caliber_ids) > 0
    """)
    
    # Revert ammunition_scope from 'all' to 'specific'
    op.execute("""
        UPDATE anchor_points
        SET ammunition_scope = 'specific'
        WHERE ammunition_scope = 'all'
    """)
    
    # Drop caliber_ids column
    op.drop_column('anchor_points', 'caliber_ids')
