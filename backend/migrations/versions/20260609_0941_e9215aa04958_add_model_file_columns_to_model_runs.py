"""add_model_file_columns_to_model_runs

Revision ID: e9215aa04958
Revises: bc36916de771
Create Date: 2026-06-09 09:41:48.309281

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e9215aa04958'
down_revision = 'bc36916de771'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('model_runs', sa.Column('model_file', sa.LargeBinary(), nullable=True))
    op.add_column('model_runs', sa.Column('preprocessor_file', sa.LargeBinary(), nullable=True))


def downgrade() -> None:
    op.drop_column('model_runs', 'preprocessor_file')
    op.drop_column('model_runs', 'model_file')
