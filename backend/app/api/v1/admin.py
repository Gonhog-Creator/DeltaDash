from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Body, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.db.models.material import Material
from app.db.models.test_session import TestSession
from app.db.models.vest import Vest
from app.db.models.vest_layer import VestLayer
from app.db.models.shot_data import ShotData
from app.db.models.ammunition import Ammunition
from app.db.models.model_run import ModelRun
from app.db.models.prediction import Prediction
from app.db.models.protocol import Protocol
from app.db.models.location import Location
from app.db.models.anchor_point import AnchorPoint, AnchorPointLayer
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
import threading
from typing import Optional, Dict
from datetime import datetime
import uuid
from sqlalchemy import text

router = APIRouter()

# Global dictionary to track restore progress
restore_progress: Dict[str, dict] = {}

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
        print(f"Attempting to connect to remote database: {remote_db_url}")
        remote_conn = psycopg2.connect(remote_db_url, connect_timeout=10)
        remote_cursor = remote_conn.cursor()
        print("Successfully connected to remote database")
        
        # Get local database session
        local_db: Session = SessionLocal()
        
        try:
            # Sync ammunition
            print("Syncing ammunition...")
            remote_cursor.execute("SELECT * FROM ammunition")
            columns = [desc[0] for desc in remote_cursor.description]
            ammunition_data = remote_cursor.fetchall()
            print(f"Found {len(ammunition_data)} ammunition records")
            
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
            
            local_db.commit()
            print("Ammunition synced successfully")
            
            # Sync materials
            remote_cursor.execute("SELECT * FROM materials")
            columns = [desc[0] for desc in remote_cursor.description]
            materials_data = remote_cursor.fetchall()
            
            for row in materials_data:
                material_dict = dict(zip(columns, row))
                # Filter out columns that don't exist in the local Material model
                valid_columns = {key: value for key, value in material_dict.items() if hasattr(Material, key)}
                # Check if material already exists
                existing = local_db.query(Material).filter(Material.id == valid_columns['id']).first()
                if not existing:
                    new_material = Material(**valid_columns)
                    local_db.add(new_material)
                else:
                    # Update existing material
                    for key, value in valid_columns.items():
                        if key != 'id' and hasattr(existing, key):
                            setattr(existing, key, value)
            
            local_db.commit()
            print("Materials synced successfully")
            
            # Sync vests
            remote_cursor.execute("SELECT * FROM vests")
            columns = [desc[0] for desc in remote_cursor.description]
            vests_data = remote_cursor.fetchall()
            
            for row in vests_data:
                vest_dict = dict(zip(columns, row))
                # Filter out columns that don't exist in the local Vest model
                valid_columns = {key: value for key, value in vest_dict.items() if hasattr(Vest, key)}
                # Check if vest already exists
                existing = local_db.query(Vest).filter(Vest.id == valid_columns['id']).first()
                if not existing:
                    new_vest = Vest(**valid_columns)
                    local_db.add(new_vest)
                else:
                    # Update existing vest
                    for key, value in valid_columns.items():
                        if key != 'id' and hasattr(existing, key):
                            setattr(existing, key, value)
            
            local_db.commit()
            print("Vests synced successfully")
            
            # Sync vest layers
            remote_cursor.execute("SELECT * FROM vest_layers")
            columns = [desc[0] for desc in remote_cursor.description]
            vest_layers_data = remote_cursor.fetchall()
            
            for row in vest_layers_data:
                layer_dict = dict(zip(columns, row))
                # Filter out columns that don't exist in the local VestLayer model
                valid_columns = {key: value for key, value in layer_dict.items() if hasattr(VestLayer, key)}
                # Check if layer already exists
                existing = local_db.query(VestLayer).filter(VestLayer.id == valid_columns['id']).first()
                if not existing:
                    new_layer = VestLayer(**valid_columns)
                    local_db.add(new_layer)
                else:
                    # Update existing layer
                    for key, value in valid_columns.items():
                        if key != 'id' and hasattr(existing, key):
                            setattr(existing, key, value)
            
            local_db.commit()
            print("Vest layers synced successfully")
            
            # Sync test sessions
            remote_cursor.execute("SELECT * FROM test_sessions")
            columns = [desc[0] for desc in remote_cursor.description]
            test_sessions_data = remote_cursor.fetchall()
            
            for row in test_sessions_data:
                session_dict = dict(zip(columns, row))
                # Filter out columns that don't exist in the local TestSession model
                valid_columns = {key: value for key, value in session_dict.items() if hasattr(TestSession, key)}
                # Check if session already exists
                existing = local_db.query(TestSession).filter(TestSession.id == valid_columns['id']).first()
                if not existing:
                    new_session = TestSession(**valid_columns)
                    local_db.add(new_session)
                else:
                    # Update existing session
                    for key, value in valid_columns.items():
                        if key != 'id' and hasattr(existing, key):
                            setattr(existing, key, value)
            
            # Commit test sessions before syncing shot data to satisfy foreign key constraint
            local_db.commit()
            print("Test sessions synced successfully")
            
            # Sync shot data
            remote_cursor.execute("SELECT * FROM shot_data")
            columns = [desc[0] for desc in remote_cursor.description]
            shot_data = remote_cursor.fetchall()
            
            for row in shot_data:
                shot_dict = dict(zip(columns, row))
                # Filter out columns that don't exist in the local ShotData model
                valid_columns = {key: value for key, value in shot_dict.items() if hasattr(ShotData, key)}
                # Check if shot already exists
                existing = local_db.query(ShotData).filter(ShotData.id == valid_columns['id']).first()
                if not existing:
                    new_shot = ShotData(**valid_columns)
                    local_db.add(new_shot)
                else:
                    # Update existing shot
                    for key, value in valid_columns.items():
                        if key != 'id' and hasattr(existing, key):
                            setattr(existing, key, value)
            
            local_db.commit()
            print("Shot data synced successfully")
            
            # Sync model runs
            remote_cursor.execute("SELECT * FROM model_runs")
            columns = [desc[0] for desc in remote_cursor.description]
            model_runs_data = remote_cursor.fetchall()
            print(f"Found {len(model_runs_data)} model run records")
            
            for row in model_runs_data:
                model_run_dict = dict(zip(columns, row))
                valid_columns = {key: value for key, value in model_run_dict.items() if hasattr(ModelRun, key)}
                existing = local_db.query(ModelRun).filter(ModelRun.id == valid_columns['id']).first()
                if not existing:
                    new_model_run = ModelRun(**valid_columns)
                    local_db.add(new_model_run)
                else:
                    for key, value in valid_columns.items():
                        if key != 'id' and hasattr(existing, key):
                            setattr(existing, key, value)
            
            local_db.commit()
            print("Model runs synced successfully")
            
            # Sync predictions
            remote_cursor.execute("SELECT * FROM predictions")
            columns = [desc[0] for desc in remote_cursor.description]
            predictions_data = remote_cursor.fetchall()
            print(f"Found {len(predictions_data)} prediction records")
            
            for row in predictions_data:
                prediction_dict = dict(zip(columns, row))
                valid_columns = {key: value for key, value in prediction_dict.items() if hasattr(Prediction, key)}
                existing = local_db.query(Prediction).filter(Prediction.id == valid_columns['id']).first()
                if not existing:
                    new_prediction = Prediction(**valid_columns)
                    local_db.add(new_prediction)
                else:
                    for key, value in valid_columns.items():
                        if key != 'id' and hasattr(existing, key):
                            setattr(existing, key, value)
            
            local_db.commit()
            print("Predictions synced successfully")
            
            # Sync protocols
            remote_cursor.execute("SELECT * FROM protocols")
            columns = [desc[0] for desc in remote_cursor.description]
            protocols_data = remote_cursor.fetchall()
            print(f"Found {len(protocols_data)} protocol records")
            
            for row in protocols_data:
                protocol_dict = dict(zip(columns, row))
                valid_columns = {key: value for key, value in protocol_dict.items() if hasattr(Protocol, key)}
                existing = local_db.query(Protocol).filter(Protocol.id == valid_columns['id']).first()
                if not existing:
                    new_protocol = Protocol(**valid_columns)
                    local_db.add(new_protocol)
                else:
                    for key, value in valid_columns.items():
                        if key != 'id' and hasattr(existing, key):
                            setattr(existing, key, value)
            
            local_db.commit()
            print("Protocols synced successfully")
            
            # Sync locations (labs)
            remote_cursor.execute("SELECT * FROM locations")
            columns = [desc[0] for desc in remote_cursor.description]
            locations_data = remote_cursor.fetchall()
            print(f"Found {len(locations_data)} location records")
            
            for row in locations_data:
                location_dict = dict(zip(columns, row))
                valid_columns = {key: value for key, value in location_dict.items() if hasattr(Location, key)}
                existing = local_db.query(Location).filter(Location.id == valid_columns['id']).first()
                if not existing:
                    new_location = Location(**valid_columns)
                    local_db.add(new_location)
                else:
                    for key, value in valid_columns.items():
                        if key != 'id' and hasattr(existing, key):
                            setattr(existing, key, value)
            
            local_db.commit()
            print("Locations synced successfully")
            
            # Sync anchor points
            remote_cursor.execute("SELECT * FROM anchor_points")
            columns = [desc[0] for desc in remote_cursor.description]
            anchor_points_data = remote_cursor.fetchall()
            print(f"Found {len(anchor_points_data)} anchor point records")
            
            for row in anchor_points_data:
                anchor_point_dict = dict(zip(columns, row))
                valid_columns = {key: value for key, value in anchor_point_dict.items() if hasattr(AnchorPoint, key)}
                existing = local_db.query(AnchorPoint).filter(AnchorPoint.id == valid_columns['id']).first()
                if not existing:
                    new_anchor_point = AnchorPoint(**valid_columns)
                    local_db.add(new_anchor_point)
                else:
                    for key, value in valid_columns.items():
                        if key != 'id' and hasattr(existing, key):
                            setattr(existing, key, value)
            
            local_db.commit()
            print("Anchor points synced successfully")
            
            # Sync anchor point layers
            remote_cursor.execute("SELECT * FROM anchor_point_layers")
            columns = [desc[0] for desc in remote_cursor.description]
            anchor_point_layers_data = remote_cursor.fetchall()
            print(f"Found {len(anchor_point_layers_data)} anchor point layer records")
            
            for row in anchor_point_layers_data:
                anchor_point_layer_dict = dict(zip(columns, row))
                valid_columns = {key: value for key, value in anchor_point_layer_dict.items() if hasattr(AnchorPointLayer, key)}
                existing = local_db.query(AnchorPointLayer).filter(AnchorPointLayer.id == valid_columns['id']).first()
                if not existing:
                    new_anchor_point_layer = AnchorPointLayer(**valid_columns)
                    local_db.add(new_anchor_point_layer)
                else:
                    for key, value in valid_columns.items():
                        if key != 'id' and hasattr(existing, key):
                            setattr(existing, key, value)
            
            local_db.commit()
            print("Anchor point layers synced successfully")
            
            return {"message": "Database sync completed successfully", "synced_records": {
                "ammunition": len(ammunition_data),
                "materials": len(materials_data),
                "vests": len(vests_data),
                "vest_layers": len(vest_layers_data),
                "test_sessions": len(test_sessions_data),
                "shot_data": len(shot_data),
                "model_runs": len(model_runs_data),
                "predictions": len(predictions_data),
                "protocols": len(protocols_data),
                "locations": len(locations_data),
                "anchor_points": len(anchor_points_data),
                "anchor_point_layers": len(anchor_point_layers_data)
            }}
            
        except Exception as e:
            local_db.rollback()
            print(f"Sync error: {str(e)}")
            import traceback
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")
        finally:
            local_db.close()
            remote_cursor.close()
            remote_conn.close()
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to connect to remote database: {str(e)}")


