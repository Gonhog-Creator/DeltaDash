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
from app.db.models.prediction import Prediction
from app.db.models.protocol import Protocol
from app.db.models.location import Location
from app.db.models.anchor_point import AnchorPoint, AnchorPointLayer
from app.db.models.geometry import Geometry
from app.db.models.geometry_material_config import GeometryMaterialConfig
from app.db.models.cover import Cover
from app.api.v1.auth import get_current_active_user, get_current_user
from app.db.models.user import User
from app.core.config import settings
from app.services.seed_geometries import seed_geometries
import psycopg2
import os
import zipfile
import tempfile
import shutil
import subprocess
import re
import threading
from typing import Optional, Dict, List, Any
from datetime import datetime
import uuid
from sqlalchemy import text
from pydantic import BaseModel

router = APIRouter()

# Global dictionary to track restore progress
restore_progress: Dict[str, dict] = {}

# Pydantic models for sync confirmation
class FieldChange(BaseModel):
    field: str
    old_value: Any
    new_value: Any

class RecordChange(BaseModel):
    id: Any
    change_type: str  # 'new', 'updated', 'deleted'
    changes: Optional[List[FieldChange]] = None
    record_data: Optional[Dict[str, Any]] = None

class EntityChanges(BaseModel):
    entity_name: str
    new_records: List[RecordChange]
    updated_records: List[RecordChange]
    deleted_records: List[RecordChange]

class SyncPreview(BaseModel):
    changes: List[EntityChanges]
    summary: Dict[str, int]

class SyncConfirmation(BaseModel):
    confirmed_changes: Dict[str, Dict[str, List[str]]]  # {entity_name: {change_type: [record_ids]}}

class ResetRequest(BaseModel):
    entities: Optional[List[str]] = None  # If None, reset all entities

def compare_records(existing_record: Any, remote_data: Dict[str, Any], model_class: Any) -> List[FieldChange]:
    """Compare existing record with remote data and return field changes."""
    changes = []
    # Ignore timestamp fields as they will differ due to timezone
    ignore_fields = {'created_at', 'updated_at'}
    
    for key, new_value in remote_data.items():
        if key == 'id' or key in ignore_fields:
            continue
        if hasattr(existing_record, key):
            old_value = getattr(existing_record, key)
            # Treat False and None as equivalent for boolean fields
            if isinstance(old_value, bool) and new_value is None:
                continue
            if old_value is None and isinstance(new_value, bool):
                continue
            # Normalize UUID comparison to handle string vs UUID object mismatch
            if isinstance(old_value, uuid.UUID) or isinstance(new_value, uuid.UUID):
                if str(old_value) != str(new_value):
                    changes.append(FieldChange(field=key, old_value=old_value, new_value=new_value))
            elif old_value != new_value:
                changes.append(FieldChange(field=key, old_value=old_value, new_value=new_value))
    return changes

def serialize_value(value: Any) -> Any:
    """Convert non-serializable types to serializable formats."""
    if isinstance(value, memoryview):
        return f"<binary data {len(value)} bytes>"
    elif isinstance(value, bytes):
        return f"<binary data {len(value)} bytes>"
    elif isinstance(value, datetime):
        return value.isoformat()
    elif isinstance(value, uuid.UUID):
        return str(value)
    elif value is None:
        return None
    else:
        try:
            str(value)
            return value
        except:
            return str(value)

def get_preview_changes(remote_cursor, local_db: Session) -> SyncPreview:
    """Generate preview of all changes that would occur during sync."""
    all_changes = []
    summary = {"new": 0, "updated": 0, "deleted": 0}
    
    # Define entities to sync
    entities = [
        ("ammunition", Ammunition, "SELECT * FROM ammunition"),
        ("materials", Material, "SELECT * FROM materials"),
        ("vests", Vest, "SELECT * FROM vests"),
        ("vest_layers", VestLayer, "SELECT * FROM vest_layers"),
        ("test_sessions", TestSession, "SELECT * FROM test_sessions"),
        ("shot_data", ShotData, "SELECT * FROM shot_data"),
        ("protocols", Protocol, "SELECT * FROM protocols"),
        ("locations", Location, "SELECT * FROM locations"),
        ("geometries", Geometry, "SELECT * FROM geometries"),
        ("geometry_material_configs", GeometryMaterialConfig, "SELECT * FROM geometry_material_configs"),
        ("covers", Cover, "SELECT * FROM covers"),
        ("anchor_points", AnchorPoint, "SELECT * FROM anchor_points"),
        ("anchor_point_layers", AnchorPointLayer, "SELECT * FROM anchor_point_layers"),
    ]
    
    for idx, (entity_name, model_class, query) in enumerate(entities):
        try:
            remote_cursor.execute(query)
            columns = [desc[0] for desc in remote_cursor.description]
            remote_data = remote_cursor.fetchall()
            
            new_records = []
            updated_records = []
            deleted_records = []
            
            # Get all local records as a hash map for O(1) lookups
            local_records = {}
            local_query = local_db.query(model_class).all()
            for item in local_query:
                local_records[str(getattr(item, 'id'))] = item
            
            remote_ids = set()
            for idx2, row in enumerate(remote_data):
                if idx2 > 0 and idx2 % 100 == 0:
                    pass
                data_dict = dict(zip(columns, row))
                remote_id = str(data_dict.get('id'))
                remote_ids.add(remote_id)
                
                # Filter valid columns and serialize values
                valid_columns = {}
                for k, v in data_dict.items():
                    if hasattr(model_class, k):
                        valid_columns[k] = serialize_value(v)
                
                # O(1) lookup instead of database query
                existing = local_records.get(remote_id)
                
                if not existing:
                    new_records.append(RecordChange(
                        id=valid_columns['id'],
                        change_type='new',
                        record_data=valid_columns
                    ))
                    summary["new"] += 1
                else:
                    changes = compare_records(existing, valid_columns, model_class)
                    if changes:
                        # Serialize change values
                        serialized_changes = []
                        for change in changes:
                            serialized_changes.append(FieldChange(
                                field=change.field,
                                old_value=serialize_value(change.old_value),
                                new_value=serialize_value(change.new_value)
                            ))
                        updated_records.append(RecordChange(
                            id=valid_columns['id'],
                            change_type='updated',
                            changes=serialized_changes,
                            record_data=valid_columns
                        ))
                        summary["updated"] += 1
        
            # Check for deleted records
            deleted_ids = set(local_records.keys()) - remote_ids
            for deleted_id in deleted_ids:
                deleted_records.append(RecordChange(
                    id=deleted_id,
                    change_type='deleted'
                ))
                summary["deleted"] += 1
            
            
            if new_records or updated_records or deleted_records:
                all_changes.append(EntityChanges(
                    entity_name=entity_name,
                    new_records=new_records,
                    updated_records=updated_records,
                    deleted_records=deleted_records
                ))
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise
    
    return SyncPreview(changes=all_changes, summary=summary)

@router.get("/preview-sync")
def preview_sync(
    current_user: User = Depends(get_current_active_user)
):
    """Preview changes that would occur during database sync without applying them.
    
    Performs field-level comparison to detect all changes including material properties.
    """
    
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    remote_db_url = os.getenv("REMOTE_DATABASE_URL")
    if not remote_db_url:
        raise HTTPException(status_code=500, detail="REMOTE_DATABASE_URL not configured")
    
    
    try:
        remote_conn = psycopg2.connect(remote_db_url, connect_timeout=30)
        remote_conn.autocommit = True
        remote_cursor = remote_conn.cursor()
        
        local_db: Session = SessionLocal()
        
        try:
            preview = get_preview_changes(remote_cursor, local_db)
            return preview
        finally:
            local_db.close()
            remote_cursor.close()
            remote_conn.close()
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to preview sync: {str(e)}")

