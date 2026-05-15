"""Change email to username

Revision ID: 002
Revises: 001
Create Date: 2026-05-14 21:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add username column
    op.add_column('users', sa.Column('username', sa.String(), nullable=True))
    
    # Drop unique constraint on email
    op.drop_index('ix_users_email', table_name='users')
    
    # Populate username from email (remove @domain part)
    op.execute("UPDATE users SET username = split_part(email, '@', 1)")
    
    # Make username not null and unique
    op.alter_column('users', 'username', nullable=False)
    op.create_index('ix_users_username', 'users', ['username'], unique=True)
    
    # Drop email column
    op.drop_column('users', 'email')


def downgrade() -> None:
    # Add email column back
    op.add_column('users', sa.Column('email', sa.String(), nullable=True))
    
    # Populate email from username (add @example.com)
    op.execute("UPDATE users SET email = username || '@example.com'")
    
    # Make email not null and unique
    op.alter_column('users', 'email', nullable=False)
    op.create_index('ix_users_email', 'users', ['email'], unique=True)
    
    # Drop username column
    op.drop_index('ix_users_username', table_name='users')
    op.drop_column('users', 'username')
