from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models import ArmorPanel as ArmorPanelModel, ArmorPanelLayer
from app.api.v1.auth import get_current_active_user, require_write_access
from app.schemas.armor_panel import ArmorPanelCreate, ArmorPanelUpdate, ArmorPanel, ArmorPanelListItem, ArmorPanelLayerCreate
from app.db.models.user import User as UserModel



router = APIRouter(redirect_slashes=False)


@router.get("/", response_model=List[ArmorPanelListItem])
def list_panels(
    skip: int = 0,
    limit: int = 100,
    vest_type: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    query = db.query(ArmorPanelModel)
    
    if vest_type:
        query = query.filter(ArmorPanelModel.vest_type == vest_type)
    
    panels = query.offset(skip).limit(limit).all()
    return panels


@router.post("/", response_model=ArmorPanel, status_code=status.HTTP_201_CREATED)
def create_panel(
    panel: ArmorPanelCreate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_write_access)
):
    # Create panel without layers first
    panel_data = panel.model_dump(exclude={"layers"})
    db_panel = ArmorPanelModel(**panel_data)
    db.add(db_panel)
    db.flush()
    
    # Create layers
    for layer_data in panel.layers:
        layer = ArmorPanelLayer(
            panel_id=db_panel.id,
            **layer_data.model_dump()
        )
        db.add(layer)
    
    db.commit()
    db.refresh(db_panel)
    return db_panel


@router.get("/{panel_id}", response_model=ArmorPanel)
def get_panel(
    panel_id: str,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    panel = db.query(ArmorPanelModel).filter(ArmorPanelModel.id == panel_id).first()
    if not panel:
        raise HTTPException(status_code=404, detail="Panel not found")
    return panel


@router.patch("/{panel_id}", response_model=ArmorPanel)
def update_panel(
    panel_id: str,
    panel_update: ArmorPanelUpdate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_write_access)
):
    panel = db.query(ArmorPanelModel).filter(ArmorPanelModel.id == panel_id).first()
    if not panel:
        raise HTTPException(status_code=404, detail="Panel not found")
    
    update_data = panel_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(panel, field, value)
    
    db.commit()
    db.refresh(panel)
    return panel


@router.delete("/{panel_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_panel(
    panel_id: str,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_write_access)
):
    panel = db.query(ArmorPanelModel).filter(ArmorPanelModel.id == panel_id).first()
    if not panel:
        raise HTTPException(status_code=404, detail="Panel not found")
    
    db.delete(panel)
    db.commit()


@router.get("/{panel_id}/layers")
def get_panel_layers(
    panel_id: str,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    panel = db.query(ArmorPanelModel).filter(ArmorPanelModel.id == panel_id).first()
    if not panel:
        raise HTTPException(status_code=404, detail="Panel not found")
    
    layers = db.query(ArmorPanelLayer).filter(ArmorPanelLayer.panel_id == panel_id).order_by(ArmorPanelLayer.layer_index).all()
    return layers


@router.put("/{panel_id}/layers")
def update_panel_layers(
    panel_id: str,
    layers: list[ArmorPanelLayerCreate],
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_write_access)
):
    panel = db.query(ArmorPanelModel).filter(ArmorPanelModel.id == panel_id).first()
    if not panel:
        raise HTTPException(status_code=404, detail="Panel not found")
    
    # Delete existing layers
    db.query(ArmorPanelLayer).filter(ArmorPanelLayer.panel_id == panel_id).delete()
    
    # Create new layers
    for layer_data in layers:
        layer = ArmorPanelLayer(
            panel_id=panel_id,
            **layer_data.model_dump()
        )
        db.add(layer)
    
    db.commit()
    
    return db.query(ArmorPanelLayer).filter(ArmorPanelLayer.panel_id == panel_id).order_by(ArmorPanelLayer.layer_index).all()
