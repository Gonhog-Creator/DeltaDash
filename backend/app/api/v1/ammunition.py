from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import Ammunition
from app.api.v1.auth import get_current_active_user
from app.schemas.user import User
from app.schemas.ammunition import AmmunitionCreate, AmmunitionUpdate, Ammunition, AmmunitionListItem

router = APIRouter()


@router.get("/", response_model=List[AmmunitionListItem])
def list_ammunition(
    skip: int = 0,
    limit: int = 100,
    caliber: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    query = db.query(Ammunition)
    
    if caliber:
        query = query.filter(Ammunition.caliber == caliber)
    
    ammunition = query.offset(skip).limit(limit).all()
    return ammunition


@router.post("/", response_model=Ammunition, status_code=status.HTTP_201_CREATED)
def create_ammunition(
    ammunition: AmmunitionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    db_ammunition = Ammunition(**ammunition.model_dump())
    db.add(db_ammunition)
    db.commit()
    db.refresh(db_ammunition)
    return db_ammunition


@router.get("/{ammunition_id}", response_model=Ammunition)
def get_ammunition(
    ammunition_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    ammunition = db.query(Ammunition).filter(Ammunition.id == ammunition_id).first()
    if not ammunition:
        raise HTTPException(status_code=404, detail="Ammunition not found")
    return ammunition


@router.patch("/{ammunition_id}", response_model=Ammunition)
def update_ammunition(
    ammunition_id: str,
    ammunition_update: AmmunitionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    ammunition = db.query(Ammunition).filter(Ammunition.id == ammunition_id).first()
    if not ammunition:
        raise HTTPException(status_code=404, detail="Ammunition not found")
    
    update_data = ammunition_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(ammunition, field, value)
    
    db.commit()
    db.refresh(ammunition)
    return ammunition


@router.delete("/{ammunition_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_ammunition(
    ammunition_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    ammunition = db.query(Ammunition).filter(Ammunition.id == ammunition_id).first()
    if not ammunition:
        raise HTTPException(status_code=404, detail="Ammunition not found")
    
    db.delete(ammunition)
    db.commit()
