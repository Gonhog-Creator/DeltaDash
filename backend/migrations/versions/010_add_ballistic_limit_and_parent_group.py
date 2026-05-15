"""add ballistic limit and parent test group

Revision ID: 010
Revises: 009
Create Date: 2026-05-15 11:37:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '010'
down_revision = '009'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('test_sessions', sa.Column('size', sa.String(), nullable=True))
    op.add_column('test_sessions', sa.Column('ballistic_limit', sa.Boolean(), nullable=True, server_default='false'))
    op.add_column('test_sessions', sa.Column('parent_test_group_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key('fk_test_sessions_parent_test_group_id', 'test_sessions', 'test_sessions', ['parent_test_group_id'], ['id'], ondelete='CASCADE')


def downgrade():
    op.drop_constraint('fk_test_sessions_parent_test_group_id', 'test_sessions', type_='foreignkey')
    op.drop_column('test_sessions', 'parent_test_group_id')
    op.drop_column('test_sessions', 'ballistic_limit')
    op.drop_column('test_sessions', 'size')
