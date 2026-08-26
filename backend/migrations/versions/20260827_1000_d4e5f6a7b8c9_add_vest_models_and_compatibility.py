"""add vest_models, model_documents, and geometry compatibility

Revision ID: d4e5f6a7b8c9
Revises: 0a7b39e71c16
Create Date: 2026-08-27 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'd4e5f6a7b8c9'
down_revision = '0a7b39e71c16'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('geometries', sa.Column('compatibility', sa.String(), nullable=True))

    op.create_table(
        'vest_models',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(), nullable=False, unique=True),
        sa.Column('composition', sa.Text(), nullable=True),
    )
    op.create_index('ix_vest_models_name', 'vest_models', ['name'])

    op.create_table(
        'model_documents',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('model_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('vest_models.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('file_path', sa.String(), nullable=False),
        sa.Column('original_name', sa.String(), nullable=True),
    )
    op.create_index('ix_model_documents_model_id', 'model_documents', ['model_id'])


def downgrade() -> None:
    op.drop_index('ix_model_documents_model_id', table_name='model_documents')
    op.drop_table('model_documents')
    op.drop_index('ix_vest_models_name', table_name='vest_models')
    op.drop_table('vest_models')
    op.drop_column('geometries', 'compatibility')
