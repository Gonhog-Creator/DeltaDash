"""change_flexibility_rating_to_numeric

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-08-26 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'c3d4e5f6a7b8'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        'vests',
        'flexibility_rating',
        existing_type=sa.String(),
        type_=sa.Numeric(5, 2),
        postgresql_using='NULL',
        nullable=True
    )


def downgrade() -> None:
    op.alter_column(
        'vests',
        'flexibility_rating',
        existing_type=sa.Numeric(5, 2),
        type_=sa.String(),
        nullable=True
    )
