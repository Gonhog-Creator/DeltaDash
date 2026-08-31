"""add geometry_id to test sessions

Revision ID: 640b8cb7bdaa
Revises: f6a7b8c9d0e1
Create Date: 2026-08-31 11:24:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision = '640b8cb7bdaa'
down_revision = 'f6a7b8c9d0e1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Check if geometry_id column already exists
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('test_sessions')]

    if 'geometry_id' not in columns:
        # Add geometry_id column to test_sessions table (nullable, user must select)
        op.add_column(
            'test_sessions',
            sa.Column('geometry_id', UUID(as_uuid=True), nullable=True)
        )

        # Create foreign key constraint to geometries table
        op.create_foreign_key(
            'fk_test_sessions_geometry_id',
            'test_sessions', 'geometries',
            ['geometry_id'], ['id'],
            ondelete='SET NULL'
        )
    else:
        # Column exists, check if foreign key exists
        foreign_keys = [fk['name'] for fk in inspector.get_foreign_keys('test_sessions')]
        if 'fk_test_sessions_geometry_id' not in foreign_keys:
            op.create_foreign_key(
                'fk_test_sessions_geometry_id',
                'test_sessions', 'geometries',
                ['geometry_id'], ['id'],
                ondelete='SET NULL'
            )


def downgrade() -> None:
    # Drop foreign key constraint
    op.drop_constraint('fk_test_sessions_geometry_id', 'test_sessions', type_='foreignkey')

    # Drop geometry_id column
    op.drop_column('test_sessions', 'geometry_id')
