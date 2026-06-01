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
            
            return {"message": "Database sync completed successfully", "synced_records": {
                "ammunition": len(ammunition_data),
                "materials": len(materials_data),
                "vests": len(vests_data),
                "vest_layers": len(vest_layers_data),
                "test_sessions": len(test_sessions_data),
                "shot_data": len(shot_data)
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
                # Use pg_dump to create a database dump, then compress with gzip
                try:
                    subprocess.run(
                        ['pg_dump', db_url, '-f', db_backup_file],
                        check=True,
                        capture_output=True
                    )
                    # Compress the SQL file with gzip
                    compressed_file = db_backup_file + '.gz'
                    subprocess.run(
                        ['gzip', '-9', db_backup_file],
                        check=True,
                        capture_output=True
                    )
                    zipf.write(compressed_file, 'database_dump.sql.gz')
                    os.remove(compressed_file)  # Clean up compressed file
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
            filename=filename
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

    return restore_progress[task_id]


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
