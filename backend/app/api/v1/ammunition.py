from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models import Ammunition as AmmunitionModel
from app.api.v1.auth import get_current_active_user, require_admin
from app.schemas.ammunition import AmmunitionCreate, AmmunitionUpdate, Ammunition, AmmunitionListItem
from app.db.models.user import User as UserModel



router = APIRouter(redirect_slashes=False)


@router.get("/", response_model=List[AmmunitionListItem])
def list_ammunition(
    skip: int = 0,
    limit: int = 100,
    caliber: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    query = db.query(AmmunitionModel)
    
    if caliber:
        query = query.filter(AmmunitionModel.caliber == caliber)
    
    ammunition = query.offset(skip).limit(limit).all()
    return ammunition


@router.post("/", response_model=Ammunition, status_code=status.HTTP_201_CREATED)
def create_ammunition(
    ammunition: AmmunitionCreate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_admin)
):
    db_ammunition = AmmunitionModel(**ammunition.model_dump())
    db.add(db_ammunition)
    db.commit()
    db.refresh(db_ammunition)
    return db_ammunition


@router.get("/{ammunition_id}", response_model=Ammunition)
def get_ammunition(
    ammunition_id: str,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    ammunition = db.query(AmmunitionModel).filter(AmmunitionModel.id == ammunition_id).first()
    if not ammunition:
        raise HTTPException(status_code=404, detail="Ammunition not found")
    return ammunition


@router.patch("/{ammunition_id}", response_model=Ammunition)
def update_ammunition(
    ammunition_id: str,
    ammunition_update: AmmunitionUpdate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_admin)
):
    ammunition = db.query(AmmunitionModel).filter(AmmunitionModel.id == ammunition_id).first()
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
    current_user: UserModel = Depends(require_admin)
):
    ammunition = db.query(AmmunitionModel).filter(AmmunitionModel.id == ammunition_id).first()
    if not ammunition:
        raise HTTPException(status_code=404, detail="Ammunition not found")
    
    db.delete(ammunition)
    db.commit()
