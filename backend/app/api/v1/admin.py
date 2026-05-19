from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.db.models.material import Material
from app.db.models.test_session import TestSession
from app.db.models.vest import Vest
from app.db.models.shot_data import ShotData
from app.db.models.ammunition import Ammunition
from app.api.v1.auth import get_current_active_user, get_current_user
from app.db.models.user import User
import psycopg2
import os
from typing import Optional
from datetime import datetime
import uuid

router = APIRouter()

@router.post("/sync-database")
def sync_database(
    current_user: User = Depends(get_current_active_user)
):
    """Sync local database with remote database (pull only)."""
    # Check if user is admin
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Remote database connection details
    remote_db_url = os.getenv("REMOTE_DATABASE_URL")
    if not remote_db_url:
        raise HTTPException(status_code=500, detail="REMOTE_DATABASE_URL not configured")
    
    try:
        # Connect to remote database
        remote_conn = psycopg2.connect(remote_db_url)
        remote_cursor = remote_conn.cursor()
        
        # Get local database session
        local_db: Session = SessionLocal()
        
        try:
            # Sync ammunition
            remote_cursor.execute("SELECT * FROM ammunition")
            columns = [desc[0] for desc in remote_cursor.description]
            ammunition_data = remote_cursor.fetchall()
            
            for row in ammunition_data:
                ammo_dict = dict(zip(columns, row))
                # Check if ammunition already exists
                existing = local_db.query(Ammunition).filter(Ammunition.id == ammo_dict['id']).first()
                if not existing:
                    new_ammo = Ammunition(**ammo_dict)
                    local_db.add(new_ammo)
                else:
                    # Update existing ammunition
                    for key, value in ammo_dict.items():
                        if key != 'id' and hasattr(existing, key):
                            setattr(existing, key, value)
            
            # Sync materials
            remote_cursor.execute("SELECT * FROM materials")
            columns = [desc[0] for desc in remote_cursor.description]
            materials_data = remote_cursor.fetchall()
            
            for row in materials_data:
                material_dict = dict(zip(columns, row))
                # Check if material already exists
                existing = local_db.query(Material).filter(Material.id == material_dict['id']).first()
                if not existing:
                    new_material = Material(**material_dict)
                    local_db.add(new_material)
                else:
                    # Update existing material
                    for key, value in material_dict.items():
                        if key != 'id' and hasattr(existing, key):
                            setattr(existing, key, value)
            
            # Sync vests
            remote_cursor.execute("SELECT * FROM vests")
            columns = [desc[0] for desc in remote_cursor.description]
            vests_data = remote_cursor.fetchall()
            
            for row in vests_data:
                vest_dict = dict(zip(columns, row))
                # Check if vest already exists
                existing = local_db.query(Vest).filter(Vest.id == vest_dict['id']).first()
                if not existing:
                    new_vest = Vest(**vest_dict)
                    local_db.add(new_vest)
                else:
                    # Update existing vest
                    for key, value in vest_dict.items():
                        if key != 'id' and hasattr(existing, key):
                            setattr(existing, key, value)
            
            # Sync test sessions
            remote_cursor.execute("SELECT * FROM test_sessions")
            columns = [desc[0] for desc in remote_cursor.description]
            test_sessions_data = remote_cursor.fetchall()
            
            for row in test_sessions_data:
                session_dict = dict(zip(columns, row))
                # Check if session already exists
                existing = local_db.query(TestSession).filter(TestSession.id == session_dict['id']).first()
                if not existing:
                    new_session = TestSession(**session_dict)
                    local_db.add(new_session)
                else:
                    # Update existing session
                    for key, value in session_dict.items():
                        if key != 'id' and hasattr(existing, key):
                            setattr(existing, key, value)
            
            # Sync shot data
            remote_cursor.execute("SELECT * FROM shot_data")
            columns = [desc[0] for desc in remote_cursor.description]
            shot_data = remote_cursor.fetchall()
            
            for row in shot_data:
                shot_dict = dict(zip(columns, row))
                # Check if shot already exists
                existing = local_db.query(ShotData).filter(ShotData.id == shot_dict['id']).first()
                if not existing:
                    new_shot = ShotData(**shot_dict)
                    local_db.add(new_shot)
                else:
                    # Update existing shot
                    for key, value in shot_dict.items():
                        if key != 'id' and hasattr(existing, key):
                            setattr(existing, key, value)
            
            local_db.commit()
            
            return {"message": "Database sync completed successfully", "synced_records": {
                "ammunition": len(ammunition_data),
                "materials": len(materials_data),
                "vests": len(vests_data),
                "test_sessions": len(test_sessions_data),
                "shot_data": len(shot_data)
            }}
            
        except Exception as e:
            local_db.rollback()
            raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")
        finally:
            local_db.close()
            remote_cursor.close()
            remote_conn.close()
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to connect to remote database: {str(e)}")
