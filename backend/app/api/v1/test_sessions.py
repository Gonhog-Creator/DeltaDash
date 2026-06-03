from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
import os
import uuid
from pathlib import Path
import json
from datetime import datetime, timezone

from app.db.session import get_db
from app.db.models import TestSession as TestSessionModel, ShotData as ShotDataModel, Shot as ShotModel, Vest as VestModel, AuditLog
from app.api.v1.auth import get_current_active_user, require_write_access
from app.schemas.test_session import TestSessionCreate, TestSessionUpdate, TestSession
from app.schemas.shot_data import ShotDataCreate
from app.db.models.user import User as UserModel
from app.services.excel_parser import ExcelParser, ExcelParseError
from app.services.test_session_service import create_sessions_from_excel_data
from app.core.config import settings



router = APIRouter(redirect_slashes=False)


@router.get("/")
def list_test_sessions(
    skip: int = 0,
    limit: int = 100,
    is_official: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    query = db.query(TestSessionModel, VestModel).outerjoin(VestModel, TestSessionModel.vest_id == VestModel.id)
    
    if is_official is not None:
        query = query.filter(TestSessionModel.is_official == is_official)
    
    test_sessions = query.order_by(TestSessionModel.name).offset(skip).limit(limit).all()
    
    result = []
    for session, vest in test_sessions:
        session_dict = {
            "id": session.id,
            "name": session.name,
            "test_date": session.test_date,
            "lab_name": session.lab_name,
            "protocol": session.protocol,
            "clay_temperature_c": session.clay_temperature_c,
            "ambient_temperature_c": session.ambient_temperature_c,
            "humidity_percent": session.humidity_percent,
            "conditioning": session.conditioning,
            "size": session.size,
            "ballistic_limit": session.ballistic_limit,
            "parent_test_group_id": session.parent_test_group_id,
            "vest_id": session.vest_id,
            "vest_name": vest.vest_code if vest else None,
            "vest_code": vest.vest_code if vest else None,
            "excel_file_path": session.excel_file_path,
            "notes": session.notes,
            "is_official": session.is_official,
            "certification_number": session.certification_number,
            "created_at": session.created_at,
            "updated_at": session.updated_at,
        }
        result.append(session_dict)
    
    return result


@router.post("/", response_model=TestSession, status_code=status.HTTP_201_CREATED)
def create_test_session(
    test_session: TestSessionCreate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_write_access)
):
    db_test_session = TestSessionModel(**test_session.model_dump())
    db.add(db_test_session)
    db.commit()
    db.refresh(db_test_session)
    return db_test_session


@router.post("/extract-date")
def extract_date_from_excel(
    excel_file: UploadFile = File(...),
):
    """Extract date from Excel file for preview before upload"""
    # Save Excel file temporarily
    os.makedirs(settings.material_docs_dir, exist_ok=True)
    file_ext = Path(excel_file.filename).suffix
    unique_filename = f"temp_{uuid.uuid4()}{file_ext}"
    file_path = os.path.join(settings.material_docs_dir, unique_filename)
    with open(file_path, 'wb') as f:
        f.write(excel_file.file.read())
    
    try:
        parser = ExcelParser(file_path)
        date_info = parser.extract_test_date()
        return date_info
    finally:
        # Clean up temporary file
        if os.path.exists(file_path):
            os.remove(file_path)


@router.post("/bulk-upload", response_model=List[TestSession], status_code=status.HTTP_201_CREATED)
def bulk_upload_excel(
    excel_files: List[UploadFile] = File(...),
    is_official: Optional[bool] = Form(False),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_write_access)
):
    """Bulk upload multiple Excel files at once (admin only)"""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    created_sessions = []
    
    for excel_file in excel_files:
        try:
            # Save Excel file with original filename
            os.makedirs(settings.material_docs_dir, exist_ok=True)
            file_path = os.path.join(settings.material_docs_dir, excel_file.filename)
            with open(file_path, 'wb') as f:
                f.write(excel_file.file.read())
            
            # Use filename as test name
            test_name = Path(excel_file.filename).stem
            
            # Create test session from Excel
            sessions = create_sessions_from_excel_data(
                db=db,
                excel_file_path=file_path,
                test_name=test_name,
                location_name=None,
                protocol=None,
                vest_id=None,
                test_date=None,
                temperature=None,
                humidity=None,
                is_full_path=True,
                is_official=is_official,
            )
            created_sessions.extend(sessions)
        except Exception as e:
            # Log error but continue with other files
            print(f"Error uploading {excel_file.filename}: {e}")
            continue
    
    return created_sessions


