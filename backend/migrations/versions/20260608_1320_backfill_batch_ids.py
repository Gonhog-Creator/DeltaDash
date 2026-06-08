"""backfill batch_ids for existing batch-created anchor points

Revision ID: 20260608_1320
Revises: 20260608_1318
Create Date: 2026-06-08 13:20:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid

# revision identifiers, used by Alembic.
revision = '20260608_1320'
down_revision = '20260608_1318'
branch_labels = None
depends_on = None


def upgrade():
    # Backfill batch_ids for existing anchor points that were created in batch mode
    # Group by base name (everything before " - ")
    connection = op.get_bind()
    
    # Get all anchor points without batch_id
    result = connection.execute(sa.text("""
        SELECT id, name 
        FROM anchor_points 
        WHERE batch_id IS NULL
    """))
    
    anchor_points = result.fetchall()
    
    # Group by base name
    groups = {}
    for anchor_id, name in anchor_points:
        base_name = name.split(' - ')[0] if ' - ' in name else name
        if base_name not in groups:
            groups[base_name] = []
        groups[base_name].append(anchor_id)
    
    # Assign batch_id to groups with more than one anchor point
    for base_name, ids in groups.items():
        if len(ids) > 1:
            batch_id = str(uuid.uuid4())
            connection.execute(sa.text("""
                UPDATE anchor_points 
                SET batch_id = :batch_id 
                WHERE id = ANY(:ids)
            """), {'batch_id': batch_id, 'ids': ids})


def downgrade():
    # Remove batch_ids that were backfilled
    connection = op.get_bind()
    connection.execute(sa.text("""
        UPDATE anchor_points 
        SET batch_id = NULL 
        WHERE batch_id IS NOT NULL
    """))