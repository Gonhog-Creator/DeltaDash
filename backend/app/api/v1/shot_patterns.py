from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models import ShotPattern, ShotPatternPosition
from app.api.v1.auth import get_current_active_user, require_write_access
from app.schemas.shot_pattern import ShotPatternCreate, ShotPatternUpdate, ShotPattern, ShotPatternPositionCreate
from app.db.models.user import User as UserModel



router = APIRouter(redirect_slashes=False)


@router.get("/", response_model=List[ShotPattern])
def list_shot_patterns(
    skip: int = 0,
    limit: int = 100,
    vest_type: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    query = db.query(ShotPattern)
    
    if vest_type:
        query = query.filter(ShotPattern.vest_type == vest_type)
    
    patterns = query.offset(skip).limit(limit).all()
    return patterns


@router.post("/", response_model=ShotPattern, status_code=status.HTTP_201_CREATED)
def create_shot_pattern(
    pattern: ShotPatternCreate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_write_access)
):
    # Create pattern without positions first
    pattern_data = pattern.model_dump(exclude={"positions"})
    db_pattern = ShotPattern(**pattern_data)
    db.add(db_pattern)
    db.flush()
    
    # Create positions
    for position_data in pattern.positions:
        position = ShotPatternPosition(
            shot_pattern_id=db_pattern.id,
            **position_data.model_dump()
        )
        db.add(position)
    
    db.commit()
    db.refresh(db_pattern)
    return db_pattern


@router.get("/{shot_pattern_id}", response_model=ShotPattern)
def get_shot_pattern(
    shot_pattern_id: str,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    pattern = db.query(ShotPattern).filter(ShotPattern.id == shot_pattern_id).first()
    if not pattern:
        raise HTTPException(status_code=404, detail="Shot pattern not found")
    return pattern


@router.patch("/{shot_pattern_id}", response_model=ShotPattern)
def update_shot_pattern(
    shot_pattern_id: str,
    pattern_update: ShotPatternUpdate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_write_access)
):
    pattern = db.query(ShotPattern).filter(ShotPattern.id == shot_pattern_id).first()
    if not pattern:
        raise HTTPException(status_code=404, detail="Shot pattern not found")
    
    update_data = pattern_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(pattern, field, value)
    
    db.commit()
    db.refresh(pattern)
    return pattern


@router.delete("/{shot_pattern_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_shot_pattern(
    shot_pattern_id: str,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_write_access)
):
    pattern = db.query(ShotPattern).filter(ShotPattern.id == shot_pattern_id).first()
    if not pattern:
        raise HTTPException(status_code=404, detail="Shot pattern not found")
    
    db.delete(pattern)
    db.commit()


@router.get("/{shot_pattern_id}/positions")
def get_shot_pattern_positions(
    shot_pattern_id: str,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    pattern = db.query(ShotPattern).filter(ShotPattern.id == shot_pattern_id).first()
    if not pattern:
        raise HTTPException(status_code=404, detail="Shot pattern not found")
    
    positions = db.query(ShotPatternPosition).filter(ShotPatternPosition.shot_pattern_id == shot_pattern_id).order_by(ShotPatternPosition.shot_number).all()
    return positions


@router.put("/{shot_pattern_id}/positions")
def update_shot_pattern_positions(
    shot_pattern_id: str,
    positions: list[ShotPatternPositionCreate],
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_write_access)
):
    pattern = db.query(ShotPattern).filter(ShotPattern.id == shot_pattern_id).first()
    if not pattern:
        raise HTTPException(status_code=404, detail="Shot pattern not found")
    
    # Delete existing positions
    db.query(ShotPatternPosition).filter(ShotPatternPosition.shot_pattern_id == shot_pattern_id).delete()
    
    # Create new positions
    for position_data in positions:
        position = ShotPatternPosition(
            shot_pattern_id=shot_pattern_id,
            **position_data.model_dump()
        )
        db.add(position)
    
    db.commit()
    
    return db.query(ShotPatternPosition).filter(ShotPatternPosition.shot_pattern_id == shot_pattern_id).order_by(ShotPatternPosition.shot_number).all()
