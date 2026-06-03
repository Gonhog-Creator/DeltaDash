"""Update protocol structure to support nested levels

Revision ID: 20260603_1030
Revises: 20260603_1000
Create Date: 2026-06-03 10:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260603_1030'
down_revision = '20260603_1000'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Rename ammunition_config to levels_config
    op.alter_column('protocols', 'ammunition_config', new_column_name='levels_config')
    
    # Drop total_shots column as it's no longer needed
    op.drop_column('protocols', 'total_shots')


def downgrade() -> None:
    # Add back total_shots column
    op.add_column('protocols', sa.Column('total_shots', sa.Integer(), nullable=True))
    
    # Rename levels_config back to ammunition_config
    op.alter_column('protocols', 'levels_config', new_column_name='ammunition_config')