@router.post("/reset-database")
def reset_database(
    current_user: User = Depends(get_current_active_user)
):
    """Reset local database to match remote database (delete local data + sync fresh)."""
    # Check if user is admin
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Remote database connection details
    remote_db_url = os.getenv("REMOTE_DATABASE_URL")
    if not remote_db_url:
        raise HTTPException(status_code=500, detail="REMOTE_DATABASE_URL not configured")
    
    local_db: Session = SessionLocal()
    
    try:
        # Delete all local data
        print("Deleting local database data...")
        local_db.query(AnchorPointLayer).delete()
        local_db.query(AnchorPoint).delete()
        local_db.query(Location).delete()
        local_db.query(Protocol).delete()
        local_db.query(Prediction).delete()
        local_db.query(ModelRun).delete()
        local_db.query(ShotData).delete()
        local_db.query(VestLayer).delete()
        local_db.query(Vest).delete()
        local_db.query(TestSession).delete()
        local_db.query(Material).delete()
        local_db.query(Ammunition).delete()
        local_db.commit()
        print("Local data deleted successfully")
        
        # Connect to remote database
        print(f"Attempting to connect to remote database: {remote_db_url}")
        remote_conn = psycopg2.connect(remote_db_url, connect_timeout=10)
        remote_cursor = remote_conn.cursor()
        print("Successfully connected to remote database")
        
        try:
            # Sync ammunition
            print("Syncing ammunition...")
            remote_cursor.execute("SELECT * FROM ammunition")
            columns = [desc[0] for desc in remote_cursor.description]
            ammunition_data = remote_cursor.fetchall()
            print(f"Found {len(ammunition_data)} ammunition records")
            
            for row in ammunition_data:
                ammo_dict = dict(zip(columns, row))
                new_ammo = Ammunition(**ammo_dict)
                local_db.add(new_ammo)
            
            local_db.commit()
            print("Ammunition synced successfully")
            
            # Sync materials
            remote_cursor.execute("SELECT * FROM materials")
            columns = [desc[0] for desc in remote_cursor.description]
            materials_data = remote_cursor.fetchall()
            
            for row in materials_data:
                material_dict = dict(zip(columns, row))
                valid_columns = {key: value for key, value in material_dict.items() if hasattr(Material, key)}
                new_material = Material(**valid_columns)
                local_db.add(new_material)
            
            local_db.commit()
            print("Materials synced successfully")
            
            # Sync vests
            remote_cursor.execute("SELECT * FROM vests")
            columns = [desc[0] for desc in remote_cursor.description]
            vests_data = remote_cursor.fetchall()
            
            for row in vests_data:
                vest_dict = dict(zip(columns, row))
                valid_columns = {key: value for key, value in vest_dict.items() if hasattr(Vest, key)}
                new_vest = Vest(**valid_columns)
                local_db.add(new_vest)
            
            local_db.commit()
            print("Vests synced successfully")
            
            # Sync vest layers
            remote_cursor.execute("SELECT * FROM vest_layers")
            columns = [desc[0] for desc in remote_cursor.description]
            vest_layers_data = remote_cursor.fetchall()
            
            for row in vest_layers_data:
                vest_layer_dict = dict(zip(columns, row))
                valid_columns = {key: value for key, value in vest_layer_dict.items() if hasattr(VestLayer, key)}
                new_vest_layer = VestLayer(**valid_columns)
                local_db.add(new_vest_layer)
            
            local_db.commit()
            print("Vest layers synced successfully")
            
            # Sync test sessions
            remote_cursor.execute("SELECT * FROM test_sessions")
            columns = [desc[0] for desc in remote_cursor.description]
            test_sessions_data = remote_cursor.fetchall()
            
            for row in test_sessions_data:
                test_session_dict = dict(zip(columns, row))
                valid_columns = {key: value for key, value in test_session_dict.items() if hasattr(TestSession, key)}
                new_test_session = TestSession(**valid_columns)
                local_db.add(new_test_session)
            
            local_db.commit()
            print("Test sessions synced successfully")
            
            # Sync shot data
            remote_cursor.execute("SELECT * FROM shot_data")
            columns = [desc[0] for desc in remote_cursor.description]
            shot_data = remote_cursor.fetchall()
            
            for row in shot_data:
                shot_dict = dict(zip(columns, row))
                valid_columns = {key: value for key, value in shot_dict.items() if hasattr(ShotData, key)}
                new_shot = ShotData(**valid_columns)
                local_db.add(new_shot)
            
            local_db.commit()
            print("Shot data synced successfully")
            
            # Sync model runs
            remote_cursor.execute("SELECT * FROM model_runs")
            columns = [desc[0] for desc in remote_cursor.description]
            model_runs_data = remote_cursor.fetchall()
            
            for row in model_runs_data:
                model_run_dict = dict(zip(columns, row))
                valid_columns = {key: value for key, value in model_run_dict.items() if hasattr(ModelRun, key)}
                new_model_run = ModelRun(**valid_columns)
                local_db.add(new_model_run)
            
            local_db.commit()
            print("Model runs synced successfully")
            
            # Sync predictions
            remote_cursor.execute("SELECT * FROM predictions")
            columns = [desc[0] for desc in remote_cursor.description]
            predictions_data = remote_cursor.fetchall()
            
            for row in predictions_data:
                prediction_dict = dict(zip(columns, row))
                valid_columns = {key: value for key, value in prediction_dict.items() if hasattr(Prediction, key)}
                new_prediction = Prediction(**valid_columns)
                local_db.add(new_prediction)
            
            local_db.commit()
            print("Predictions synced successfully")
            
            # Sync protocols
            remote_cursor.execute("SELECT * FROM protocols")
            columns = [desc[0] for desc in remote_cursor.description]
            protocols_data = remote_cursor.fetchall()
            
            for row in protocols_data:
                protocol_dict = dict(zip(columns, row))
                valid_columns = {key: value for key, value in protocol_dict.items() if hasattr(Protocol, key)}
                new_protocol = Protocol(**valid_columns)
                local_db.add(new_protocol)
            
            local_db.commit()
            print("Protocols synced successfully")
            
            # Sync locations
            remote_cursor.execute("SELECT * FROM locations")
            columns = [desc[0] for desc in remote_cursor.description]
            locations_data = remote_cursor.fetchall()
            
            for row in locations_data:
                location_dict = dict(zip(columns, row))
                valid_columns = {key: value for key, value in location_dict.items() if hasattr(Location, key)}
                new_location = Location(**valid_columns)
                local_db.add(new_location)
            
            local_db.commit()
            print("Locations synced successfully")
            
            # Sync anchor points
            remote_cursor.execute("SELECT * FROM anchor_points")
            columns = [desc[0] for desc in remote_cursor.description]
            anchor_points_data = remote_cursor.fetchall()
            print(f"Found {len(anchor_points_data)} anchor point records")
            
            for row in anchor_points_data:
                anchor_point_dict = dict(zip(columns, row))
                valid_columns = {key: value for key, value in anchor_point_dict.items() if hasattr(AnchorPoint, key)}
                new_anchor_point = AnchorPoint(**valid_columns)
                local_db.add(new_anchor_point)
            
            local_db.commit()
            print("Anchor points synced successfully")
            
            # Sync anchor point layers
            remote_cursor.execute("SELECT * FROM anchor_point_layers")
            columns = [desc[0] for desc in remote_cursor.description]
            anchor_point_layers_data = remote_cursor.fetchall()
            print(f"Found {len(anchor_point_layers_data)} anchor point layer records")
            
            for row in anchor_point_layers_data:
                anchor_point_layer_dict = dict(zip(columns, row))
                valid_columns = {key: value for key, value in anchor_point_layer_dict.items() if hasattr(AnchorPointLayer, key)}
                new_anchor_point_layer = AnchorPointLayer(**valid_columns)
                local_db.add(new_anchor_point_layer)
            
            local_db.commit()
            print("Anchor point layers synced successfully")
            
            return {"message": "Database reset completed successfully", "synced_records": {
                "ammunition": len(ammunition_data),
                "materials": len(materials_data),
                "vests": len(vests_data),
                "vest_layers": len(vest_layers_data),
                "test_sessions": len(test_sessions_data),
                "shot_data": len(shot_data),
                "model_runs": len(model_runs_data),
                "predictions": len(predictions_data),
                "protocols": len(protocols_data),
                "locations": len(locations_data),
                "anchor_points": len(anchor_points_data),
                "anchor_point_layers": len(anchor_point_layers_data)
            }}
            
        except Exception as e:
            local_db.rollback()
            print(f"Sync error: {str(e)}")
            import traceback
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Reset failed: {str(e)}")
        finally:
            local_db.close()
            remote_cursor.close()
            remote_conn.close()
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reset database: {str(e)}")


