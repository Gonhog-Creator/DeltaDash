"""split force into longitudinal and transverse, remove stretch_test_length

Revision ID: 20260602_1149
Revises: 20260602_1130
Create Date: 2026-06-02 11:49:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260602_1149'
down_revision = '20260602_1130'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new columns for longitudinal and transverse force
    op.add_column('materials', sa.Column('force_longitudinal_newtons', sa.Numeric(10, 2), nullable=True))
    op.add_column('materials', sa.Column('force_longitudinal_error_percent', sa.Numeric(10, 2), nullable=True))
    op.add_column('materials', sa.Column('force_transverse_newtons', sa.Numeric(10, 2), nullable=True))
    op.add_column('materials', sa.Column('force_transverse_error_percent', sa.Numeric(10, 2), nullable=True))

    # Migrate data from old force_newtons to both longitudinal and transverse
    op.execute("""
        UPDATE materials 
        SET force_longitudinal_newtons = force_newtons,
            force_transverse_newtons = force_newtons
        WHERE force_newtons IS NOT NULL
    """)

    op.execute("""
        UPDATE materials 
        SET force_longitudinal_error_percent = force_error_percent,
            force_transverse_error_percent = force_error_percent
        WHERE force_error_percent IS NOT NULL
    """)

    # Drop old columns
    op.drop_column('materials', 'stretch_test_length')
    op.drop_column('materials', 'force_error_percent')
    op.drop_column('materials', 'force_newtons')


def downgrade() -> None:
    # Add back old columns
    op.add_column('materials', sa.Column('force_newtons', sa.Numeric(10, 2), nullable=True))
    op.add_column('materials', sa.Column('force_error_percent', sa.Numeric(10, 2), nullable=True))
    op.add_column('materials', sa.Column('stretch_test_length', sa.String(10), nullable=True))

    # Migrate data back (use longitudinal values for the old single force field)
    op.execute("""
        UPDATE materials 
        SET force_newtons = force_longitudinal_newtons
        WHERE force_longitudinal_newtons IS NOT NULL
    """)

    op.execute("""
        UPDATE materials 
        SET force_error_percent = force_longitudinal_error_percent
        WHERE force_longitudinal_error_percent IS NOT NULL
    """)

    # Set default stretch_test_length to '5cm' for existing records
    op.execute("""
        UPDATE materials 
        SET stretch_test_length = '5cm'
        WHERE force_longitudinal_newtons IS NOT NULL
    """)

    # Drop new columns
    op.drop_column('materials', 'force_transverse_error_percent')
    op.drop_column('materials', 'force_transverse_newtons')
    op.drop_column('materials', 'force_longitudinal_error_percent')
    op.drop_column('materials', 'force_longitudinal_newtons')
