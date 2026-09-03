"""add_classifier_file_to_model_runs

Revision ID: b3c4d5e6f7a8
Revises: f1e2d3c4b5a6
Create Date: 2026-09-03 15:40:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b3c4d5e6f7a8'
down_revision = 'f1e2d3c4b5a6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('model_runs', sa.Column('classifier_file', sa.LargeBinary(), nullable=True))


def downgrade() -> None:
    op.drop_column('model_runs', 'classifier_file')
