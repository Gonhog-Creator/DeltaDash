"""add vest_id to shots table

Revision ID: 20260521_1100
Revises: 20260519_1600
Create Date: 2026-05-21 11:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision = '20260521_1100'
down_revision = '20260519_1600'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Check if vest_id column already exists
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('shots')]
    
    if 'vest_id' not in columns:
        # Add vest_id column to shots table
        op.add_column('shots', sa.Column('vest_id', UUID(as_uuid=True), nullable=True))
        
        # Create foreign key constraint
        op.create_foreign_key(
            'fk_shots_vest_id',
            'shots', 'vests',
            ['vest_id'], ['id'],
            ondelete='SET NULL'
        )
    else:
        # Column exists, check if foreign key exists
        foreign_keys = [fk['name'] for fk in inspector.get_foreign_keys('shots')]
        if 'fk_shots_vest_id' not in foreign_keys:
            op.create_foreign_key(
                'fk_shots_vest_id',
                'shots', 'vests',
                ['vest_id'], ['id'],
                ondelete='SET NULL'
            )


def downgrade() -> None:
    # Drop foreign key constraint
    op.drop_constraint('fk_shots_vest_id', 'shots', type_='foreignkey')
    
    # Drop vest_id column
    op.drop_column('shots', 'vest_id')