@router.post("/from-excel", response_model=List[TestSession], status_code=status.HTTP_201_CREATED)
def create_test_session_from_excel(
    excel_file: UploadFile = File(...),
    test_name: str = Form(...),
    location_id: Optional[str] = Form(None),
    protocol: Optional[str] = Form(None),
    vest_id: str = Form(...),
    test_date: Optional[str] = Form(None),
    date_format: Optional[str] = Form(None),  # 'spanish' or 'english' for ambiguous dates
    is_official: Optional[bool] = Form(False),
    certification_number: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_write_access)
):
    # Save Excel file with original filename
    os.makedirs(settings.material_docs_dir, exist_ok=True)
    file_path = os.path.join(settings.material_docs_dir, excel_file.filename)
    with open(file_path, 'wb') as f:
        f.write(excel_file.file.read())
    
    # Get location name if location_id is provided
    location_name = None
    if location_id:
        from app.db.models.location import Location as LocationModel
        location = db.query(LocationModel).filter(LocationModel.id == location_id).first()
        location_name = location.name if location else None
    
    # Extract date from Excel if not provided
    if not test_date:
        parser = ExcelParser(file_path)
        date_info = parser.extract_test_date()
        if date_info and date_info['date']:
            if date_info.get('ambiguous') and not date_format:
                # Return date ambiguity info to frontend
                return {
                    "error": "ambiguous_date",
                    "message": "Date format is ambiguous. Please choose between Spanish (DD/MM/YY) or English (MM/DD/YY) format.",
                    "date_info": date_info
                }
            elif date_format == 'english' and date_info.get('english_date'):
                test_date = date_info['english_date']
            else:
                # Default to Spanish format
                test_date = date_info['date']
    
    # Parse the Excel file - service will handle multi-sheet vs single-sheet
    # No need to extract temperature/humidity here - the service handles it
    return create_sessions_from_excel_data(
        db=db,
        excel_file_path=file_path,  # Pass full path since file was just saved
        test_name=test_name,
        location_name=location_name,
        protocol=protocol,
        vest_id=vest_id,
        test_date=test_date,
        temperature=None,  # Service will extract from parsed data
        humidity=None,    # Service will extract from parsed data
        is_full_path=True,
        is_official=is_official,
        certification_number=certification_number,
    )


