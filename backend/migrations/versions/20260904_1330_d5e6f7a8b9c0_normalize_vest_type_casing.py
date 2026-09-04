"""normalize_vest_type_casing

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-09-04 13:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd5e6f7a8b9c0'
down_revision = 'c4d5e6f7a8b9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Normalize vest_type to consistent casing: Soft, Hard, IWC
    op.execute("UPDATE vests SET vest_type = 'Soft' WHERE LOWER(vest_type) = 'soft'")
    op.execute("UPDATE vests SET vest_type = 'Hard' WHERE LOWER(vest_type) = 'hard'")
    op.execute("UPDATE vests SET vest_type = 'IWC' WHERE LOWER(vest_type) = 'iwc'")


def downgrade() -> None:
    # No meaningful downgrade — we can't recover the original inconsistent casings
    pass
