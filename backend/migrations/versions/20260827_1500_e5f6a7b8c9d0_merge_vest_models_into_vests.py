"""merge vest_models into vests: add composition, repoint model_documents

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-08-27 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'e5f6a7b8c9d0'
down_revision = 'd4e5f6a7b8c9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add composition column to vests
    op.add_column('vests', sa.Column('composition', sa.Text(), nullable=True))

    # 2. Add vest_id column to model_documents (new FK to vests)
    op.add_column('model_documents', sa.Column('vest_id', postgresql.UUID(as_uuid=True), nullable=True))

    # 3. Migrate data: for each vest_model, find a vest with matching vest_code
    #    and repoint its documents to that vest. Also copy composition.
    op.execute("""
        UPDATE model_documents d
        SET vest_id = v.id
        FROM vest_models vm, vests v
        WHERE d.model_id = vm.id
          AND v.vest_code = vm.name
    """)

    # Copy composition from vest_models to matching vests
    op.execute("""
        UPDATE vests v
        SET composition = vm.composition
        FROM vest_models vm
        WHERE v.vest_code = vm.name
          AND vm.composition IS NOT NULL
    """)

    # 4. Make vest_id non-nullable after migration (documents that didn't match will be orphaned)
    #    We delete orphans first, then set NOT NULL
    op.execute("DELETE FROM model_documents WHERE vest_id IS NULL")

    # 5. Add FK constraint and index
    op.create_foreign_key(
        'fk_model_documents_vest_id', 'model_documents', 'vests',
        ['vest_id'], ['id'], ondelete='CASCADE'
    )
    op.create_index('ix_model_documents_vest_id', 'model_documents', ['vest_id'])

    # 6. Drop the old model_id column (PostgreSQL auto-drops the FK constraint)
    op.drop_index('ix_model_documents_model_id', table_name='model_documents')
    op.drop_column('model_documents', 'model_id')

    # 7. Drop vest_models table
    op.drop_index('ix_vest_models_name', table_name='vest_models')
    op.drop_table('vest_models')


def downgrade() -> None:
    # Recreate vest_models table
    op.create_table(
        'vest_models',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(), nullable=False, unique=True),
        sa.Column('composition', sa.Text(), nullable=True),
    )
    op.create_index('ix_vest_models_name', 'vest_models', ['name'])

    # Re-add model_id column to model_documents
    op.add_column('model_documents', sa.Column('model_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_index('ix_model_documents_model_id', 'model_documents', ['model_id'])
    op.create_foreign_key(
        'fk_model_documents_model_id_vest_models', 'model_documents', 'vest_models',
        ['model_id'], ['id'], ondelete='CASCADE'
    )

    # Remove vest_id FK, index, and column
    op.drop_constraint('fk_model_documents_vest_id', 'model_documents', type_='foreignkey')
    op.drop_index('ix_model_documents_vest_id', table_name='model_documents')
    op.drop_column('model_documents', 'vest_id')

    # Remove composition from vests
    op.drop_column('vests', 'composition')
