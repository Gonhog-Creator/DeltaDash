"""change_flexibility_rating_to_boolean

Revision ID: 9e1f63785a9c
Revises: 640b8cb7bdaa
Create Date: 2026-08-31 14:09:02.643135

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9e1f63785a9c'
down_revision = '640b8cb7bdaa'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Convert any existing numeric/null flexibility values to a boolean.
    # Any previous non-zero rating is treated as "yes"; null/0 becomes "no" (false).
    op.alter_column(
        'vests',
        'flexibility_rating',
        existing_type=sa.NUMERIC(precision=5, scale=2),
        type_=sa.Boolean(),
        nullable=False,
        server_default='false',
        postgresql_using='CASE WHEN flexibility_rating > 0 THEN true ELSE false END'
    )


def downgrade() -> None:
    op.alter_column(
        'vests',
        'flexibility_rating',
        existing_type=sa.Boolean(),
        type_=sa.NUMERIC(precision=5, scale=2),
        nullable=True,
        postgresql_using='flexibility_rating::int::numeric(5,2)'
    )