def get_count_preview(remote_cursor, local_db: Session) -> SyncPreview:
    """Generate a simplified preview based on record counts only."""
    all_changes = []
    summary = {"new": 0, "updated": 0, "deleted": 0}
    
    # Define entities to sync
    entities = [
        ("ammunition", Ammunition, "SELECT COUNT(*) FROM ammunition"),
        ("materials", Material, "SELECT COUNT(*) FROM materials"),
        ("vests", Vest, "SELECT COUNT(*) FROM vests"),
        ("vest_layers", VestLayer, "SELECT COUNT(*) FROM vest_layers"),
        ("test_sessions", TestSession, "SELECT COUNT(*) FROM test_sessions"),
        ("shot_data", ShotData, "SELECT COUNT(*) FROM shot_data"),
        ("protocols", Protocol, "SELECT COUNT(*) FROM protocols"),
        ("locations", Location, "SELECT COUNT(*) FROM locations"),
        ("geometries", Geometry, "SELECT COUNT(*) FROM geometries"),
        ("geometry_material_configs", GeometryMaterialConfig, "SELECT COUNT(*) FROM geometry_material_configs"),
        ("covers", Cover, "SELECT COUNT(*) FROM covers"),
        ("users", User, "SELECT COUNT(*) FROM users"),
        ("anchor_points", AnchorPoint, "SELECT COUNT(*) FROM anchor_points"),
        ("anchor_point_layers", AnchorPointLayer, "SELECT COUNT(*) FROM anchor_point_layers"),
    ]
    
    for idx, (entity_name, model_class, query) in enumerate(entities):
        try:
            # Get remote count
            remote_cursor.execute(query)
            remote_count = remote_cursor.fetchone()[0]
            
            # Get local count
            local_count = local_db.query(model_class).count()
            
            # If counts differ, add to changes (simplified - just mark as needs sync)
            if remote_count != local_count:
                diff = remote_count - local_count
                if diff > 0:
                    summary["new"] += diff
                else:
                    summary["deleted"] += abs(diff)
                
                all_changes.append(EntityChanges(
                    entity_name=entity_name,
                    new_records=[RecordChange(id="count", change_type="new", record_data={"count": remote_count})] if remote_count > local_count else [],
                    updated_records=[],
                    deleted_records=[RecordChange(id="count", change_type="deleted", record_data={"count": local_count})] if local_count > remote_count else []
                ))
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise
    
    return SyncPreview(changes=all_changes, summary=summary)

