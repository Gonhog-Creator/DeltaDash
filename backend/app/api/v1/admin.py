from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.db.models.material import Material
from app.db.models.test_session import TestSession
from app.db.models.vest import Vest
from app.db.models.shot_data import ShotData
from app.db.models.ammunition import Ammunition
from app.api.v1.auth import get_current_active_user, get_current_user
from app.db.models.user import User
from app.core.config import settings
import psycopg2
import os
import zipfile
import tempfile
import shutil
import subprocess
import re
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


@router.post("/backup")
def create_backup(
    current_user: User = Depends(get_current_active_user)
):
    """Create a backup of the database and storage files."""
    # Check if user is admin
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    try:
        # Create a temporary directory for the backup
        temp_dir = tempfile.mkdtemp()
        backup_filename = f"deltadash_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        backup_path = os.path.join(temp_dir, backup_filename)
        
        with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Dump the database
            db_backup_file = os.path.join(temp_dir, 'database_dump.sql')
            db_url = os.getenv("DATABASE_URL")
            
            # Parse DATABASE_URL to get connection details
            # Format: postgresql://user:password@host:port/database
            if db_url:
                # Use pg_dump to create a database dump
                try:
                    subprocess.run(
                        ['pg_dump', db_url, '-f', db_backup_file],
                        check=True,
                        capture_output=True
                    )
                    zipf.write(db_backup_file, 'database_dump.sql')
                except subprocess.CalledProcessError as e:
                    raise HTTPException(status_code=500, detail=f"Database dump failed: {e.stderr.decode()}")
            
            # Add storage files to the zip
            storage_dirs = [
                settings.material_docs_dir,
                settings.upload_dir,
                settings.reports_dir,
                settings.model_artifacts_dir
            ]
            
            for storage_dir in storage_dirs:
                if os.path.exists(storage_dir):
                    for root, dirs, files in os.walk(storage_dir):
                        for file in files:
                            file_path = os.path.join(root, file)
                            arcname = os.path.relpath(file_path, os.path.dirname(storage_dir))
                            zipf.write(file_path, arcname)
        
        # Return the zip file without cleanup - let the OS handle temp file cleanup
        return FileResponse(
            backup_path,
            media_type='application/zip',
            filename=backup_filename,
            background=None  # Don't use background task for cleanup
        )
        
    except Exception as e:
        # Clean up on error
        if 'temp_dir' in locals():
            shutil.rmtree(temp_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail=f"Backup failed: {str(e)}")


@router.post("/restore")
def restore_backup(
    backup_file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user)
):
    """Restore a backup of the database and storage files."""
    # Check if user is admin
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    try:
        # Create a temporary directory for extraction
        temp_dir = tempfile.mkdtemp()
        backup_path = os.path.join(temp_dir, backup_file.filename)
        
        # Save the uploaded file
        with open(backup_path, 'wb') as f:
            f.write(backup_file.file.read())
        
        # Extract the zip file
        with zipfile.ZipFile(backup_path, 'r') as zipf:
            zipf.extractall(temp_dir)
        
        # Restore the database
        db_backup_file = os.path.join(temp_dir, 'database_dump.sql')
        if os.path.exists(db_backup_file):
            db_url = os.getenv("DATABASE_URL")
            if db_url:
                try:
                    subprocess.run(
                        ['psql', db_url, '-f', db_backup_file],
                        check=True,
                        capture_output=True
                    )
                except subprocess.CalledProcessError as e:
                    raise HTTPException(status_code=500, detail=f"Database restore failed: {e.stderr.decode()}")
        
        # Restore storage files
        storage_dirs = [
            settings.material_docs_dir,
            settings.upload_dir,
            settings.reports_dir,
            settings.model_artifacts_dir
        ]
        
        for storage_dir in storage_dirs:
            os.makedirs(storage_dir, exist_ok=True)
            # Copy files from the backup to the storage directory
            backup_storage_dir = os.path.join(temp_dir, os.path.basename(storage_dir))
            if os.path.exists(backup_storage_dir):
                for item in os.listdir(backup_storage_dir):
                    src = os.path.join(backup_storage_dir, item)
                    dst = os.path.join(storage_dir, item)
                    if os.path.isdir(src):
                        shutil.rmtree(dst, ignore_errors=True)
                        shutil.copytree(src, dst)
                    else:
                        if os.path.exists(dst):
                            os.remove(dst)
                        shutil.copy2(src, dst)
        
        return {"message": "Backup restored successfully"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Restore failed: {str(e)}")
    finally:
        # Clean up temporary directory
        if 'temp_dir' in locals():
            shutil.rmtree(temp_dir, ignore_errors=True)


@router.get("/version")
def get_version(
    current_user: User = Depends(get_current_user)
):
    """Get the current version from environment variable or git commits."""
    # Use environment variable if available (production)
    if settings.VERSION:
        return {"version": settings.VERSION}
    
    # Fallback to git in development
    try:
        # Get the latest commit message
        result = subprocess.run(
            ['git', 'log', '-1', '--pretty=%B'],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        )

        commit_message = result.stdout.strip()

        # Try to extract version from commit message (semantic versioning pattern)
        version_match = re.match(r'^(\d+\.\d+(?:\.\d+)?)', commit_message)
        if version_match:
            return {"version": version_match.group(1)}
        else:
            # If no version found, return commit hash
            hash_result = subprocess.run(
                ['git', 'rev-parse', '--short', 'HEAD'],
                capture_output=True,
                text=True,
                cwd=os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            )
            return {"version": hash_result.stdout.strip()}

    except Exception as e:
        # If git is not available or fails, return default version
        return {"version": "1.0.0"}
