from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import Shot
from app.api.v1.auth import get_current_active_user
from app.schemas.user import User
from app.schemas.shot import ShotCreate, ShotUpdate, Shot

router = APIRouter()


@router.get("/", response_model=List[Shot])
def list_shots(
    skip: int = 0,
    limit: int = 100,
    test_session_id: str | None = None,
    panel_id: str | None = None,
    ammunition_id: str | None = None,
    penetration: bool | None = None,
    anomaly_flag: bool | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    query = db.query(Shot)
    
    if test_session_id:
        query = query.filter(Shot.test_session_id == test_session_id)
    if panel_id:
        query = query.filter(Shot.panel_id == panel_id)
    if ammunition_id:
        query = query.filter(Shot.ammunition_id == ammunition_id)
    if penetration is not None:
        query = query.filter(Shot.penetration == penetration)
    if anomaly_flag is not None:
        query = query.filter(Shot.anomaly_flag == anomaly_flag)
    
    shots = query.offset(skip).limit(limit).all()
    return shots


@router.post("/", response_model=Shot, status_code=status.HTTP_201_CREATED)
def create_shot(
    shot: ShotCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    db_shot = Shot(**shot.model_dump())
    db.add(db_shot)
    db.commit()
    db.refresh(db_shot)
    return db_shot


@router.get("/{shot_id}", response_model=Shot)
def get_shot(
    shot_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    shot = db.query(Shot).filter(Shot.id == shot_id).first()
    if not shot:
        raise HTTPException(status_code=404, detail="Shot not found")
    return shot


@router.patch("/{shot_id}", response_model=Shot)
def update_shot(
    shot_id: str,
    shot_update: ShotUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    shot = db.query(Shot).filter(Shot.id == shot_id).first()
    if not shot:
        raise HTTPException(status_code=404, detail="Shot not found")
    
    update_data = shot_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(shot, field, value)
    
    db.commit()
    db.refresh(shot)
    return shot


@router.delete("/{shot_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_shot(
    shot_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    shot = db.query(Shot).filter(Shot.id == shot_id).first()
    if not shot:
        raise HTTPException(status_code=404, detail="Shot not found")
    
    db.delete(shot)
    db.commit()