@router.post("/sync-database")
def sync_database(
    confirmation: Optional[SyncConfirmation] = None,
    current_user: User = Depends(get_current_active_user)
):
    """Sync local database with remote database (pull only).
    
    If confirmation is provided, only applies the confirmed changes.
    If confirmation is not provided, requires preview first.
    """
    # Check if user is admin
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Remote database connection details
    remote_db_url = os.getenv("REMOTE_DATABASE_URL")
    if not remote_db_url:
        raise HTTPException(status_code=500, detail="REMOTE_DATABASE_URL not configured")
    
    # If no confirmation provided, require preview first
    if confirmation is None:
        raise HTTPException(
            status_code=400, 
            detail="Please call /preview-sync first to see changes, then provide confirmation"
        )
    
    try:
        # Connect to remote database
        remote_conn = psycopg2.connect(remote_db_url, connect_timeout=10)
        remote_cursor = remote_conn.cursor()
        
        # Get local database session
        local_db: Session = SessionLocal()
        
        try:
            applied_changes = {"new": 0, "updated": 0, "deleted": 0}
            
            # Initialize data variables
            ammunition_data = []
            materials_data = []
            vests_data = []
            vest_layers_data = []
            test_sessions_data = []
            shot_data = []
            protocols_data = []
            locations_data = []
            users_data = []
            anchor_points_data = []
            anchor_point_layers_data = []
            geometries_data = []
            geometry_material_configs_data = []
            covers_data = []
            
            # Helper function to check if a record should be synced
            def should_sync_record(entity_name: str, record_id: str, change_type: str) -> bool:
                if confirmation is None:
                    return False
                if entity_name not in confirmation.confirmed_changes:
                    return False
                if change_type not in confirmation.confirmed_changes[entity_name]:
                    return False
                
                confirmed_ids = confirmation.confirmed_changes[entity_name][change_type]
                
                # If confirmation contains the special "count" marker, sync all records of this type
                if "count" in confirmed_ids:
                    return True
                
                return str(record_id) in confirmed_ids
            
            # Helper function to check if an entity should sync all records of a type
            def should_sync_all(entity_name: str, change_type: str) -> bool:
                if confirmation is None:
                    return False
                if entity_name not in confirmation.confirmed_changes:
                    return False
                if change_type not in confirmation.confirmed_changes[entity_name]:
                    return False
                
                confirmed_ids = confirmation.confirmed_changes[entity_name][change_type]
                return "count" in confirmed_ids
            
            # Sync ammunition
            remote_cursor.execute("SELECT * FROM ammunition")
            columns = [desc[0] for desc in remote_cursor.description]
            ammunition_data = remote_cursor.fetchall()
            
            # Skip if no remote data
            if not ammunition_data:
                pass
            else:
                # Check if we should sync all records (count-based)
                sync_all_new = should_sync_all("ammunition", "new")
                sync_all_updated = should_sync_all("ammunition", "updated")
                
                # Get existing records as hash map for O(1) lookups
                existing_ammunition = {}
                for item in local_db.query(Ammunition).all():
                    existing_ammunition[str(item.id)] = item
                
                new_ammunition = []
                updated_ammunition = []
                
                for row in ammunition_data:
                    ammo_dict = dict(zip(columns, row))
                    existing = existing_ammunition.get(str(ammo_dict['id']))
                    
                    if not existing:
                        if sync_all_new or should_sync_record("ammunition", ammo_dict['id'], "new"):
                            new_ammunition.append(ammo_dict)
                    else:
                        if sync_all_updated or should_sync_record("ammunition", ammo_dict['id'], "updated"):
                            updated_ammunition.append(ammo_dict)
                
                # Bulk insert new records
                if new_ammunition:
                    local_db.bulk_insert_mappings(Ammunition, new_ammunition)
                    applied_changes["new"] += len(new_ammunition)
                
                # Bulk update existing records
                if updated_ammunition:
                    local_db.bulk_update_mappings(Ammunition, updated_ammunition)
                    applied_changes["updated"] += len(updated_ammunition)
                
                local_db.commit()
            
            # Sync materials
            remote_cursor.execute("SELECT * FROM materials")
            columns = [desc[0] for desc in remote_cursor.description]
            materials_data = remote_cursor.fetchall()
            
            # Skip if no remote data
            if not materials_data:
                pass
            else:
                # Check if we should sync all records (count-based)
                sync_all_new = should_sync_all("materials", "new")
                sync_all_updated = should_sync_all("materials", "updated")
                
                # Get existing records as hash map for O(1) lookups
                existing_materials = {}
                for item in local_db.query(Material).all():
                    existing_materials[str(item.id)] = item
                
                new_materials = []
                updated_materials = []
                
                for row in materials_data:
                    material_dict = dict(zip(columns, row))
                    # Filter out columns that don't exist in the local Material model
                    valid_columns = {key: value for key, value in material_dict.items() if hasattr(Material, key)}
                    existing = existing_materials.get(str(valid_columns['id']))
                    
                    if not existing:
                        if sync_all_new or should_sync_record("materials", valid_columns['id'], "new"):
                            new_materials.append(valid_columns)
                    else:
                        if sync_all_updated or should_sync_record("materials", valid_columns['id'], "updated"):
                            updated_materials.append(valid_columns)
                
                # Bulk insert new records
                if new_materials:
                    local_db.bulk_insert_mappings(Material, new_materials)
                    applied_changes["new"] += len(new_materials)
                
                # Bulk update existing records
                if updated_materials:
                    local_db.bulk_update_mappings(Material, updated_materials)
                    applied_changes["updated"] += len(updated_materials)
                
                local_db.commit()
            
            # Sync vests
            remote_cursor.execute("SELECT * FROM vests")
            columns = [desc[0] for desc in remote_cursor.description]
            vests_data = remote_cursor.fetchall()
            
            # Skip if no remote data
            if not vests_data:
                pass
            else:
                # Check if we should sync all records (count-based)
                sync_all_new = should_sync_all("vests", "new")
                sync_all_updated = should_sync_all("vests", "updated")
                
                # Get existing records as hash map for O(1) lookups
                existing_vests = {}
                for item in local_db.query(Vest).all():
                    existing_vests[str(item.id)] = item
                
                new_vests = []
                updated_vests = []
                
                for row in vests_data:
                    vest_dict = dict(zip(columns, row))
                    # Filter out columns that don't exist in the local Vest model
                    valid_columns = {key: value for key, value in vest_dict.items() if hasattr(Vest, key)}
                    existing = existing_vests.get(str(valid_columns['id']))
                    if not existing:
                        if sync_all_new or should_sync_record("vests", valid_columns['id'], "new"):
                            new_vests.append(valid_columns)
                    else:
                        if sync_all_updated or should_sync_record("vests", valid_columns['id'], "updated"):
                            updated_vests.append(valid_columns)
                
                if new_vests:
                    local_db.bulk_insert_mappings(Vest, new_vests)
                    applied_changes["new"] += len(new_vests)
                
                if updated_vests:
                    local_db.bulk_update_mappings(Vest, updated_vests)
                    applied_changes["updated"] += len(updated_vests)
                
                local_db.commit()
            
            # Sync vest layers
            remote_cursor.execute("SELECT * FROM vest_layers")
            columns = [desc[0] for desc in remote_cursor.description]
            vest_layers_data = remote_cursor.fetchall()
            
            # Skip if no remote data
            if not vest_layers_data:
                pass
            else:
                # Check if we should sync all records (count-based)
                sync_all_new = should_sync_all("vest_layers", "new")
                sync_all_updated = should_sync_all("vest_layers", "updated")
                
                # Get existing records as hash map for O(1) lookups
                existing_vest_layers = {}
                for item in local_db.query(VestLayer).all():
                    existing_vest_layers[str(item.id)] = item
                
                new_vest_layers = []
                updated_vest_layers = []
                
                for row in vest_layers_data:
                    layer_dict = dict(zip(columns, row))
                    # Filter out columns that don't exist in the local VestLayer model
                    valid_columns = {key: value for key, value in layer_dict.items() if hasattr(VestLayer, key)}
                    existing = existing_vest_layers.get(str(valid_columns['id']))
                    if not existing:
                        if sync_all_new or should_sync_record("vest_layers", valid_columns['id'], "new"):
                            new_vest_layers.append(valid_columns)
                    else:
                        if sync_all_updated or should_sync_record("vest_layers", valid_columns['id'], "updated"):
                            updated_vest_layers.append(valid_columns)
                
                if new_vest_layers:
                    local_db.bulk_insert_mappings(VestLayer, new_vest_layers)
                    applied_changes["new"] += len(new_vest_layers)
                
                if updated_vest_layers:
                    local_db.bulk_update_mappings(VestLayer, updated_vest_layers)
                    applied_changes["updated"] += len(updated_vest_layers)
                
                local_db.commit()
            
            # Sync test sessions
            remote_cursor.execute("SELECT * FROM test_sessions")
            columns = [desc[0] for desc in remote_cursor.description]
            test_sessions_data = remote_cursor.fetchall()
            
            # Skip if no remote data
            if not test_sessions_data:
                pass
            else:
                # Check if we should sync all records (count-based)
                sync_all_new = should_sync_all("test_sessions", "new")
                sync_all_updated = should_sync_all("test_sessions", "updated")
                
                # Get existing records as hash map for O(1) lookups
                existing_test_sessions = {}
                for item in local_db.query(TestSession).all():
                    existing_test_sessions[str(item.id)] = item
                
                new_test_sessions = []
                updated_test_sessions = []
                parent_fk_updates = []  # Track FK updates for second pass
                
                for row in test_sessions_data:
                    session_dict = dict(zip(columns, row))
                    # Filter out columns that don't exist in the local TestSession model
                    valid_columns = {key: value for key, value in session_dict.items() if hasattr(TestSession, key)}
                    existing = existing_test_sessions.get(str(valid_columns['id']))
                    
                    # Handle parent_test_group_id foreign key
                    original_parent_id = valid_columns.get('parent_test_group_id')
                    if original_parent_id is not None:
                        parent_id_str = str(original_parent_id)
                        # Check if parent exists locally or will be inserted
                        parent_exists = parent_id_str in existing_test_sessions
                        if not parent_exists:
                            # Check if parent is in new_test_sessions
                            for new_ts in new_test_sessions:
                                if str(new_ts.get('id')) == parent_id_str:
                                    parent_exists = True
                                    break
                        if not parent_exists:
                            # Set to NULL for now, will update later
                            valid_columns['parent_test_group_id'] = None
                            parent_fk_updates.append({
                                'id': valid_columns['id'],
                                'parent_test_group_id': original_parent_id
                            })
                    
                    if not existing:
                        if sync_all_new or should_sync_record("test_sessions", valid_columns['id'], "new"):
                            new_test_sessions.append(valid_columns)
                    else:
                        if sync_all_updated or should_sync_record("test_sessions", valid_columns['id'], "updated"):
                            updated_test_sessions.append(valid_columns)
                
                if new_test_sessions:
                    local_db.bulk_insert_mappings(TestSession, new_test_sessions)
                    applied_changes["new"] += len(new_test_sessions)
                
                if updated_test_sessions:
                    local_db.bulk_update_mappings(TestSession, updated_test_sessions)
                    applied_changes["updated"] += len(updated_test_sessions)
                
                local_db.commit()
                
                # Second pass: update parent_test_group_id for records that had missing parents
                if parent_fk_updates:
                    for update in parent_fk_updates:
                        parent_id_str = str(update['parent_test_group_id'])
                        # Check if parent now exists after insert
                        parent_exists = local_db.query(TestSession).filter(TestSession.id == update['parent_test_group_id']).first() is not None
                        if parent_exists:
                            local_db.query(TestSession).filter(TestSession.id == update['id']).update({
                                'parent_test_group_id': update['parent_test_group_id']
                            })
                    local_db.commit()
                
            
            # Sync shot data
            remote_cursor.execute("SELECT * FROM shot_data")
            columns = [desc[0] for desc in remote_cursor.description]
            shot_data = remote_cursor.fetchall()
            
            # Skip if no remote data
            if not shot_data:
                pass
            else:
                # Check if we should sync all records (count-based)
                sync_all_new = should_sync_all("shot_data", "new")
                sync_all_updated = should_sync_all("shot_data", "updated")
                
                # Get existing records as hash map for O(1) lookups
                existing_shot_data = {}
                for item in local_db.query(ShotData).all():
                    existing_shot_data[str(item.id)] = item
                
                # Get all test session IDs for FK validation
                existing_test_session_ids = set()
                for item in local_db.query(TestSession).all():
                    existing_test_session_ids.add(str(item.id))
                
                new_shot_data = []
                updated_shot_data = []
                test_session_fk_updates = []  # Track FK updates for second pass
                
                for row in shot_data:
                    shot_dict = dict(zip(columns, row))
                    # Filter out columns that don't exist in the local ShotData model
                    valid_columns = {key: value for key, value in shot_dict.items() if hasattr(ShotData, key)}
                    existing = existing_shot_data.get(str(valid_columns['id']))
                    
                    # Handle test_session_id foreign key
                    original_test_session_id = valid_columns.get('test_session_id')
                    if original_test_session_id is not None:
                        test_session_id_str = str(original_test_session_id)
                        # Check if test session exists locally
                        if test_session_id_str not in existing_test_session_ids:
                            # Set to NULL for now, will update later
                            valid_columns['test_session_id'] = None
                            test_session_fk_updates.append({
                                'id': valid_columns['id'],
                                'test_session_id': original_test_session_id
                            })
                    
                    if not existing:
                        if sync_all_new or should_sync_record("shot_data", valid_columns['id'], "new"):
                            new_shot_data.append(valid_columns)
                    else:
                        if sync_all_updated or should_sync_record("shot_data", valid_columns['id'], "updated"):
                            updated_shot_data.append(valid_columns)
                
                if new_shot_data:
                    local_db.bulk_insert_mappings(ShotData, new_shot_data)
                    applied_changes["new"] += len(new_shot_data)
                
                if updated_shot_data:
                    local_db.bulk_update_mappings(ShotData, updated_shot_data)
                    applied_changes["updated"] += len(updated_shot_data)
                
                local_db.commit()
                
                # Second pass: update test_session_id for records that had missing test sessions
                if test_session_fk_updates:
                    for update in test_session_fk_updates:
                        test_session_id_str = str(update['test_session_id'])
                        # Check if test session now exists after insert
                        test_session_exists = local_db.query(TestSession).filter(TestSession.id == update['test_session_id']).first() is not None
                        if test_session_exists:
                            local_db.query(ShotData).filter(ShotData.id == update['id']).update({
                                'test_session_id': update['test_session_id']
                            })
                    local_db.commit()
                

            
            # Sync protocols
            remote_cursor.execute("SELECT * FROM protocols")
            columns = [desc[0] for desc in remote_cursor.description]
            protocols_data = remote_cursor.fetchall()
            
            # Skip if no remote data
            if not protocols_data:
                pass
            else:
                # Check if we should sync all records (count-based)
                sync_all_new = should_sync_all("protocols", "new")
                sync_all_updated = should_sync_all("protocols", "updated")
                
                # Get existing records as hash map for O(1) lookups
                existing_protocols = {}
                for item in local_db.query(Protocol).all():
                    existing_protocols[str(item.id)] = item
                
                new_protocols = []
                updated_protocols = []
                
                for row in protocols_data:
                    protocol_dict = dict(zip(columns, row))
                    valid_columns = {key: value for key, value in protocol_dict.items() if hasattr(Protocol, key)}
                    existing = existing_protocols.get(str(valid_columns['id']))
                    
                    if not existing:
                        if sync_all_new or should_sync_record("protocols", valid_columns['id'], "new"):
                            new_protocols.append(valid_columns)
                    else:
                        if sync_all_updated or should_sync_record("protocols", valid_columns['id'], "updated"):
                            updated_protocols.append(valid_columns)
                
                if new_protocols:
                    local_db.bulk_insert_mappings(Protocol, new_protocols)
                    applied_changes["new"] += len(new_protocols)
                
                if updated_protocols:
                    local_db.bulk_update_mappings(Protocol, updated_protocols)
                    applied_changes["updated"] += len(updated_protocols)
                
                local_db.commit()
            
            # Sync locations (labs)
            remote_cursor.execute("SELECT * FROM locations")
            columns = [desc[0] for desc in remote_cursor.description]
            locations_data = remote_cursor.fetchall()
            
            # Skip if no remote data
            if not locations_data:
                pass
            else:
                # Check if we should sync all records (count-based)
                sync_all_new = should_sync_all("locations", "new")
                sync_all_updated = should_sync_all("locations", "updated")
                
                # Get existing records as hash map for O(1) lookups
                existing_locations = {}
                for item in local_db.query(Location).all():
                    existing_locations[str(item.id)] = item
                
                new_locations = []
                updated_locations = []
                
                for row in locations_data:
                    location_dict = dict(zip(columns, row))
                    valid_columns = {key: value for key, value in location_dict.items() if hasattr(Location, key)}
                    existing = existing_locations.get(str(valid_columns['id']))
                    
                    if not existing:
                        if sync_all_new or should_sync_record("locations", valid_columns['id'], "new"):
                            new_locations.append(valid_columns)
                    else:
                        if sync_all_updated or should_sync_record("locations", valid_columns['id'], "updated"):
                            updated_locations.append(valid_columns)
                
                if new_locations:
                    local_db.bulk_insert_mappings(Location, new_locations)
                    applied_changes["new"] += len(new_locations)
                
                if updated_locations:
                    local_db.bulk_update_mappings(Location, updated_locations)
                    applied_changes["updated"] += len(updated_locations)
                
                local_db.commit()
            
            # Sync users (must be before anchor_points due to FK constraint)
            remote_to_local_user_id = {}
            fallback_user_id = None
            remote_cursor.execute("SELECT * FROM users")
            columns = [desc[0] for desc in remote_cursor.description]
            users_data = remote_cursor.fetchall()
            
            # Skip if no remote data
            if not users_data:
                pass
            else:
                # Check if we should sync all records (count-based)
                sync_all_new = should_sync_all("users", "new")
                sync_all_updated = should_sync_all("users", "updated")
                
                # Get existing records as hash map by username for O(1) lookups
                # Use username instead of ID since usernames are unique and matter for auth
                existing_users = {}
                for item in local_db.query(User).all():
                    existing_users[item.username] = item
                
                new_users = []
                updated_users = []
                
                for row in users_data:
                    user_dict = dict(zip(columns, row))
                    valid_columns = {key: value for key, value in user_dict.items() if hasattr(User, key)}
                    # Convert UUID strings to UUID objects
                    if 'id' in valid_columns and isinstance(valid_columns['id'], str):
                        valid_columns['id'] = uuid.UUID(valid_columns['id'])
                    # Match by username instead of ID
                    existing = existing_users.get(valid_columns.get('username'))
                    
                    if not existing:
                        if sync_all_new or should_sync_record("users", str(valid_columns['id']), "new"):
                            new_users.append(valid_columns)
                    else:
                        # Update the ID to match the existing local record's ID
                        # This preserves the local ID while updating other fields
                        valid_columns['id'] = existing.id
                        if sync_all_updated or should_sync_record("users", str(valid_columns['id']), "updated"):
                            updated_users.append(valid_columns)
                
                if new_users:
                    local_db.bulk_insert_mappings(User, new_users)
                    applied_changes["new"] += len(new_users)
                
                if updated_users:
                    local_db.bulk_update_mappings(User, updated_users)
                    applied_changes["updated"] += len(updated_users)
                
                local_db.commit()

                # Build remote-to-local user ID mapping for FK remapping
                # Remote users matched by username have different IDs than local
                remote_to_local_user_id = {}
                local_users_by_username = {u.username: u for u in local_db.query(User).all()}
                for row in users_data:
                    remote_user = dict(zip(columns, row))
                    remote_username = remote_user.get('username')
                    remote_id = remote_user.get('id')
                    if remote_id and remote_username and remote_username in local_users_by_username:
                        remote_to_local_user_id[str(remote_id)] = local_users_by_username[remote_username].id

                # Fallback: use first local admin user for unmapped remote users
                # (users not in preview/sync confirmation are skipped, so their IDs won't exist locally)
                fallback_user = local_db.query(User).filter(User.is_admin == True).first()
                if not fallback_user:
                    fallback_user = local_db.query(User).first()
                if fallback_user:
                    fallback_user_id = fallback_user.id

            # Sync anchor points
            remote_cursor.execute("SELECT * FROM anchor_points")
            columns = [desc[0] for desc in remote_cursor.description]
            anchor_points_data = remote_cursor.fetchall()
            
            # Skip if no remote data
            if not anchor_points_data:
                pass
            else:
                # Check if we should sync all records (count-based)
                sync_all_new = should_sync_all("anchor_points", "new")
                sync_all_updated = should_sync_all("anchor_points", "updated")
                
                # Get existing records as hash map for O(1) lookups
                existing_anchor_points = {}
                for item in local_db.query(AnchorPoint).all():
                    existing_anchor_points[str(item.id)] = item
                
                new_anchor_points = []
                updated_anchor_points = []
                
                for row in anchor_points_data:
                    anchor_point_dict = dict(zip(columns, row))
                    valid_columns = {key: value for key, value in anchor_point_dict.items() if hasattr(AnchorPoint, key)}
                    # Convert UUID strings to UUID objects
                    if 'id' in valid_columns and isinstance(valid_columns['id'], str):
                        valid_columns['id'] = uuid.UUID(valid_columns['id'])
                    if 'created_by_id' in valid_columns and valid_columns['created_by_id']:
                        remote_uid = str(valid_columns['created_by_id'])
                        if remote_uid in remote_to_local_user_id:
                            valid_columns['created_by_id'] = remote_to_local_user_id[remote_uid]
                        elif fallback_user_id:
                            valid_columns['created_by_id'] = fallback_user_id
                        elif isinstance(valid_columns['created_by_id'], str):
                            valid_columns['created_by_id'] = uuid.UUID(valid_columns['created_by_id'])
                    if 'batch_id' in valid_columns and valid_columns['batch_id'] and isinstance(valid_columns['batch_id'], str):
                        valid_columns['batch_id'] = uuid.UUID(valid_columns['batch_id'])
                    existing = existing_anchor_points.get(str(valid_columns['id']))
                    if not existing:
                        if sync_all_new or should_sync_record("anchor_points", str(valid_columns['id']), "new"):
                            new_anchor_points.append(valid_columns)
                    else:
                        if sync_all_updated or should_sync_record("anchor_points", str(valid_columns['id']), "updated"):
                            updated_anchor_points.append(valid_columns)
                
                if new_anchor_points:
                    local_db.bulk_insert_mappings(AnchorPoint, new_anchor_points)
                    applied_changes["new"] += len(new_anchor_points)
                
                if updated_anchor_points:
                    local_db.bulk_update_mappings(AnchorPoint, updated_anchor_points)
                    applied_changes["updated"] += len(updated_anchor_points)
                
                local_db.commit()
            
            # Sync anchor point layers
            remote_cursor.execute("SELECT * FROM anchor_point_layers")
            columns = [desc[0] for desc in remote_cursor.description]
            anchor_point_layers_data = remote_cursor.fetchall()
            
            # Skip if no remote data
            if not anchor_point_layers_data:
                pass
            else:
                # Check if we should sync all records (count-based)
                sync_all_new = should_sync_all("anchor_point_layers", "new")
                sync_all_updated = should_sync_all("anchor_point_layers", "updated")
                
                # Get existing records as hash map for O(1) lookups
                existing_anchor_point_layers = {}
                for item in local_db.query(AnchorPointLayer).all():
                    existing_anchor_point_layers[str(item.id)] = item
                
                new_anchor_point_layers = []
                updated_anchor_point_layers = []
                
                for row in anchor_point_layers_data:
                    anchor_point_layer_dict = dict(zip(columns, row))
                    valid_columns = {key: value for key, value in anchor_point_layer_dict.items() if hasattr(AnchorPointLayer, key)}
                    existing = existing_anchor_point_layers.get(str(valid_columns['id']))
                    if not existing:
                        if sync_all_new or should_sync_record("anchor_point_layers", valid_columns['id'], "new"):
                            new_anchor_point_layers.append(valid_columns)
                    else:
                        if sync_all_updated or should_sync_record("anchor_point_layers", valid_columns['id'], "updated"):
                            updated_anchor_point_layers.append(valid_columns)
                
                if new_anchor_point_layers:
                    local_db.bulk_insert_mappings(AnchorPointLayer, new_anchor_point_layers)
                    applied_changes["new"] += len(new_anchor_point_layers)
                
                if updated_anchor_point_layers:
                    local_db.bulk_update_mappings(AnchorPointLayer, updated_anchor_point_layers)
                    applied_changes["updated"] += len(updated_anchor_point_layers)
                
                local_db.commit()
            
            # Sync geometries
            remote_cursor.execute("SELECT * FROM geometries")
            columns = [desc[0] for desc in remote_cursor.description]
            geometries_data = remote_cursor.fetchall()
            
            if not geometries_data:
                pass
            else:
                sync_all_new = should_sync_all("geometries", "new")
                sync_all_updated = should_sync_all("geometries", "updated")
                
                existing_geometries = {}
                for item in local_db.query(Geometry).all():
                    existing_geometries[str(item.id)] = item
                
                new_geometries = []
                updated_geometries = []
                
                for row in geometries_data:
                    geometry_dict = dict(zip(columns, row))
                    valid_columns = {key: value for key, value in geometry_dict.items() if hasattr(Geometry, key)}
                    existing = existing_geometries.get(str(valid_columns['id']))
                    
                    if not existing:
                        if sync_all_new or should_sync_record("geometries", str(valid_columns['id']), "new"):
                            new_geometries.append(valid_columns)
                    else:
                        if sync_all_updated or should_sync_record("geometries", str(valid_columns['id']), "updated"):
                            updated_geometries.append(valid_columns)
                
                if new_geometries:
                    local_db.bulk_insert_mappings(Geometry, new_geometries)
                    applied_changes["new"] += len(new_geometries)
                
                if updated_geometries:
                    local_db.bulk_update_mappings(Geometry, updated_geometries)
                    applied_changes["updated"] += len(updated_geometries)
                
                local_db.commit()
            
            # Sync geometry material configs
            remote_cursor.execute("SELECT * FROM geometry_material_configs")
            columns = [desc[0] for desc in remote_cursor.description]
            geometry_material_configs_data = remote_cursor.fetchall()
            
            if not geometry_material_configs_data:
                pass
            else:
                sync_all_new = should_sync_all("geometry_material_configs", "new")
                sync_all_updated = should_sync_all("geometry_material_configs", "updated")
                
                existing_geometry_material_configs = {}
                for item in local_db.query(GeometryMaterialConfig).all():
                    existing_geometry_material_configs[str(item.id)] = item
                
                new_geometry_material_configs = []
                updated_geometry_material_configs = []
                
                for row in geometry_material_configs_data:
                    gmc_dict = dict(zip(columns, row))
                    valid_columns = {key: value for key, value in gmc_dict.items() if hasattr(GeometryMaterialConfig, key)}
                    existing = existing_geometry_material_configs.get(str(valid_columns['id']))
                    
                    if not existing:
                        if sync_all_new or should_sync_record("geometry_material_configs", str(valid_columns['id']), "new"):
                            new_geometry_material_configs.append(valid_columns)
                    else:
                        if sync_all_updated or should_sync_record("geometry_material_configs", str(valid_columns['id']), "updated"):
                            updated_geometry_material_configs.append(valid_columns)
                
                if new_geometry_material_configs:
                    local_db.bulk_insert_mappings(GeometryMaterialConfig, new_geometry_material_configs)
                    applied_changes["new"] += len(new_geometry_material_configs)
                
                if updated_geometry_material_configs:
                    local_db.bulk_update_mappings(GeometryMaterialConfig, updated_geometry_material_configs)
                    applied_changes["updated"] += len(updated_geometry_material_configs)
                
                local_db.commit()
            
            # Sync covers
            remote_cursor.execute("SELECT * FROM covers")
            columns = [desc[0] for desc in remote_cursor.description]
            covers_data = remote_cursor.fetchall()
            
            if not covers_data:
                pass
            else:
                sync_all_new = should_sync_all("covers", "new")
                sync_all_updated = should_sync_all("covers", "updated")
                
                existing_covers = {}
                for item in local_db.query(Cover).all():
                    existing_covers[str(item.id)] = item
                
                new_covers = []
                updated_covers = []
                
                for row in covers_data:
                    cover_dict = dict(zip(columns, row))
                    valid_columns = {key: value for key, value in cover_dict.items() if hasattr(Cover, key)}
                    existing = existing_covers.get(str(valid_columns['id']))
                    
                    if not existing:
                        if sync_all_new or should_sync_record("covers", str(valid_columns['id']), "new"):
                            new_covers.append(valid_columns)
                    else:
                        if sync_all_updated or should_sync_record("covers", str(valid_columns['id']), "updated"):
                            updated_covers.append(valid_columns)
                
                if new_covers:
                    local_db.bulk_insert_mappings(Cover, new_covers)
                    applied_changes["new"] += len(new_covers)
                
                if updated_covers:
                    local_db.bulk_update_mappings(Cover, updated_covers)
                    applied_changes["updated"] += len(updated_covers)
                
                local_db.commit()
            
            # Handle deletions based on confirmation - order matters for foreign key constraints
            # Delete in reverse dependency order: children before parents
            deletion_order = [
                ("shot_data", ShotData),
                ("anchor_point_layers", AnchorPointLayer),
                ("anchor_points", AnchorPoint),
                ("test_sessions", TestSession),
                ("vest_layers", VestLayer),
                ("vests", Vest),
                ("geometry_material_configs", GeometryMaterialConfig),
                ("covers", Cover),
                ("materials", Material),
                ("ammunition", Ammunition),
                ("protocols", Protocol),
                ("locations", Location),
                ("geometries", Geometry)
            ]
            
            for entity_name, model_class in deletion_order:
                if entity_name in confirmation.confirmed_changes and "deleted" in confirmation.confirmed_changes[entity_name]:
                    deleted_ids = confirmation.confirmed_changes[entity_name]["deleted"]
                    if deleted_ids:
                        # Check if "count" marker is present - means delete all local records not on remote
                        if "count" in deleted_ids:
                            # Get all local record IDs
                            local_ids = set(str(item.id) for item in local_db.query(model_class).all())
                            # Get all remote record IDs
                            remote_ids = set()
                            if entity_name == "ammunition":
                                remote_cursor.execute("SELECT id FROM ammunition")
                            elif entity_name == "materials":
                                remote_cursor.execute("SELECT id FROM materials")
                            elif entity_name == "vests":
                                remote_cursor.execute("SELECT id FROM vests")
                            elif entity_name == "vest_layers":
                                remote_cursor.execute("SELECT id FROM vest_layers")
                            elif entity_name == "test_sessions":
                                remote_cursor.execute("SELECT id FROM test_sessions")
                            elif entity_name == "shot_data":
                                remote_cursor.execute("SELECT id FROM shot_data")
                            elif entity_name == "protocols":
                                remote_cursor.execute("SELECT id FROM protocols")
                            elif entity_name == "locations":
                                remote_cursor.execute("SELECT id FROM locations")
                            elif entity_name == "users":
                                remote_cursor.execute("SELECT id FROM users")
                            elif entity_name == "anchor_points":
                                remote_cursor.execute("SELECT id FROM anchor_points")
                            elif entity_name == "anchor_point_layers":
                                remote_cursor.execute("SELECT id FROM anchor_point_layers")
                            elif entity_name == "geometries":
                                remote_cursor.execute("SELECT id FROM geometries")
                            elif entity_name == "geometry_material_configs":
                                remote_cursor.execute("SELECT id FROM geometry_material_configs")
                            elif entity_name == "covers":
                                remote_cursor.execute("SELECT id FROM covers")
                            
                            for row in remote_cursor.fetchall():
                                remote_ids.add(str(row[0]))
                            
                            # Find IDs to delete (local but not remote)
                            actual_deleted_ids = list(local_ids - remote_ids)
                        else:
                            # Filter out "count" marker which is used for syncing all records
                            actual_deleted_ids = [id for id in deleted_ids if id != "count"]
                        
                        if not actual_deleted_ids:
                            continue
                        # For test_sessions, handle self-referential FK by setting parent_test_group_id to NULL
                        if entity_name == "test_sessions":
                            # Set parent_test_group_id to NULL for any test_sessions that reference deleted ones
                            local_db.query(TestSession).filter(TestSession.parent_test_group_id.in_(actual_deleted_ids)).update({"parent_test_group_id": None}, synchronize_session=False)
                            local_db.commit()
                        # For vests, handle vest_id FK in test_sessions by setting vest_id to NULL
                        if entity_name == "vests":
                            # Set vest_id to NULL for any test_sessions that reference deleted vests
                            local_db.query(TestSession).filter(TestSession.vest_id.in_(actual_deleted_ids)).update({"vest_id": None}, synchronize_session=False)
                            local_db.commit()
                        for record_id in actual_deleted_ids:
                            existing = local_db.query(model_class).filter(model_class.id == record_id).first()
                            if existing:
                                local_db.delete(existing)
                                applied_changes["deleted"] += 1
            
            local_db.commit()
            
            return {"message": "Database sync completed successfully", "synced_records": {
                "ammunition": len(ammunition_data),
                "materials": len(materials_data),
                "vests": len(vests_data),
                "vest_layers": len(vest_layers_data),
                "test_sessions": len(test_sessions_data),
                "shot_data": len(shot_data),
                "protocols": len(protocols_data),
                "locations": len(locations_data),
                "users": len(users_data),
                "anchor_points": len(anchor_points_data),
                "anchor_point_layers": len(anchor_point_layers_data),
                "geometries": len(geometries_data),
                "geometry_material_configs": len(geometry_material_configs_data),
                "covers": len(covers_data)
            }}
            
        except Exception as e:
            local_db.rollback()
            import traceback
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")
        finally:
            local_db.close()
            remote_cursor.close()
            remote_conn.close()
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to connect to remote database: {str(e)}")


