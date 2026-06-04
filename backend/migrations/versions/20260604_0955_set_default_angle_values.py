"""Set default angle values for shots 1-6

Revision ID: 20260604_0955
Revises: 20260603_1030
Create Date: 2026-06-04 09:55:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260604_0955'
down_revision = '20260603_1030'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Set default angle values for shots 1-6
    # Shot 1: 0°, Shot 2: 0°, Shot 3: 0°, Shot 4: 30°, Shot 5: 45°, Shot 6: 0°
    
    # Update shot_data table (handles decimal shot numbers like "1.0", "2.0")
    op.execute("""
        UPDATE shot_data 
        SET angle_degrees = CASE 
            WHEN shot_number::numeric::integer = 1 THEN 0
            WHEN shot_number::numeric::integer = 2 THEN 0
            WHEN shot_number::numeric::integer = 3 THEN 0
            WHEN shot_number::numeric::integer = 4 THEN 30
            WHEN shot_number::numeric::integer = 5 THEN 45
            WHEN shot_number::numeric::integer = 6 THEN 0
            ELSE angle_degrees
        END
        WHERE angle_degrees IS NULL 
        AND shot_number IS NOT NULL
        AND shot_number ~ '^[0-9.]+$'
        AND shot_number::numeric::integer BETWEEN 1 AND 6
    """)
    
    # Update shots table (manual shots)
    op.execute("""
        UPDATE shots 
        SET impact_angle_degrees = CASE 
            WHEN shot_number = 1 THEN 0
            WHEN shot_number = 2 THEN 0
            WHEN shot_number = 3 THEN 0
            WHEN shot_number = 4 THEN 30
            WHEN shot_number = 5 THEN 45
            WHEN shot_number = 6 THEN 0
            ELSE impact_angle_degrees
        END
        WHERE impact_angle_degrees IS NULL 
        AND shot_number IS NOT NULL
        AND shot_number BETWEEN 1 AND 6
    """)


def downgrade() -> None:
    # To downgrade, we would need to set the values back to NULL
    # However, this would lose user-edited values, so we'll leave them as is
    # This is a data migration that's not easily reversible
    pass
