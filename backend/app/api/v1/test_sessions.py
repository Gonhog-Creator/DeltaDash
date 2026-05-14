from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import TestSession
from app.api.v1.auth import get_current_active_user
from app.schemas.user import User
from app.schemas.test_session import TestSessionCreate, TestSessionUpdate, TestSession

router = APIRouter()


@router.get("/", response_model=List[TestSession])
def list_test_sessions(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    test_sessions = db.query(TestSession).offset(skip).limit(limit).all()
    return test_sessions


@router.post("/", response_model=TestSession, status_code=status.HTTP_201_CREATED)
def create_test_session(
    test_session: TestSessionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    db_test_session = TestSession(**test_session.model_dump())
    db.add(db_test_session)
    db.commit()
    db.refresh(db_test_session)
    return db_test_session


@router.get("/{test_session_id}", response_model=TestSession)
def get_test_session(
    test_session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    test_session = db.query(TestSession).filter(TestSession.id == test_session_id).first()
    if not test_session:
        raise HTTPException(status_code=404, detail="Test session not found")
    return test_session


@router.patch("/{test_session_id}", response_model=TestSession)
def update_test_session(
    test_session_id: str,
    test_session_update: TestSessionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    test_session = db.query(TestSession).filter(TestSession.id == test_session_id).first()
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
    current_user: User = Depends(get_current_active_user)
):
    test_session = db.query(TestSession).filter(TestSession.id == test_session_id).first()
    if not test_session:
        raise HTTPException(status_code=404, detail="Test session not found")
    
    db.delete(test_session)
    db.commit()