@router.patch("/{session_id}/vest", response_model=TestSession)
def update_session_vest(
    session_id: str,
    vest_id: str = Form(...),
    cascade: bool = Form(False),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_write_access)
):
    """Update vest for a test session, optionally cascading to all child sessions"""
    session = db.query(TestSessionModel).filter(TestSessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Test session not found")
    
    session.vest_id = vest_id
    
    # Cascade to children if requested
    if cascade:
        children = db.query(TestSessionModel).filter(TestSessionModel.parent_test_group_id == session_id).all()
        for child in children:
            child.vest_id = vest_id
    
    db.commit()
    db.refresh(session)
    
    # Return updated session with vest code
    vest = db.query(VestModel).filter(VestModel.id == vest_id).first()
    session_dict = {
        "id": session.id,
        "name": session.name,
        "test_date": session.test_date,
        "lab_name": session.lab_name,
        "protocol": session.protocol,
        "clay_temperature_c": session.clay_temperature_c,
        "ambient_temperature_c": session.ambient_temperature_c,
        "humidity_percent": session.humidity_percent,
        "conditioning": session.conditioning,
        "size": session.size,
        "ballistic_limit": session.ballistic_limit,
        "parent_test_group_id": session.parent_test_group_id,
        "vest_id": session.vest_id,
        "vest_name": vest.vest_code if vest else None,
        "vest_code": vest.vest_code if vest else None,
        "excel_file_path": session.excel_file_path,
        "notes": session.notes,
        "is_official": session.is_official,
        "certification_number": session.certification_number,
        "created_at": session.created_at,
        "updated_at": session.updated_at,
    }
    return session_dict


@router.get("/stats")
def get_stats(
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """Get statistics for dashboard"""
    # Count test sessions
    test_session_count = db.query(TestSessionModel).count()
    
    # Count shot data from Excel uploads
    shot_data_count = db.query(ShotDataModel).count()
    
    # Count manual shots
    manual_shots_count = db.query(ShotModel).count()
    
    print(f"DEBUG: test_session_count={test_session_count}, shot_data_count={shot_data_count}, manual_shots_count={manual_shots_count}")
    
    return {
        "test_session_count": test_session_count,
        "shot_data_count": shot_data_count,
        "manual_shots_count": manual_shots_count,
        "total_shots": shot_data_count + manual_shots_count
    }


@router.get("/{test_session_id}")
def get_test_session(
    test_session_id: str,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    test_session = db.query(TestSessionModel, VestModel).outerjoin(VestModel, TestSessionModel.vest_id == VestModel.id).filter(TestSessionModel.id == test_session_id).first()
    if not test_session:
        raise HTTPException(status_code=404, detail="Test session not found")
    
    session, vest = test_session
    
    session_dict = {
        "id": session.id,
        "name": session.name,
        "test_date": session.test_date,
        "lab_name": session.lab_name,
        "protocol": session.protocol,
        "clay_temperature_c": session.clay_temperature_c,
        "ambient_temperature_c": session.ambient_temperature_c,
        "humidity_percent": session.humidity_percent,
        "conditioning": session.conditioning,
        "size": session.size,
        "ballistic_limit": session.ballistic_limit,
        "parent_test_group_id": session.parent_test_group_id,
        "vest_id": session.vest_id,
        "vest": {
            "id": vest.id if vest else None,
            "vest_code": vest.vest_code if vest else None,
            "name": vest.vest_code if vest else None,
        } if vest else None,
        "excel_file_path": session.excel_file_path,
        "notes": session.notes,
        "is_official": session.is_official,
        "certification_number": session.certification_number,
        "created_at": session.created_at,
        "updated_at": session.updated_at,
    }
    return session_dict


@router.patch("/{test_session_id}", response_model=TestSession)
def update_test_session(
    test_session_id: str,
    test_session_update: TestSessionUpdate,
    cascade: bool = False,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_write_access)
):
    test_session = db.query(TestSessionModel).filter(TestSessionModel.id == test_session_id).first()
    if not test_session:
        raise HTTPException(status_code=404, detail="Test session not found")
    
    update_data = test_session_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(test_session, field, value)
    
    # Cascade protocol update to children if requested
    if cascade and 'protocol' in update_data:
        children = db.query(TestSessionModel).filter(TestSessionModel.parent_test_group_id == test_session_id).all()
        for child in children:
            child.protocol = update_data['protocol']
    
    db.commit()
    
    # Force refresh for parent and all children
    db.refresh(test_session)
    if cascade and 'protocol' in update_data:
        children = db.query(TestSessionModel).filter(TestSessionModel.parent_test_group_id == test_session_id).all()
        for child in children:
            db.refresh(child)
    
    return test_session


@router.delete("/{test_session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_test_session(
    test_session_id: str,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_write_access)
):
    test_session = db.query(TestSessionModel).filter(TestSessionModel.id == test_session_id).first()
    if not test_session:
        raise HTTPException(status_code=404, detail="Test session not found")

    # Query child sessions first
    child_sessions = db.query(TestSessionModel).filter(TestSessionModel.parent_test_group_id == test_session_id).all()

    # Audit log: Record what will be deleted before deletion
    audit_log = AuditLog(
        user_id=current_user.id,
        action="delete_test_session",
        entity_type="test_session",
        entity_id=test_session.id,
        before_json={
            "test_session": {
                "id": str(test_session.id),
                "name": test_session.name,
                "test_date": str(test_session.test_date) if test_session.test_date else None,
                "lab_name": test_session.lab_name,
                "protocol": test_session.protocol,
                "vest_id": str(test_session.vest_id) if test_session.vest_id else None,
                "excel_file_path": test_session.excel_file_path,
                "parent_test_group_id": str(test_session.parent_test_group_id) if test_session.parent_test_group_id else None,
            },
            "child_sessions": [
                {
                    "id": str(child.id),
                    "name": child.name,
                }
                for child in child_sessions
            ],
        },
        after_json={"status": "deleted"},
        created_at=datetime.now(timezone.utc)
    )
    db.add(audit_log)
    db.flush()

    # Null out parent_test_group_id to break the foreign key constraint
    db.query(TestSessionModel).filter(TestSessionModel.parent_test_group_id == test_session_id).update({"parent_test_group_id": None})
    db.flush()

    # Delete child sessions
    for child in child_sessions:
        # Delete shot data for child
        db.query(ShotDataModel).filter(ShotDataModel.test_session_id == child.id).delete()
        db.delete(child)

    # Delete associated shot data
    db.query(ShotDataModel).filter(ShotDataModel.test_session_id == test_session_id).delete()

    db.delete(test_session)
    db.commit()


@router.post("/{test_session_id}/upload-excel", response_model=TestSession)
def upload_excel_to_test_session(
    test_session_id: str,
    excel_file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    test_session = db.query(TestSessionModel).filter(TestSessionModel.id == test_session_id).first()
    if not test_session:
        raise HTTPException(status_code=404, detail="Test session not found")
    
    # Save Excel file with original filename
    os.makedirs(settings.material_docs_dir, exist_ok=True)
    file_path = os.path.join(settings.material_docs_dir, excel_file.filename)
    with open(file_path, 'wb') as f:
        f.write(excel_file.file.read())
    
    # Parse Excel
    try:
        parser = ExcelParser(file_path)
        shot_data, temperature, humidity = parser.parse()
    except ExcelParseError as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse Excel: {str(e)}")
    
    # Update test session with Excel file path and environmental data
    test_session.excel_file_path = excel_file.filename
    if not test_session.ambient_temperature_c:
        test_session.ambient_temperature_c = temperature
    if not test_session.humidity_percent:
        test_session.humidity_percent = humidity
    
    # Delete existing shot data for this test session
    db.query(ShotDataModel).filter(ShotDataModel.test_session_id == test_session_id).delete()
    
    # Insert new shot data
    for shot in shot_data:
        shot_data_db = ShotDataModel(
            test_session_id=test_session_id,
            **shot
        )
        db.add(shot_data_db)
    
    db.commit()
    db.refresh(test_session)
    return test_session


@router.post("/admin/bulk-reupload-all", response_model=List[TestSession])
def bulk_reupload_all_test_sessions(
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """
    Admin endpoint: Re-upload all test sessions that have an associated Excel file.
    This is useful for testing when the Excel parsing logic changes.
    WARNING: This will delete all existing test sessions and shot data before re-uploading.
    """
    # Get all parent test sessions with Excel files
    parent_sessions = db.query(TestSessionModel).filter(
        TestSessionModel.excel_file_path.isnot(None),
        TestSessionModel.parent_test_group_id.is_(None)
    ).all()
    
    if not parent_sessions:
        raise HTTPException(status_code=404, detail="No test sessions with Excel files found")
    
    all_created_sessions = []
    
    # First, verify all Excel files exist before deleting anything
    missing_files = []
    for parent_session in parent_sessions:
        excel_file_path = parent_session.excel_file_path
        if excel_file_path.startswith('./'):
            original_file_path = excel_file_path
        else:
            original_file_path = os.path.join(settings.material_docs_dir, excel_file_path)
        
        # If file not found, try to find it by filename in material_docs directory
        if not os.path.exists(original_file_path):
            filename = os.path.basename(excel_file_path)
            alt_path = os.path.join(settings.material_docs_dir, filename)
            if not os.path.exists(alt_path):
                missing_files.append(f"{parent_session.name}: {excel_file_path}")
    
    if missing_files:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot proceed with bulk reupload. The following Excel files are missing: {', '.join(missing_files)}"
        )
    
    # Collect all session IDs to be deleted
    all_session_ids = []
    for parent_session in parent_sessions:
        all_session_ids.append(parent_session.id)
        child_sessions = db.query(TestSessionModel).filter(TestSessionModel.parent_test_group_id == parent_session.id).all()
        all_session_ids.extend([child.id for child in child_sessions])
    
    # Audit log: Record what will be deleted before deletion
    deleted_test_sessions = db.query(TestSessionModel).filter(TestSessionModel.id.in_(all_session_ids)).all()
    deleted_shot_data = db.query(ShotDataModel).filter(ShotDataModel.test_session_id.in_(all_session_ids)).all()
    
    audit_log = AuditLog(
        user_id=current_user.id,
        action="bulk_reupload_all_test_sessions",
        entity_type="test_session",
        entity_id=None,
        before_json={
            "deleted_test_sessions": [
                {
                    "id": str(ts.id),
                    "name": ts.name,
                    "test_date": str(ts.test_date) if ts.test_date else None,
                    "lab_name": ts.lab_name,
                    "protocol": ts.protocol,
                    "vest_id": str(ts.vest_id) if ts.vest_id else None,
                    "excel_file_path": ts.excel_file_path,
                    "parent_test_group_id": str(ts.parent_test_group_id) if ts.parent_test_group_id else None,
                }
                for ts in deleted_test_sessions
            ],
            "deleted_shot_data_count": len(deleted_shot_data),
            "session_count": len(deleted_test_sessions),
        },
        after_json={"status": "deleted_before_reupload"},
        created_at=datetime.now(timezone.utc)
    )
    db.add(audit_log)
    db.flush()
    
    # Set parent_test_group_id to None for all sessions to break foreign key constraints
    db.query(TestSessionModel).filter(TestSessionModel.id.in_(all_session_ids)).update({"parent_test_group_id": None})
    db.flush()
    
    # Delete shot data for all sessions
    db.query(ShotDataModel).filter(ShotDataModel.test_session_id.in_(all_session_ids)).delete()
    
    # Delete all sessions
    db.query(TestSessionModel).filter(TestSessionModel.id.in_(all_session_ids)).delete()
    db.commit()
    
    # Now re-upload each Excel file
    for parent_session in parent_sessions:
        excel_file_path = parent_session.excel_file_path
        # Handle both relative paths starting with ./ and just filenames
        if excel_file_path.startswith('./'):
            original_file_path = excel_file_path
        else:
            original_file_path = os.path.join(settings.material_docs_dir, excel_file_path)
        
        # If file not found, try to find it by filename in material_docs directory
        if not os.path.exists(original_file_path):
            # Extract just the filename from the path
            filename = os.path.basename(excel_file_path)
            # Try to find the file in material_docs directory
            alt_path = os.path.join(settings.material_docs_dir, filename)
            if os.path.exists(alt_path):
                original_file_path = alt_path
            else:
                print(f"Excel file not found for {parent_session.name}: {excel_file_path}")
                continue
        
        # Re-upload the Excel file
        # Get location name if lab_name is provided
        location_name = parent_session.lab_name
        
        created_sessions = create_sessions_from_excel_data(
            db=db,
            excel_file_path=original_file_path,
            test_name=parent_session.name,
            location_name=location_name,
            protocol=parent_session.protocol,
            vest_id=parent_session.vest_id,
            test_date=parent_session.test_date,
            temperature=None,  # Service will extract from parsed data
            humidity=None,    # Service will extract from parsed data
            is_full_path=True,
        )
        all_created_sessions.extend(created_sessions)
    
    return all_created_sessions
