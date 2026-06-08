"""add_training_avg_error_to_model_runs

Revision ID: 3f093c3babbd
Revises: 20260608_1320
Create Date: 2026-06-08 14:19:12.378985

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3f093c3babbd'
down_revision = '20260608_1320'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('model_runs', sa.Column('training_avg_error', sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column('model_runs', 'training_avg_error')
