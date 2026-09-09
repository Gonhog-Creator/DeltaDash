"""rename pdf_document to pdf_documents

Revision ID: b9c0d1e2f3a4
Revises: a8b9c0d1e2f3
Create Date: 2026-09-09 11:15:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = 'b9c0d1e2f3a4'
down_revision = 'a8b9c0d1e2f3'
branch_labels = None
depends_on = None


def upgrade():
    # Rename pdf_document -> pdf_documents if the old column exists
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [c['name'] for c in inspector.get_columns('test_sessions')]

    if 'pdf_document' in columns and 'pdf_documents' not in columns:
        op.alter_column('test_sessions', 'pdf_document', new_column_name='pdf_documents')
    elif 'pdf_documents' not in columns:
        op.add_column('test_sessions', sa.Column('pdf_documents', JSONB, nullable=True))


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [c['name'] for c in inspector.get_columns('test_sessions')]

    if 'pdf_documents' in columns and 'pdf_document' not in columns:
        op.alter_column('test_sessions', 'pdf_documents', new_column_name='pdf_document')