@router.post("/backup")
def create_backup(
    current_user: User = Depends(get_current_active_user)
):
    """Create a backup of the database and storage files."""
    # Check if user is admin
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    try:
        # Create backup directory in storage
        backup_dir = os.path.join(settings.upload_dir, 'backups')
        os.makedirs(backup_dir, exist_ok=True)

        backup_filename = f"deltadash_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        backup_path = os.path.join(backup_dir, backup_filename)

        with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Dump the database
            db_backup_file = os.path.join(backup_dir, 'database_dump.sql')
            db_url = os.getenv("DATABASE_URL")

            # Parse DATABASE_URL to get connection details
            # Format: postgresql://user:password@host:port/database
            if db_url:
                # Use pg_dump to create a database dump
                try:
                    # Check if pg_dump is available
                    subprocess.run(['which', 'pg_dump'], capture_output=True, check=True)
                    
                    subprocess.run(
                        ['pg_dump', db_url, '-f', db_backup_file],
                        check=True,
                        capture_output=True
                    )
                    
                    # Compress the SQL file with gzip if available
                    try:
                        subprocess.run(['which', 'gzip'], capture_output=True, check=True)
                        compressed_file = db_backup_file + '.gz'
                        subprocess.run(
                            ['gzip', '-9', db_backup_file],
                            check=True,
                            capture_output=True
                        )
                        zipf.write(compressed_file, 'database_dump.sql.gz')
                        os.remove(compressed_file)  # Clean up compressed file
                    except subprocess.CalledProcessError:
                        # gzip not available, add uncompressed file
                        zipf.write(db_backup_file, 'database_dump.sql')
                    
                    # Clean up the SQL file if it still exists
                    if os.path.exists(db_backup_file):
                        os.remove(db_backup_file)
                        
                except subprocess.CalledProcessError as e:
                    # pg_dump failed, try to provide more detailed error
                    stderr = e.stderr.decode() if e.stderr else str(e)
                    print(f"pg_dump failed: {stderr}")
                    raise HTTPException(status_code=500, detail=f"Database dump failed: {stderr}")

            # Add storage files to the zip
            storage_dirs = [
                settings.material_docs_dir,
                settings.upload_dir,
                settings.reports_dir,
                settings.model_artifacts_dir
            ]
            
            # Exclude backups directory from backup to prevent exponential growth
            backup_dir = os.path.join(settings.upload_dir, 'backups')

            for storage_dir in storage_dirs:
                if os.path.exists(storage_dir):
                    # Calculate directory size before zipping
                    dir_size = 0
                    file_count = 0
                    for root, dirs, files in os.walk(storage_dir):
                        # Skip backups directory
                        if backup_dir in root:
                            continue
                        for file in files:
                            file_path = os.path.join(root, file)
                            file_size = os.path.getsize(file_path)
                            dir_size += file_size
                            file_count += 1
                    print(f"Backup: Adding {storage_dir} - {file_count} files, {dir_size / (1024*1024):.2f} MB")
                    
                    for root, dirs, files in os.walk(storage_dir):
                        # Skip backups directory
                        if backup_dir in root:
                            continue
                        for file in files:
                            file_path = os.path.join(root, file)
                            arcname = os.path.relpath(file_path, os.path.dirname(storage_dir))
                            zipf.write(file_path, arcname)

        return {"message": "Backup created successfully", "filename": backup_filename}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Backup failed: {str(e)}")


