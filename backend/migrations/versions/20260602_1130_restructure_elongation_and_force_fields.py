"""restructure elongation and force fields: split elongation into transverse/longitudinal, change force_newtons_5cm to force_newtons + stretch_test_length, change errors to percentages

Revision ID: 20260602_1130
Revises: 20260522_1000
Create Date: 2026-06-02 11:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260602_1130'
down_revision = '20260522_1000'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new columns
    op.add_column('materials', sa.Column('elongation_transverse_percent', sa.Numeric(10, 2), nullable=True))
    op.add_column('materials', sa.Column('elongation_transverse_error_percent', sa.Numeric(10, 2), nullable=True))
    op.add_column('materials', sa.Column('elongation_longitudinal_percent', sa.Numeric(10, 2), nullable=True))
    op.add_column('materials', sa.Column('elongation_longitudinal_error_percent', sa.Numeric(10, 2), nullable=True))
    op.add_column('materials', sa.Column('force_newtons', sa.Numeric(10, 2), nullable=True))
    op.add_column('materials', sa.Column('force_error_percent', sa.Numeric(10, 2), nullable=True))
    op.add_column('materials', sa.Column('stretch_test_length', sa.String(10), nullable=True))

    # Migrate data from old columns to new columns
    # Copy old elongation_percent to both transverse and longitudinal (default behavior)
    op.execute("""
        UPDATE materials 
        SET elongation_transverse_percent = elongation_percent,
            elongation_longitudinal_percent = elongation_percent
        WHERE elongation_percent IS NOT NULL
    """)

    # Copy old elongation_error to both transverse and longitudinal error (as percentage)
    op.execute("""
        UPDATE materials 
        SET elongation_transverse_error_percent = elongation_error,
            elongation_longitudinal_error_percent = elongation_error
        WHERE elongation_error IS NOT NULL
    """)

    # Copy force_newtons_5cm to force_newtons
    op.execute("""
        UPDATE materials 
        SET force_newtons = force_newtons_5cm
        WHERE force_newtons_5cm IS NOT NULL
    """)

    # Copy force_error to force_error_percent (it was already stored as a percentage in the DB)
    op.execute("""
        UPDATE materials 
        SET force_error_percent = force_error
        WHERE force_error IS NOT NULL
    """)

    # Set default stretch_test_length to '5cm' for existing records
    op.execute("""
        UPDATE materials 
        SET stretch_test_length = '5cm'
        WHERE force_newtons_5cm IS NOT NULL
    """)

    # Drop old columns
    op.drop_column('materials', 'force_error')
    op.drop_column('materials', 'elongation_error')
    op.drop_column('materials', 'force_newtons_5cm')
    op.drop_column('materials', 'elongation_percent')


def downgrade() -> None:
    # Add back old columns
    op.add_column('materials', sa.Column('elongation_percent', sa.Numeric(10, 2), nullable=True))
    op.add_column('materials', sa.Column('force_newtons_5cm', sa.Numeric(10, 2), nullable=True))
    op.add_column('materials', sa.Column('elongation_error', sa.Numeric(10, 2), nullable=True))
    op.add_column('materials', sa.Column('force_error', sa.Numeric(10, 2), nullable=True))

    # Migrate data back (use transverse values for the old single elongation field)
    op.execute("""
        UPDATE materials 
        SET elongation_percent = elongation_transverse_percent
        WHERE elongation_transverse_percent IS NOT NULL
    """)

    op.execute("""
        UPDATE materials 
        SET elongation_error = elongation_transverse_error_percent
        WHERE elongation_transverse_error_percent IS NOT NULL
    """)

    # Copy force_newtons back to force_newtons_5cm
    op.execute("""
        UPDATE materials 
        SET force_newtons_5cm = force_newtons
        WHERE force_newtons IS NOT NULL
    """)

    # Copy force_error_percent back to force_error
    op.execute("""
        UPDATE materials 
        SET force_error = force_error_percent
        WHERE force_error_percent IS NOT NULL
    """)

    # Drop new columns
    op.drop_column('materials', 'stretch_test_length')
    op.drop_column('materials', 'force_error_percent')
    op.drop_column('materials', 'force_newtons')
    op.drop_column('materials', 'elongation_longitudinal_error_percent')
    op.drop_column('materials', 'elongation_longitudinal_percent')
    op.drop_column('materials', 'elongation_transverse_error_percent')
    op.drop_column('materials', 'elongation_transverse_percent')
