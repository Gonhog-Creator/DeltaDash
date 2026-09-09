"""add_pdf_and_images_to_test_sessions

Revision ID: a8b9c0d1e2f3
Revises: f7a8b9c0d1e2
Create Date: 2026-09-09 11:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision = 'a8b9c0d1e2f3'
down_revision = 'f7a8b9c0d1e2'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('test_sessions', sa.Column('pdf_documents', JSONB, nullable=True))
    op.add_column('test_sessions', sa.Column('front_image', JSONB, nullable=True))
    op.add_column('test_sessions', sa.Column('back_image', JSONB, nullable=True))


def downgrade():
    op.drop_column('test_sessions', 'back_image')
    op.drop_column('test_sessions', 'front_image')
    op.drop_column('test_sessions', 'pdf_documents')