@router.get("/backups")
def list_backups(
    current_user: User = Depends(get_current_active_user)
):
    """List available backups."""
    # Check if user is admin
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    try:
        backup_dir = os.path.join(settings.upload_dir, 'backups')
        if not os.path.exists(backup_dir):
            return {"backups": []}

        backups = []
        for filename in os.listdir(backup_dir):
            if filename.endswith('.zip'):
                file_path = os.path.join(backup_dir, filename)
                backups.append({
                    "filename": filename,
                    "size": os.path.getsize(file_path),
                    "created": datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat()
                })

        # Sort by creation time, newest first
        backups.sort(key=lambda x: x['created'], reverse=True)
        return {"backups": backups}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list backups: {str(e)}")


@router.get("/backups/{filename}")
def download_backup(
    filename: str,
    current_user: User = Depends(get_current_active_user)
):
    """Download a backup file."""
    # Check if user is admin
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    try:
        backup_dir = os.path.join(settings.upload_dir, 'backups')
        backup_path = os.path.join(backup_dir, filename)

        if not os.path.exists(backup_path):
            raise HTTPException(status_code=404, detail="Backup not found")

        return FileResponse(
            backup_path,
            media_type='application/zip',
            filename=filename,
            headers={
                'Content-Disposition': f'attachment; filename="{filename}"'
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to download backup: {str(e)}")


@router.delete("/backups/{filename}")
def delete_backup(
    filename: str,
    current_user: User = Depends(get_current_active_user)
):
    """Delete a backup file."""
    # Check if user is admin
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    try:
        backup_dir = os.path.join(settings.upload_dir, 'backups')
        backup_path = os.path.join(backup_dir, filename)

        if not os.path.exists(backup_path):
            raise HTTPException(status_code=404, detail="Backup not found")

        os.remove(backup_path)
        return {"message": "Backup deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete backup: {str(e)}")


@router.post("/backups/upload")
def upload_backup(
    backup_file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user)
):
    """Upload a backup file to storage."""
    # Check if user is admin
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    try:
        # Create backup directory in storage
        backup_dir = os.path.join(settings.upload_dir, 'backups')
        os.makedirs(backup_dir, exist_ok=True)

        # Save the uploaded file in chunks to handle large files
        backup_path = os.path.join(backup_dir, backup_file.filename)
        chunk_size = 8192
        with open(backup_path, 'wb') as f:
            while True:
                chunk = backup_file.file.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)

        file_size = os.path.getsize(backup_path)
        return {"message": "Backup uploaded successfully", "filename": backup_file.filename, "size": file_size}

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to upload backup: {str(e)}")


