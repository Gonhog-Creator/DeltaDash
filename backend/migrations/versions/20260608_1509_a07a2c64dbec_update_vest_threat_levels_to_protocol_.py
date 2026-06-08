"""update_vest_threat_levels_to_protocol_prefixed_format

Revision ID: a07a2c64dbec
Revises: 4aca2329496e
Create Date: 2026-06-08 15:09:35.755199

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a07a2c64dbec'
down_revision = '4aca2329496e'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Update existing threat level values to protocol-prefixed format
    # Map old values to new format with protocol names
    op.execute("""
        UPDATE vests 
        SET threat_level = 'ANMaC 2023 - RB2' 
        WHERE threat_level = 'ARG_RB2'
    """)
    op.execute("""
        UPDATE vests 
        SET threat_level = 'ANMaC 2023 - RB3' 
        WHERE threat_level = 'ARG_RB3'
    """)
    op.execute("""
        UPDATE vests 
        SET threat_level = 'ANMaC 2023 - RB4' 
        WHERE threat_level = 'ARG_RB4'
    """)
    op.execute("""
        UPDATE vests 
        SET threat_level = 'NIJ 0101.07 (USA) - HG2' 
        WHERE threat_level = 'NIJ_0101.07_HG2'
    """)


def downgrade() -> None:
    # Revert to old format
    op.execute("""
        UPDATE vests 
        SET threat_level = 'ARG_RB2' 
        WHERE threat_level = 'ANMaC 2023 - RB2'
    """)
    op.execute("""
        UPDATE vests 
        SET threat_level = 'ARG_RB3' 
        WHERE threat_level = 'ANMaC 2023 - RB3'
    """)
    op.execute("""
        UPDATE vests 
        SET threat_level = 'ARG_RB4' 
        WHERE threat_level = 'ANMaC 2023 - RB4'
    """)
    op.execute("""
        UPDATE vests 
        SET threat_level = 'NIJ_0101.07_HG2' 
        WHERE threat_level = 'NIJ 0101.07 (USA) - HG2'
    """)
