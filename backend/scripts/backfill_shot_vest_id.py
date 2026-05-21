"""
Backfill vest_id in Shot table from test_session.vest_id
This script populates the vest_id column in the shots table
by copying the vest_id from the associated test_session.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.db.session import SessionLocal
from app.db.models.shot import Shot
from app.db.models.test_session import TestSession


def backfill_shot_vest_id():
    """
    Backfill vest_id in Shot table from test_session.vest_id
    """
    db: Session = SessionLocal()
    
    try:
        # Get all shots that have vest_id = NULL but have a test_session with vest_id
        query = db.query(Shot).join(TestSession).filter(
            Shot.vest_id.is_(None),
            TestSession.vest_id != None
        )
        
        shots_to_update = query.all()
        
        print(f"Found {len(shots_to_update)} shots to update")
        
        if not shots_to_update:
            print("No shots need vest_id backfill")
            return
        
        # Update each shot
        updated_count = 0
        for shot in shots_to_update:
            if shot.test_session and shot.test_session.vest_id:
                shot.vest_id = shot.test_session.vest_id
                updated_count += 1
        
        db.commit()
        
        print(f"Successfully updated {updated_count} shots with vest_id")
        
        # Verify the update
        remaining_null = db.query(Shot).filter(
            Shot.vest_id.is_(None)
        ).count()
        
        print(f"Remaining shots with NULL vest_id: {remaining_null}")
        
    except Exception as e:
        db.rollback()
        print(f"Error backfilling vest_id: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    backfill_shot_vest_id()