@router.post("/backups/upload-base64")
def upload_backup_base64(
    filename: str = Body(...),
    content: str = Body(...),
    current_user: User = Depends(get_current_active_user)
):
    """Upload a backup file via base64 encoding."""
    # Check if user is admin
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    try:
        import base64

        # Create backup directory in storage
        backup_dir = os.path.join(settings.upload_dir, 'backups')
        os.makedirs(backup_dir, exist_ok=True)

        # Decode base64 and save
        backup_path = os.path.join(backup_dir, filename)
        with open(backup_path, 'wb') as f:
            f.write(base64.b64decode(content))

        file_size = os.path.getsize(backup_path)

        # Keep only the 5 most recent backups
        backups = sorted(
            [os.path.join(backup_dir, f) for f in os.listdir(backup_dir) if f.endswith('.zip')],
            key=os.path.getmtime,
            reverse=True
        )
        for old_backup in backups[5:]:
            os.remove(old_backup)

        return {"message": "Backup uploaded successfully", "filename": filename, "size": file_size}

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to upload backup: {str(e)}")


@router.put("/backups/upload-chunk")
def upload_backup_chunk(
    filename: str,
    chunk_index: int,
    total_chunks: int,
    chunk: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user)
):
    """Upload a chunk of a backup file."""
    # Check if user is admin
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    try:
        # Create chunks directory in storage
        chunks_dir = os.path.join(settings.upload_dir, 'backup_chunks')
        os.makedirs(chunks_dir, exist_ok=True)

        # Save the chunk
        chunk_filename = f"{filename}.chunk_{chunk_index}_{total_chunks}"
        chunk_path = os.path.join(chunks_dir, chunk_filename)
        with open(chunk_path, 'wb') as f:
            f.write(chunk.file.read())

        return {"message": "Chunk uploaded successfully", "chunk_index": chunk_index}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload chunk: {str(e)}")