@router.post("/seed-geometries")
def seed_geometries_endpoint(
    current_user: User = Depends(get_current_active_user)
):
    """Seed or update geometries from the fixtures/geometries.json file (admin only)."""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    db = SessionLocal()
    try:
        geometries = seed_geometries(db)
        return {"message": f"Seeded {len(geometries)} geometries", "count": len(geometries)}
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Seed failed: {str(e)}")
    finally:
        db.close()


@router.post("/reset-database")
def reset_database(
    request: Optional[ResetRequest] = None,
    current_user: User = Depends(get_current_active_user)
):
    """Reset local database to match remote database (delete local data + sync fresh).
    If entities are specified, only reset those entities. Otherwise, reset all."""
    # Check if user is admin
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Get list of entities to reset
    entities_to_reset = request.entities if request and request.entities else None
    
    # Remote database connection details
    remote_db_url = os.getenv("REMOTE_DATABASE_URL")
    if not remote_db_url:
        raise HTTPException(status_code=500, detail="REMOTE_DATABASE_URL not configured")
    
    local_db: Session = SessionLocal()
    
    try:
        # Define entity deletion order (children before parents)
        # Must delete all entities in proper order to handle FK dependencies
        deletion_order = [
            ("anchor_point_layers", AnchorPointLayer),
            ("shot_data", ShotData),
            ("vest_layers", VestLayer),
            ("test_sessions", TestSession),
            ("anchor_points", AnchorPoint),
            ("vests", Vest),
            ("geometry_material_configs", GeometryMaterialConfig),
            ("covers", Cover),
            ("materials", Material),
            ("ammunition", Ammunition),
            ("protocols", Protocol),
            ("locations", Location),
            ("geometries", Geometry),
            ("users", User),
        ]
        
        # Delete local data
        # If entities are selected, delete all of them (in proper order)
        # If no entities selected, delete all
        if entities_to_reset:
            for entity_name, model_class in deletion_order:
                if entity_name in entities_to_reset:
                    local_db.query(model_class).delete()
        else:
            for entity_name, model_class in deletion_order:
                local_db.query(model_class).delete()
        local_db.commit()
        
        # Connect to remote database
        remote_conn = psycopg2.connect(remote_db_url, connect_timeout=10)
        remote_cursor = remote_conn.cursor()
        
        try:
            # Initialize data variables for return statement
            ammunition_data = []
            materials_data = []
            vests_data = []
            vest_layers_data = []
            test_sessions_data = []
            shot_data = []
            protocols_data = []
            locations_data = []
            users_data = []
            anchor_points_data = []
            anchor_point_layers_data = []
            geometries_data = []
            geometry_material_configs_data = []
            covers_data = []
            
            # Sync ammunition
            if not entities_to_reset or "ammunition" in entities_to_reset:
                remote_cursor.execute("SELECT * FROM ammunition")
                columns = [desc[0] for desc in remote_cursor.description]
                ammunition_data = remote_cursor.fetchall()
                
                for row in ammunition_data:
                    ammo_dict = dict(zip(columns, row))
                    new_ammo = Ammunition(**ammo_dict)
                    local_db.add(new_ammo)
                
                local_db.commit()
            
            # Sync materials
            if not entities_to_reset or "materials" in entities_to_reset:
                remote_cursor.execute("SELECT * FROM materials")
                columns = [desc[0] for desc in remote_cursor.description]
                materials_data = remote_cursor.fetchall()
                
                for row in materials_data:
                    material_dict = dict(zip(columns, row))
                    valid_columns = {key: value for key, value in material_dict.items() if hasattr(Material, key)}
                    new_material = Material(**valid_columns)
                    local_db.add(new_material)
                
                local_db.commit()
            
            # Sync vests
            if not entities_to_reset or "vests" in entities_to_reset:
                remote_cursor.execute("SELECT * FROM vests")
                columns = [desc[0] for desc in remote_cursor.description]
                vests_data = remote_cursor.fetchall()
                
                for row in vests_data:
                    vest_dict = dict(zip(columns, row))
                    valid_columns = {key: value for key, value in vest_dict.items() if hasattr(Vest, key)}
                    new_vest = Vest(**valid_columns)
                    local_db.add(new_vest)
                
                local_db.commit()
            
            # Sync vest layers
            if not entities_to_reset or "vest_layers" in entities_to_reset:
                remote_cursor.execute("SELECT * FROM vest_layers")
                columns = [desc[0] for desc in remote_cursor.description]
                vest_layers_data = remote_cursor.fetchall()
                
                for row in vest_layers_data:
                    vest_layer_dict = dict(zip(columns, row))
                    valid_columns = {key: value for key, value in vest_layer_dict.items() if hasattr(VestLayer, key)}
                    new_vest_layer = VestLayer(**valid_columns)
                    local_db.add(new_vest_layer)
                
                local_db.commit()
            
            # Sync test sessions
            if not entities_to_reset or "test_sessions" in entities_to_reset:
                remote_cursor.execute("SELECT * FROM test_sessions")
                columns = [desc[0] for desc in remote_cursor.description]
                test_sessions_data = remote_cursor.fetchall()
                
                for row in test_sessions_data:
                    test_session_dict = dict(zip(columns, row))
                    valid_columns = {key: value for key, value in test_session_dict.items() if hasattr(TestSession, key)}
                    new_test_session = TestSession(**valid_columns)
                    local_db.add(new_test_session)
                
                local_db.commit()
            
            # Sync shot data
            if not entities_to_reset or "shot_data" in entities_to_reset:
                remote_cursor.execute("SELECT * FROM shot_data")
                columns = [desc[0] for desc in remote_cursor.description]
                shot_data = remote_cursor.fetchall()
                
                for row in shot_data:
                    shot_dict = dict(zip(columns, row))
                    valid_columns = {key: value for key, value in shot_dict.items() if hasattr(ShotData, key)}
                    new_shot = ShotData(**valid_columns)
                    local_db.add(new_shot)
                
                local_db.commit()
            
            # Sync protocols
            if not entities_to_reset or "protocols" in entities_to_reset:
                remote_cursor.execute("SELECT * FROM protocols")
                columns = [desc[0] for desc in remote_cursor.description]
                protocols_data = remote_cursor.fetchall()
                
                for row in protocols_data:
                    protocol_dict = dict(zip(columns, row))
                    valid_columns = {key: value for key, value in protocol_dict.items() if hasattr(Protocol, key)}
                    new_protocol = Protocol(**valid_columns)
                    local_db.add(new_protocol)
                
                local_db.commit()
            
            # Sync locations
            if not entities_to_reset or "locations" in entities_to_reset:
                remote_cursor.execute("SELECT * FROM locations")
                columns = [desc[0] for desc in remote_cursor.description]
                locations_data = remote_cursor.fetchall()
                
                for row in locations_data:
                    location_dict = dict(zip(columns, row))
                    valid_columns = {key: value for key, value in location_dict.items() if hasattr(Location, key)}
                    new_location = Location(**valid_columns)
                    local_db.add(new_location)
                
                local_db.commit()
            
            # Sync users (must be before anchor_points due to FK constraint)
            if not entities_to_reset or "users" in entities_to_reset:
                remote_cursor.execute("SELECT * FROM users")
                columns = [desc[0] for desc in remote_cursor.description]
                users_data = remote_cursor.fetchall()
                
                # Get existing users by username to avoid duplicates
                existing_users = {}
                for item in local_db.query(User).all():
                    existing_users[item.username] = item
                
                for row in users_data:
                    user_dict = dict(zip(columns, row))
                    valid_columns = {key: value for key, value in user_dict.items() if hasattr(User, key)}
                    # Convert UUID strings to UUID objects
                    if 'id' in valid_columns and isinstance(valid_columns['id'], str):
                        valid_columns['id'] = uuid.UUID(valid_columns['id'])
                    
                    # Check if user with same username exists locally
                    existing = existing_users.get(valid_columns.get('username'))
                    if existing:
                        # Update existing user instead of inserting duplicate
                        for key, value in valid_columns.items():
                            if hasattr(existing, key) and key != 'id':
                                setattr(existing, key, value)
                    else:
                        # Insert new user
                        new_user = User(**valid_columns)
                        local_db.add(new_user)
                
                local_db.commit()
            
            # Sync anchor points
            if not entities_to_reset or "anchor_points" in entities_to_reset:
                remote_cursor.execute("SELECT * FROM anchor_points")
                columns = [desc[0] for desc in remote_cursor.description]
                anchor_points_data = remote_cursor.fetchall()
                
                for row in anchor_points_data:
                    anchor_point_dict = dict(zip(columns, row))
                    valid_columns = {key: value for key, value in anchor_point_dict.items() if hasattr(AnchorPoint, key)}
                    # Convert UUID strings to UUID objects
                    if 'id' in valid_columns and isinstance(valid_columns['id'], str):
                        valid_columns['id'] = uuid.UUID(valid_columns['id'])
                    if 'created_by_id' in valid_columns and isinstance(valid_columns['created_by_id'], str):
                        valid_columns['created_by_id'] = uuid.UUID(valid_columns['created_by_id'])
                    if 'batch_id' in valid_columns and valid_columns['batch_id'] and isinstance(valid_columns['batch_id'], str):
                        valid_columns['batch_id'] = uuid.UUID(valid_columns['batch_id'])
                    new_anchor_point = AnchorPoint(**valid_columns)
                    local_db.add(new_anchor_point)
                
                local_db.commit()
            
            # Sync anchor point layers
            if not entities_to_reset or "anchor_point_layers" in entities_to_reset:
                remote_cursor.execute("SELECT * FROM anchor_point_layers")
                columns = [desc[0] for desc in remote_cursor.description]
                anchor_point_layers_data = remote_cursor.fetchall()
                
                for row in anchor_point_layers_data:
                    anchor_point_layer_dict = dict(zip(columns, row))
                    valid_columns = {key: value for key, value in anchor_point_layer_dict.items() if hasattr(AnchorPointLayer, key)}
                    new_anchor_point_layer = AnchorPointLayer(**valid_columns)
                    local_db.add(new_anchor_point_layer)
                
                local_db.commit()
            
            # Sync geometries
            if not entities_to_reset or "geometries" in entities_to_reset:
                remote_cursor.execute("SELECT * FROM geometries")
                columns = [desc[0] for desc in remote_cursor.description]
                geometries_data = remote_cursor.fetchall()
                
                for row in geometries_data:
                    geometry_dict = dict(zip(columns, row))
                    valid_columns = {key: value for key, value in geometry_dict.items() if hasattr(Geometry, key)}
                    new_geometry = Geometry(**valid_columns)
                    local_db.add(new_geometry)
                
                local_db.commit()
            
            # Sync geometry material configs
            if not entities_to_reset or "geometry_material_configs" in entities_to_reset:
                remote_cursor.execute("SELECT * FROM geometry_material_configs")
                columns = [desc[0] for desc in remote_cursor.description]
                geometry_material_configs_data = remote_cursor.fetchall()
                
                for row in geometry_material_configs_data:
                    gmc_dict = dict(zip(columns, row))
                    valid_columns = {key: value for key, value in gmc_dict.items() if hasattr(GeometryMaterialConfig, key)}
                    new_gmc = GeometryMaterialConfig(**valid_columns)
                    local_db.add(new_gmc)
                
                local_db.commit()
            
            # Sync covers
            if not entities_to_reset or "covers" in entities_to_reset:
                remote_cursor.execute("SELECT * FROM covers")
                columns = [desc[0] for desc in remote_cursor.description]
                covers_data = remote_cursor.fetchall()
                
                for row in covers_data:
                    cover_dict = dict(zip(columns, row))
                    valid_columns = {key: value for key, value in cover_dict.items() if hasattr(Cover, key)}
                    new_cover = Cover(**valid_columns)
                    local_db.add(new_cover)
                
                local_db.commit()
            
            return {"message": "Database reset completed successfully", "synced_records": {
                "ammunition": len(ammunition_data),
                "materials": len(materials_data),
                "vests": len(vests_data),
                "vest_layers": len(vest_layers_data),
                "test_sessions": len(test_sessions_data),
                "shot_data": len(shot_data),
                "protocols": len(protocols_data),
                "locations": len(locations_data),
                "users": len(users_data),
                "anchor_points": len(anchor_points_data),
                "anchor_point_layers": len(anchor_point_layers_data),
                "geometries": len(geometries_data),
                "geometry_material_configs": len(geometry_material_configs_data),
                "covers": len(covers_data)
            }}
            
        except Exception as e:
            local_db.rollback()
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
                    pg_dump_bin = shutil.which('pg_dump')
                    if not pg_dump_bin:
                        raise Exception("pg_dump not found on PATH. Ensure postgresql-client is installed and matches the server version.")
                    
                    subprocess.run(
                        ['pg_dump', db_url, '-f', db_backup_file],
                        check=True,
                        capture_output=True
                    )
                    
                    # Compress the SQL file with gzip if available
                    if shutil.which('gzip'):
                        compressed_file = db_backup_file + '.gz'
                        subprocess.run(
                            ['gzip', '-9', db_backup_file],
                            check=True,
                            capture_output=True
                        )
                        zipf.write(compressed_file, 'database_dump.sql.gz')
                        os.remove(compressed_file)  # Clean up compressed file
                    else:
                        zipf.write(db_backup_file, 'database_dump.sql')
                    
                    # Clean up the SQL file if it still exists
                    if os.path.exists(db_backup_file):
                        os.remove(db_backup_file)
                        
                except subprocess.CalledProcessError as e:
                    # pg_dump failed, try to provide more detailed error
                    stderr = e.stderr.decode() if e.stderr else str(e)
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
                    
                    for root, dirs, files in os.walk(storage_dir):
                        # Skip backups directory
                        if backup_dir in root:
                            continue
                        for file in files:
                            file_path = os.path.join(root, file)
                            arcname = os.path.relpath(file_path, os.path.dirname(storage_dir))
                            zipf.write(file_path, arcname)

        return {"message": "Backup created successfully", "filename": backup_filename}

    except HTTPException:
        raise
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
    
    try:
        restore_progress[task_id] = {"status": "extracting", "progress": 10, "message": "Extracting backup file..."}
        
        # Extract the zip file
        with zipfile.ZipFile(backup_path, 'r') as zipf:
            zipf.extractall(temp_dir)
        
        restore_progress[task_id] = {"status": "restoring_db", "progress": 30, "message": "Restoring database..."}
        
        # Restore the database
        db_backup_file = os.path.join(temp_dir, 'database_dump.sql')
        db_backup_file_gz = os.path.join(temp_dir, 'database_dump.sql.gz')

        # Decompress if needed
        if os.path.exists(db_backup_file_gz):
            subprocess.run(
                ['gunzip', '-k', db_backup_file_gz],
                check=True,
                capture_output=True
            )

        if os.path.exists(db_backup_file):
            db_url = os.getenv("DATABASE_URL")
            if db_url:
                try:
                    # Parse DATABASE_URL to get connection details
                    match = re.match(r'postgresql://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)', db_url)
                    if not match:
                        restore_progress[task_id] = {"status": "error", "progress": 0, "message": "Invalid DATABASE_URL format"}
                        return
                    
                    user, password, host, port, database = match.groups()
                    
                    # Set environment variables for psql
                    env = os.environ.copy()
                    env['PGPASSWORD'] = password
                    
                    # Use Popen with proper stream handling
                    process = subprocess.Popen(
                        ['psql', '-h', host, '-p', port, '-U', user, '-d', database, '-f', db_backup_file],
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        env=env,
                        text=True
                    )
                    
                    stdout, stderr = process.communicate(timeout=300)
                    
                    if process.returncode != 0:
                        raise Exception(f"psql failed: {stderr}")
                    
                    
                    restore_progress[task_id] = {"status": "restoring_files", "progress": 70, "message": "Restoring storage files..."}
                except Exception as e:
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
        # Create a unique task ID
        task_id = str(uuid.uuid4())

        # Get backup path from storage
        backup_dir = os.path.join(settings.upload_dir, 'backups')
        backup_path = os.path.join(backup_dir, filename)

        if not os.path.exists(backup_path):
            raise HTTPException(status_code=404, detail="Backup file not found")

        # Create a temporary directory for extraction
        temp_dir = tempfile.mkdtemp()

        # Initialize progress
        restore_progress[task_id] = {"status": "starting", "progress": 0, "message": "Starting restore..."}

        # Start background thread
        thread = threading.Thread(target=perform_restore, args=(task_id, backup_path, temp_dir))
        thread.daemon = True
        thread.start()

        return {"task_id": task_id, "message": "Restore started"}

    except HTTPException:
        raise
    except Exception as e:
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
    """Get the current application version."""
    if settings.VERSION:
        return {"version": settings.VERSION}
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
