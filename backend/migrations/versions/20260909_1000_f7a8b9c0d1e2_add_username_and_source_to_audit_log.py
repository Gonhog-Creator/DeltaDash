"""add_username_and_source_to_audit_log

Revision ID: f7a8b9c0d1e2
Revises: e6f7a8b9c0d1
Create Date: 2026-09-09 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f7a8b9c0d1e2'
down_revision = 'e6f7a8b9c0d1'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('audit_log', sa.Column('username', sa.String(), nullable=True))
    op.add_column('audit_log', sa.Column('source', sa.String(), nullable=True))
    op.execute("""
        UPDATE audit_log
        SET username = u.username
        FROM users u
        WHERE audit_log.user_id = u.id AND audit_log.username IS NULL
    """)
    op.execute("""
        UPDATE audit_log
        SET source = 'production'
        WHERE source IS NULL
    """)


def downgrade():
    op.drop_column('audit_log', 'source')
    op.drop_column('audit_log', 'username')