@router.post("/backups/assemble")
def assemble_backup(
    filename: str = Body(...),
    total_chunks: int = Body(...),
    current_user: User = Depends(get_current_active_user)
):
    """Assemble uploaded chunks into a complete backup file."""
    # Check if user is admin
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    try:
        # Create backup directory in storage
        backup_dir = os.path.join(settings.upload_dir, 'backups')
        os.makedirs(backup_dir, exist_ok=True)

        chunks_dir = os.path.join(settings.upload_dir, 'backup_chunks')
        backup_path = os.path.join(backup_dir, filename)

        # Assemble chunks
        with open(backup_path, 'wb') as outfile:
            for chunk_index in range(total_chunks):
                chunk_filename = f"{filename}.chunk_{chunk_index}_{total_chunks}"
                chunk_path = os.path.join(chunks_dir, chunk_filename)

                if not os.path.exists(chunk_path):
                    raise HTTPException(status_code=400, detail=f"Chunk {chunk_index} missing")

                with open(chunk_path, 'rb') as infile:
                    outfile.write(infile.read())

                # Delete chunk after assembly
                os.remove(chunk_path)

        return {"message": "Backup assembled successfully", "filename": filename}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to assemble backup: {str(e)}")


def perform_restore(task_id: str, backup_path: str, temp_dir: str):
    """Background task to perform the actual restore."""
    print(f"[BACKGROUND TASK] Starting restore for task {task_id}")
    print(f"[BACKGROUND TASK] backup_path: {backup_path}")
    print(f"[BACKGROUND TASK] temp_dir: {temp_dir}")
    print(f"[BACKGROUND TASK] File exists: {os.path.exists(backup_path)}")
    
    try:
        restore_progress[task_id] = {"status": "extracting", "progress": 10, "message": "Extracting backup file..."}
        print(f"[BACKGROUND TASK] Progress updated to extracting")
        
        # Extract the zip file
        with zipfile.ZipFile(backup_path, 'r') as zipf:
            zipf.extractall(temp_dir)
        print(f"[BACKGROUND TASK] Extraction complete")
        
        restore_progress[task_id] = {"status": "restoring_db", "progress": 30, "message": "Restoring database..."}
        print(f"[BACKGROUND TASK] Progress updated to restoring_db")
        
        # Restore the database
        db_backup_file = os.path.join(temp_dir, 'database_dump.sql')
        db_backup_file_gz = os.path.join(temp_dir, 'database_dump.sql.gz')
        print(f"[BACKGROUND TASK] Checking for db_backup_file: {db_backup_file}")
        print(f"[BACKGROUND TASK] db_backup_file exists: {os.path.exists(db_backup_file)}")
        print(f"[BACKGROUND TASK] Checking for db_backup_file_gz: {db_backup_file_gz}")
        print(f"[BACKGROUND TASK] db_backup_file_gz exists: {os.path.exists(db_backup_file_gz)}")

        # Decompress if needed
        if os.path.exists(db_backup_file_gz):
            print(f"[BACKGROUND TASK] Decompressing SQL file...")
            subprocess.run(
                ['gunzip', '-k', db_backup_file_gz],
                check=True,
                capture_output=True
            )
            print(f"[BACKGROUND TASK] Decompression complete")

        if os.path.exists(db_backup_file):
            db_url = os.getenv("DATABASE_URL")
            print(f"[BACKGROUND TASK] DATABASE_URL found: {bool(db_url)}")
            if db_url:
                try:
                    print(f"[BACKGROUND TASK] Parsing DATABASE_URL...")
                    # Parse DATABASE_URL to get connection details
                    match = re.match(r'postgresql://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)', db_url)
                    if not match:
                        print(f"[BACKGROUND TASK] DATABASE_URL format invalid")
                        restore_progress[task_id] = {"status": "error", "progress": 0, "message": "Invalid DATABASE_URL format"}
                        return
                    
                    user, password, host, port, database = match.groups()
                    print(f"[BACKGROUND TASK] Parsed: host={host}, port={port}, database={database}, user={user}")
                    
                    # Set environment variables for psql
                    env = os.environ.copy()
                    env['PGPASSWORD'] = password
                    print(f"[BACKGROUND TASK] PGPASSWORD set")
                    
                    print(f"[BACKGROUND TASK] Starting psql command with Popen...")
                    # Use Popen with proper stream handling
                    process = subprocess.Popen(
                        ['psql', '-h', host, '-p', port, '-U', user, '-d', database, '-f', db_backup_file],
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        env=env,
                        text=True
                    )
                    
                    print(f"[BACKGROUND TASK] Waiting for psql to complete...")
                    stdout, stderr = process.communicate(timeout=300)
                    
                    if process.returncode != 0:
                        print(f"[BACKGROUND TASK] psql failed with return code {process.returncode}")
                        print(f"[BACKGROUND TASK] stderr: {stderr}")
                        raise Exception(f"psql failed: {stderr}")
                    
                    print(f"[BACKGROUND TASK] psql completed successfully")
                    
                    restore_progress[task_id] = {"status": "restoring_files", "progress": 70, "message": "Restoring storage files..."}
                except Exception as e:
                    print(f"[BACKGROUND TASK] Database restore error: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    restore_progress[task_id] = {"status": "error", "progress": 0, "message": f"Database restore failed: {str(e)}"}
                    return
        
        # Restore storage files
        storage_dirs = [
            settings.material_docs_dir,
            settings.upload_dir,
            settings.reports_dir,
            settings.model_artifacts_dir
        ]
        
        for i, storage_dir in enumerate(storage_dirs):
            os.makedirs(storage_dir, exist_ok=True)
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
            
            # Update progress
            progress = 70 + ((i + 1) / len(storage_dirs)) * 25
            restore_progress[task_id] = {"status": "restoring_files", "progress": int(progress), "message": f"Restoring storage files ({i+1}/{len(storage_dirs)})..."}
        
        restore_progress[task_id] = {"status": "completed", "progress": 100, "message": "Restore completed successfully"}
        
    except Exception as e:
        restore_progress[task_id] = {"status": "error", "progress": 0, "message": f"Restore failed: {str(e)}"}
    finally:
        # Clean up temporary directory
        shutil.rmtree(temp_dir, ignore_errors=True)


@router.post("/restore")
def restore_backup(
    filename: str = Body(..., embed=True),
    current_user: User = Depends(get_current_active_user)
):
    """Restore a backup of the database and storage files from storage."""
    # Check if user is admin
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    try:
        print("[RESTORE ENDPOINT] Starting restore endpoint")
        # Create a unique task ID
        task_id = str(uuid.uuid4())
        print(f"[RESTORE ENDPOINT] Task ID: {task_id}")

        # Get backup path from storage
        backup_dir = os.path.join(settings.upload_dir, 'backups')
        backup_path = os.path.join(backup_dir, filename)
        print(f"[RESTORE ENDPOINT] backup_path: {backup_path}")

        if not os.path.exists(backup_path):
            raise HTTPException(status_code=404, detail="Backup file not found")

        # Create a temporary directory for extraction
        temp_dir = tempfile.mkdtemp()
        print(f"[RESTORE ENDPOINT] temp_dir: {temp_dir}")

        # Initialize progress
        restore_progress[task_id] = {"status": "starting", "progress": 0, "message": "Starting restore..."}
        print(f"[RESTORE ENDPOINT] Progress initialized for task {task_id}")

        # Start background thread
        print(f"[RESTORE ENDPOINT] Starting background thread...")
        thread = threading.Thread(target=perform_restore, args=(task_id, backup_path, temp_dir))
        thread.daemon = True
        thread.start()
        print(f"[RESTORE ENDPOINT] Background thread started")

        return {"task_id": task_id, "message": "Restore started"}

    except HTTPException:
        raise
    except Exception as e:
        print(f"[RESTORE ENDPOINT] Error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to start restore: {str(e)}")


@router.get("/restore/progress/{task_id}")
def get_restore_progress(
    task_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get the progress of a restore operation."""
    if task_id not in restore_progress:
        return {"status": "error", "progress": 0, "message": "Task not found or expired"}

    progress = restore_progress[task_id]
    
    # Clean up old completed tasks to prevent memory leaks
    if progress.get("status") in ["completed", "error"]:
        # Keep for 5 minutes then delete
        if "completed_at" not in progress:
            progress["completed_at"] = datetime.now().isoformat()
        else:
            completed_time = datetime.fromisoformat(progress["completed_at"])
            if (datetime.now() - completed_time).total_seconds() > 300:
                del restore_progress[task_id]
    
    return progress


@router.get("/version")
def get_version(
    current_user: User = Depends(get_current_user)
):
    """Get the current version from environment variable or git commits."""
    # Use environment variable if explicitly set (production override)
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


@router.get("/alembic/status")
def get_alembic_status(
    current_user: User = Depends(get_current_active_user)
):
    """Get the current alembic migration status."""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    try:
        db: Session = SessionLocal()
        try:
            # Get current version from alembic_version table
            result = db.execute(text("SELECT version_num FROM alembic_version"))
            versions = [row[0] for row in result.fetchall()]
            
            # Get migration files - fix path calculation
            # The migrations directory is at backend/migrations/versions
            # admin.py is at backend/app/api/v1/admin.py
            # So we need to go up 3 levels from __file__ to get to backend, then into migrations/versions
            backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
            migrations_dir = os.path.join(backend_dir, 'migrations', 'versions')
            
            migration_files = []
            if os.path.exists(migrations_dir):
                migration_files = [f for f in os.listdir(migrations_dir) if f.endswith('.py') and not f.startswith('__')]
            else:
                # Try alternative path
                migrations_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'migrations', 'versions'))
                if os.path.exists(migrations_dir):
                    migration_files = [f for f in os.listdir(migrations_dir) if f.endswith('.py') and not f.startswith('__')]
            
            return {
                "current_versions": versions,
                "migration_files": migration_files,
                "multiple_heads": len(versions) > 1
            }
        finally:
            db.close()
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to get alembic status: {str(e)}")


@router.post("/alembic/fix-heads")
def fix_alembic_heads(
    target_version: str = Body(..., embed=True),
    current_user: User = Depends(get_current_active_user)
):
    """Fix alembic migration heads by setting a single head."""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    try:
        db: Session = SessionLocal()
        try:
            # Delete all rows from alembic_version
            db.execute(text("DELETE FROM alembic_version"))
            
            # Insert the target version
            db.execute(text("INSERT INTO alembic_version (version_num) VALUES (:version)"), {"version": target_version})
            
            db.commit()
            return {"message": f"Alembic heads fixed. Set to version: {target_version}"}
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to fix alembic heads: {str(e)}")
        finally:
            db.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fix alembic heads: {str(e)}")


@router.post("/alembic/upgrade")
def run_alembic_upgrade(
    current_user: User = Depends(get_current_active_user)
):
    """Manually run alembic upgrade to head."""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    try:
        from alembic.config import Config
        from alembic.command import upgrade
        
        # Create alembic config
        # admin.py is at app/api/v1/admin.py - go up 3 levels to get project root
        backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
        migrations_path = os.path.join(backend_dir, 'migrations')
        if not os.path.exists(migrations_path):
            # Docker fallback: __file__ is /app/app/api/v1/admin.py, need /app
            backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
            migrations_path = os.path.join(backend_dir, 'migrations')
        config = Config(os.path.join(backend_dir, 'alembic.ini'))
        config.set_main_option("sqlalchemy.url", os.getenv("DATABASE_URL"))
        config.set_main_option("script_location", migrations_path)
        
        # Run the upgrade
        upgrade(config, "head")
        
        return {"message": "Migration successful"}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Migration failed: {str(e)}")


@router.post("/alembic/execute-sql")
def execute_sql(
    sql: str = Body(..., embed=True),
    current_user: User = Depends(get_current_active_user)
):
    """Execute a custom SQL statement against the database."""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    try:
        db: Session = SessionLocal()
        try:
            result = db.execute(text(sql))
            db.commit()
            
            # Get the results if it's a SELECT query
            if sql.strip().upper().startswith('SELECT'):
                rows = result.fetchall()
                columns = result.keys()
                return {
                    "message": "Query executed successfully",
                    "rows": [dict(zip(columns, row)) for row in rows]
                }
            else:
                return {"message": f"SQL executed successfully. Rows affected: {result.rowcount}"}
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"SQL execution failed: {str(e)}")
        finally:
            db.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"SQL execution failed: {str(e)}")
