"""drop backing_material from vests

Revision ID: 20260603_drop_backing_material
Revises: 20260603_1030
Create Date: 2026-06-03 15:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260603_drop_backing_material'
down_revision = '20260603_1030'
branch_labels = None
depends_on = None


def upgrade():
    # Check if column exists before dropping
    from sqlalchemy import text, inspect
    from app.db.session import SessionLocal
    db = SessionLocal()
    try:
        inspector = inspect(db.bind)
        columns = [col['name'] for col in inspector.get_columns('vests')]
        if 'backing_material' in columns:
            op.drop_column('vests', 'backing_material')
    finally:
        db.close()


def downgrade():
    op.add_column('vests', sa.Column('backing_material', sa.String(), nullable=True))
