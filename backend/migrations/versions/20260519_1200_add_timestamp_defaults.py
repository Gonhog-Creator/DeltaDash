"""add timestamp defaults

Revision ID: 20260519_1200
Revises: 314b789d9830
Create Date: 2026-05-19 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import func


# revision identifiers, used by Alembic.
revision = '20260519_1200'
down_revision = '314b789d9830'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add server_default for created_at and updated_at in materials table
    op.alter_column('materials', 'created_at',
                   existing_type=sa.DateTime(timezone=True),
                   nullable=False,
                   server_default=func.now())
    op.alter_column('materials', 'updated_at',
                   existing_type=sa.DateTime(timezone=True),
                   nullable=False,
                   server_default=func.now(),
                   onupdate=func.now())
    
    # Do the same for other tables that have created_at/updated_at
    op.alter_column('ammunition', 'created_at',
                   existing_type=sa.DateTime(timezone=True),
                   nullable=False,
                   server_default=func.now())
    op.alter_column('ammunition', 'updated_at',
                   existing_type=sa.DateTime(timezone=True),
                   nullable=False,
                   server_default=func.now(),
                   onupdate=func.now())
    
    op.alter_column('test_sessions', 'created_at',
                   existing_type=sa.DateTime(timezone=True),
                   nullable=False,
                   server_default=func.now())
    op.alter_column('test_sessions', 'updated_at',
                   existing_type=sa.DateTime(timezone=True),
                   nullable=False,
                   server_default=func.now(),
                   onupdate=func.now())


def downgrade() -> None:
    # Remove server_default from created_at and updated_at
    op.alter_column('materials', 'created_at',
                   existing_type=sa.DateTime(timezone=True),
                   nullable=False,
                   server_default=None)
    op.alter_column('materials', 'updated_at',
                   existing_type=sa.DateTime(timezone=True),
                   nullable=False,
                   server_default=None,
                   onupdate=None)
    
    op.alter_column('ammunition', 'created_at',
                   existing_type=sa.DateTime(timezone=True),
                   nullable=False,
                   server_default=None)
    op.alter_column('ammunition', 'updated_at',
                   existing_type=sa.DateTime(timezone=True),
                   nullable=False,
                   server_default=None,
                   onupdate=None)
    
    op.alter_column('test_sessions', 'created_at',
                   existing_type=sa.DateTime(timezone=True),
                   nullable=False,
                   server_default=None)
    op.alter_column('test_sessions', 'updated_at',
                   existing_type=sa.DateTime(timezone=True),
                   nullable=False,
                   server_default=None,
                   onupdate=None)
