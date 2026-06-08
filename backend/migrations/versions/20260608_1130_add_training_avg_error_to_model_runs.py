"""Add training_avg_error to model_runs

Revision ID: 20260608_1130
Revises: 20260604_0955
Create Date: 2024-06-08 11:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260608_1130'
down_revision = '20260604_0955'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('model_runs', sa.Column('training_avg_error', sa.Float(), nullable=True))


def downgrade():
    op.drop_column('model_runs', 'training_avg_error')
