from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
import os
import uuid
from pathlib import Path

from app.db.session import get_db
from app.db.models import TestSession as TestSessionModel, ShotData as ShotDataModel, Shot as ShotModel
from app.api.v1.auth import get_current_active_user
from app.schemas.test_session import TestSessionCreate, TestSessionUpdate, TestSession
from app.schemas.shot_data import ShotDataCreate
from app.db.models.user import User as UserModel
from app.services.excel_parser import ExcelParser, ExcelParseError
from app.services.test_session_service import create_sessions_from_excel_data
from app.core.config import settings



router = APIRouter(redirect_slashes=False)


@router.get("/", response_model=List[TestSession])
def list_test_sessions(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    test_sessions = db.query(TestSessionModel).offset(skip).limit(limit).all()
    return test_sessions


@router.post("/", response_model=TestSession, status_code=status.HTTP_201_CREATED)
def create_test_session(
    test_session: TestSessionCreate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    db_test_session = TestSessionModel(**test_session.model_dump())
    db.add(db_test_session)
    db.commit()
    db.refresh(db_test_session)
    return db_test_session


@router.post("/from-excel", response_model=List[TestSession], status_code=status.HTTP_201_CREATED)
def create_test_session_from_excel(
    excel_file: UploadFile = File(...),
    test_name: str = Form(...),
    location_id: Optional[str] = Form(None),
    protocol: Optional[str] = Form(None),
    test_date: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    # Save Excel file
    os.makedirs(settings.material_docs_dir, exist_ok=True)
    file_ext = Path(excel_file.filename).suffix
    unique_filename = f"{uuid.uuid4()}{file_ext}"
    file_path = os.path.join(settings.material_docs_dir, unique_filename)
    with open(file_path, 'wb') as f:
        f.write(excel_file.file.read())
    
    # Get location name if location_id is provided
    location_name = None
    if location_id:
        from app.db.models.location import Location as LocationModel
        location = db.query(LocationModel).filter(LocationModel.id == location_id).first()
        location_name = location.name if location else None
    
    # Parse the Excel file - service will handle multi-sheet vs single-sheet
    # No need to extract temperature/humidity here - the service handles it
    return create_sessions_from_excel_data(
        db=db,
        excel_file_path=file_path,  # Pass full path since file was just saved
        test_name=test_name,
        location_name=location_name,
        operator=None,
        protocol=protocol,
        test_date=test_date,
        temperature=None,  # Service will extract from parsed data
        humidity=None,    # Service will extract from parsed data
        is_full_path=True,
    )


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


@router.get("/{test_session_id}", response_model=TestSession)
def get_test_session(
    test_session_id: str,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    test_session = db.query(TestSessionModel).filter(TestSessionModel.id == test_session_id).first()
    if not test_session:
        raise HTTPException(status_code=404, detail="Test session not found")
    return test_session


@router.patch("/{test_session_id}", response_model=TestSession)
def update_test_session(
    test_session_id: str,
    test_session_update: TestSessionUpdate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    test_session = db.query(TestSessionModel).filter(TestSessionModel.id == test_session_id).first()
    if not test_session:
        raise HTTPException(status_code=404, detail="Test session not found")
    
    update_data = test_session_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(test_session, field, value)
    
    db.commit()
    db.refresh(test_session)
    return test_session


@router.delete("/{test_session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_test_session(
    test_session_id: str,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    test_session = db.query(TestSessionModel).filter(TestSessionModel.id == test_session_id).first()
    if not test_session:
        raise HTTPException(status_code=404, detail="Test session not found")

    # Query child sessions first
    child_sessions = db.query(TestSessionModel).filter(TestSessionModel.parent_test_group_id == test_session_id).all()

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
    
    # Save Excel file
    os.makedirs(settings.material_docs_dir, exist_ok=True)
    file_ext = Path(excel_file.filename).suffix
    unique_filename = f"{uuid.uuid4()}{file_ext}"
    file_path = os.path.join(settings.material_docs_dir, unique_filename)
    with open(file_path, 'wb') as f:
        f.write(excel_file.file.read())
    
    # Parse Excel
    try:
        parser = ExcelParser(file_path)
        shot_data, temperature, humidity = parser.parse()
    except ExcelParseError as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse Excel: {str(e)}")
    
    # Update test session with Excel file path and environmental data
    test_session.excel_file_path = unique_filename
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
    """
    # Get all parent test sessions with Excel files
    parent_sessions = db.query(TestSessionModel).filter(
        TestSessionModel.excel_file_path.isnot(None),
        TestSessionModel.parent_test_group_id.is_(None)
    ).all()
    
    if not parent_sessions:
        raise HTTPException(status_code=404, detail="No test sessions with Excel files found")
    
    all_created_sessions = []
    
    for parent_session in parent_sessions:
        excel_file_path = parent_session.excel_file_path
        # Handle both relative paths starting with ./ and just filenames
        if excel_file_path.startswith('./'):
            original_file_path = excel_file_path
        else:
            original_file_path = os.path.join(settings.material_docs_dir, excel_file_path)
        
        if not os.path.exists(original_file_path):
            print(f"Excel file not found for {parent_session.name}: {excel_file_path}")
            continue
        
        # Delete this parent session and all child sessions
        child_sessions = db.query(TestSessionModel).filter(TestSessionModel.parent_test_group_id == parent_session.id).all()
        for child in child_sessions:
            db.query(ShotDataModel).filter(ShotDataModel.test_session_id == child.id).delete()
            db.delete(child)
        
        db.query(ShotDataModel).filter(ShotDataModel.test_session_id == parent_session.id).delete()
        db.delete(parent_session)
        db.commit()
        
        # Re-upload the Excel file
        # Note: Service now handles multi-sheet parsing internally
        # Get location name if lab_name is provided
        location_name = parent_session.lab_name
        
        created_sessions = create_sessions_from_excel_data(
            db=db,
            excel_file_path=original_file_path,
            test_name=parent_session.name,
            location_name=location_name,
            operator=parent_session.operator,
            protocol=parent_session.protocol,
            test_date=parent_session.test_date,
            temperature=None,  # Service will extract from parsed data
            humidity=None,    # Service will extract from parsed data
            is_full_path=True,
        )
        all_created_sessions.extend(created_sessions)
    
    return all_created_sessions
