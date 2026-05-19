from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models import Vest as VestModel, VestLayer
from app.api.v1.auth import get_current_active_user, require_write_access
from app.schemas.vest import VestCreate, VestUpdate, Vest, VestListItem, VestLayerCreate
from app.db.models.user import User as UserModel



router = APIRouter(redirect_slashes=False)


@router.get("/", response_model=List[VestListItem])
def list_vests(
    skip: int = 0,
    limit: int = 100,
    vest_type: Optional[str] = None,
    threat_level: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    query = db.query(VestModel)
    
    if vest_type:
        query = query.filter(VestModel.vest_type == vest_type)
    
    if threat_level:
        query = query.filter(VestModel.threat_level == threat_level)
    
    vests = query.offset(skip).limit(limit).all()
    return vests


@router.post("/", response_model=Vest, status_code=status.HTTP_201_CREATED)
def create_vest(
    vest: VestCreate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_write_access)
):
    # Create vest without layers first
    vest_data = vest.model_dump(exclude={"layers"})
    db_vest = VestModel(**vest_data)
    db.add(db_vest)
    db.flush()
    
    # Create layers
    for layer_data in vest.layers:
        layer = VestLayer(
            vest_id=db_vest.id,
            **layer_data.model_dump()
        )
        db.add(layer)
    
    db.commit()
    db.refresh(db_vest)
    return db_vest


@router.get("/{vest_id}", response_model=Vest)
def get_vest(
    vest_id: str,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    vest = db.query(VestModel).filter(VestModel.id == vest_id).first()
    if not vest:
        raise HTTPException(status_code=404, detail="Vest not found")
    return vest


@router.patch("/{vest_id}", response_model=Vest)
def update_vest(
    vest_id: str,
    vest_update: VestUpdate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_write_access)
):
    vest = db.query(VestModel).filter(VestModel.id == vest_id).first()
    if not vest:
        raise HTTPException(status_code=404, detail="Vest not found")
    
    update_data = vest_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(vest, field, value)
    
    db.commit()
    db.refresh(vest)
    return vest


@router.delete("/{vest_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_vest(
    vest_id: str,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_write_access)
):
    vest = db.query(VestModel).filter(VestModel.id == vest_id).first()
    if not vest:
        raise HTTPException(status_code=404, detail="Vest not found")
    
    db.delete(vest)
    db.commit()


@router.get("/{vest_id}/layers")
def get_vest_layers(
    vest_id: str,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    vest = db.query(VestModel).filter(VestModel.id == vest_id).first()
    if not vest:
        raise HTTPException(status_code=404, detail="Vest not found")
    
    layers = db.query(VestLayer).filter(VestLayer.vest_id == vest_id).order_by(VestLayer.layer_index).all()
    return layers


@router.put("/{vest_id}/layers")
def update_vest_layers(
    vest_id: str,
    layers: list[VestLayerCreate],
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_write_access)
):
    vest = db.query(VestModel).filter(VestModel.id == vest_id).first()
    if not vest:
        raise HTTPException(status_code=404, detail="Vest not found")
    
    # Delete existing layers
    db.query(VestLayer).filter(VestLayer.vest_id == vest_id).delete()
    
    # Create new layers
    for layer_data in layers:
        layer = VestLayer(
            vest_id=vest_id,
            **layer_data.model_dump()
        )
        db.add(layer)
    
    db.commit()
    
    return db.query(VestLayer).filter(VestLayer.vest_id == vest_id).order_by(VestLayer.layer_index).all()
