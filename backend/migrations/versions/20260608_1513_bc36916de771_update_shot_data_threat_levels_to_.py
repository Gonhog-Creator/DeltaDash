"""update_shot_data_threat_levels_to_protocol_prefixed_format

Revision ID: bc36916de771
Revises: a07a2c64dbec
Create Date: 2026-06-08 15:13:27.695020

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'bc36916de771'
down_revision = 'a07a2c64dbec'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Update shot_data threat level values to protocol-prefixed format
    # Map old values to new format with protocol names
    op.execute("""
        UPDATE shot_data sd
        SET protection_level = 'ANMaC 2023 - RB2'
        FROM test_sessions ts
        WHERE sd.test_session_id = ts.id
        AND ts.protocol = 'ANMaC 2023'
        AND sd.protection_level = 'RB2'
    """)
    op.execute("""
        UPDATE shot_data sd
        SET protection_level = 'ANMaC 2023 - RB3'
        FROM test_sessions ts
        WHERE sd.test_session_id = ts.id
        AND ts.protocol = 'ANMaC 2023'
        AND sd.protection_level = 'RB3'
    """)
    op.execute("""
        UPDATE shot_data sd
        SET protection_level = 'ANMaC 2023 - RB4'
        FROM test_sessions ts
        WHERE sd.test_session_id = ts.id
        AND ts.protocol = 'ANMaC 2023'
        AND sd.protection_level = 'RB4'
    """)
    op.execute("""
        UPDATE shot_data sd
        SET protection_level = 'NIJ 0101.07 (USA) - HG2'
        FROM test_sessions ts
        WHERE sd.test_session_id = ts.id
        AND ts.protocol = 'NIJ 0101.07 (USA)'
    """)


def downgrade() -> None:
    # Revert to old format
    op.execute("""
        UPDATE shot_data sd
        SET protection_level = 'RB2'
        FROM test_sessions ts
        WHERE sd.test_session_id = ts.id
        AND ts.protocol = 'ANMaC 2023'
        AND sd.protection_level = 'ANMaC 2023 - RB2'
    """)
    op.execute("""
        UPDATE shot_data sd
        SET protection_level = 'RB3'
        FROM test_sessions ts
        WHERE sd.test_session_id = ts.id
        AND ts.protocol = 'ANMaC 2023'
        AND sd.protection_level = 'ANMaC 2023 - RB3'
    """)
    op.execute("""
        UPDATE shot_data sd
        SET protection_level = 'RB4'
        FROM test_sessions ts
        WHERE sd.test_session_id = ts.id
        AND ts.protocol = 'ANMaC 2023'
        AND sd.protection_level = 'ANMaC 2023 - RB4'
    """)
    op.execute("""
        UPDATE shot_data sd
        SET protection_level = 'HG2'
        FROM test_sessions ts
        WHERE sd.test_session_id = ts.id
        AND ts.protocol = 'NIJ 0101.07 (USA)'
        AND sd.protection_level = 'NIJ 0101.07 (USA) - HG2'
    """)
