from typing import List, Optional, Union
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models import ShotData as ShotDataModel, Shot as ShotModel
from app.api.v1.auth import get_current_active_user
from app.schemas.shot_data import ShotData
from app.schemas.shot import Shot
from app.db.models.user import User as UserModel
import uuid



router = APIRouter(redirect_slashes=False)


@router.get("/", response_model=List[Union[ShotData, Shot]])
def list_shot_data(
    skip: int = 0,
    limit: int = 100,
    test_session_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    # Convert test_session_id to UUID if provided
    test_session_uuid = None
    if test_session_id:
        try:
            test_session_uuid = uuid.UUID(test_session_id)
        except ValueError:
            print(f"Invalid test_session_id format: {test_session_id}")
    
    # Try ShotData table first (Excel uploads)
    shot_data_query = db.query(ShotDataModel)
    if test_session_uuid:
        shot_data_query = shot_data_query.filter(ShotDataModel.test_session_id == test_session_uuid)
    shot_data = shot_data_query.offset(skip).limit(limit).all()
    
    print(f"ShotData query result for test_session_id {test_session_id}: {shot_data}")
    
    # If no ShotData, try Shot table (manual entries)
    if not shot_data:
        shot_query = db.query(ShotModel)
        if test_session_uuid:
            shot_query = shot_query.filter(ShotModel.test_session_id == test_session_uuid)
        shots = shot_query.offset(skip).limit(limit).all()
        print(f"Shot query result for test_session_id {test_session_id}: {shots}")
        return shots
    
    return shot_data
