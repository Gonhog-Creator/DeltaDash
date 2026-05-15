"""add trauma_qualitative to shot_data

Revision ID: add_trauma_qualitative
Revises: 012
Create Date: 2026-05-15

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_trauma_qualitative'
down_revision = '012'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('shot_data', sa.Column('trauma_qualitative', sa.String(), nullable=True))


def downgrade():
    op.drop_column('shot_data', 'trauma_qualitative')
