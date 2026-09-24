"""backfill shot_data.conditioning from test_sessions.conditioning

Revision ID: e7f8a9b0c1d2
Revises: d2e3f4a5b6c7
Create Date: 2026-09-24 12:00:00.000000

Conditioning moved from the session (vest) level to per-shot. This backfills
shot_data.conditioning for rows that predate the column, using the parent
session's conditioning. Combined session values are stored as 'front/back'
(e.g. 'ambient/wet') and are split per side.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'e7f8a9b0c1d2'
down_revision = 'd2e3f4a5b6c7'
branch_labels = None
depends_on = None

_FRONT_SIDES = ('front', 'frente')
_BACK_SIDES = ('back', 'espalda')


def upgrade():
    conn = op.get_bind()

    sessions = conn.execute(
        sa.text("SELECT id, conditioning FROM test_sessions WHERE conditioning IS NOT NULL")
    ).fetchall()

    for session_id, conditioning in sessions:
        parts = str(conditioning).split('/')
        if len(parts) == 2:
            # Combined 'front/back' value: assign each side its own part
            conn.execute(
                sa.text(
                    "UPDATE shot_data SET conditioning = :val "
                    "WHERE test_session_id = :sid AND conditioning IS NULL "
                    "AND lower(side) IN ('front', 'frente')"
                ),
                {"val": parts[0], "sid": session_id},
            )
            conn.execute(
                sa.text(
                    "UPDATE shot_data SET conditioning = :val "
                    "WHERE test_session_id = :sid AND conditioning IS NULL "
                    "AND lower(side) IN ('back', 'espalda')"
                ),
                {"val": parts[1], "sid": session_id},
            )
        else:
            # Single value applies to every shot missing conditioning
            conn.execute(
                sa.text(
                    "UPDATE shot_data SET conditioning = :val "
                    "WHERE test_session_id = :sid AND conditioning IS NULL"
                ),
                {"val": parts[0], "sid": session_id},
            )


def downgrade():
    # Revert only rows whose conditioning still matches the session-level value
    # (i.e. rows that were backfilled rather than set per-shot).
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE shot_data SET conditioning = NULL "
            "WHERE conditioning IS NOT NULL AND conditioning = ("
            "  SELECT conditioning FROM test_sessions "
            "  WHERE test_sessions.id = shot_data.test_session_id"
            ")"
        )
    )
