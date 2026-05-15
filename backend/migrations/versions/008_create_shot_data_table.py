"""create shot_data table

Revision ID: 008
Revises: 007
Create Date: 2026-05-15

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = '008'
down_revision = '007'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'shot_data',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('test_session_id', UUID(as_uuid=True), sa.ForeignKey('test_sessions.id'), nullable=False),
        sa.Column('vest_number', sa.String(), nullable=True),
        sa.Column('side', sa.String(), nullable=True),
        sa.Column('shot_number', sa.String(), nullable=True),
        sa.Column('protection_level', sa.String(), nullable=True),
        sa.Column('caliber', sa.String(), nullable=True),
        sa.Column('trauma_mm', sa.Numeric(10, 2), nullable=True),
        sa.Column('velocity_m_s', sa.Numeric(10, 2), nullable=True),
        sa.Column('temperature_c', sa.Numeric(5, 2), nullable=True),
        sa.Column('humidity_percent', sa.Numeric(5, 2), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('shot_data')
