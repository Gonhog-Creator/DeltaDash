"""update parent test group foreign key to cascade delete

Revision ID: 012
Revises: 011
Create Date: 2026-05-15 11:58:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '012'
down_revision = '011'
branch_labels = None
depends_on = None


def upgrade():
    # Drop existing foreign key constraint
    op.drop_constraint('fk_test_sessions_parent_test_group_id', 'test_sessions', type_='foreignkey')
    
    # Recreate with CASCADE delete
    op.create_foreign_key(
        'fk_test_sessions_parent_test_group_id',
        'test_sessions',
        'test_sessions',
        ['parent_test_group_id'],
        ['id'],
        ondelete='CASCADE'
    )


def downgrade():
    # Drop cascade constraint
    op.drop_constraint('fk_test_sessions_parent_test_group_id', 'test_sessions', type_='foreignkey')
    
    # Recreate without CASCADE
    op.create_foreign_key(
        'fk_test_sessions_parent_test_group_id',
        'test_sessions',
        'test_sessions',
        ['parent_test_group_id'],
        ['id']
    )
