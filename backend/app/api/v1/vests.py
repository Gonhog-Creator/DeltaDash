from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from app.db.session import get_db
from app.db.models import Vest as VestModel, VestLayer
from app.db.models.material import Material
from app.db.models.test_session import TestSession
from app.db.models.shot_data import ShotData as ShotDataModel
from app.api.v1.auth import get_current_active_user, require_write_access
from app.schemas.vest import VestCreate, VestUpdate, Vest, VestListItem, VestLayerCreate
from app.db.models.user import User as UserModel



router = APIRouter(redirect_slashes=False)


def calculate_vest_thickness(vest_id: str, db: Session) -> Optional[float]:
    """Calculate total thickness from vest layers."""
    vest_layers = db.query(VestLayer).filter(VestLayer.vest_id == vest_id).all()
    if not vest_layers:
        return None
    
    total_thickness = 0.0
    for layer in vest_layers:
        if layer.material_id:
            material = db.query(Material).filter(Material.id == layer.material_id).first()
            if material and material.thickness_mm:
                layer_count = layer.layer_count or 1
                total_thickness += float(material.thickness_mm) * layer_count
    
    return round(total_thickness, 3) if total_thickness > 0 else None


@router.get("/", response_model=List[VestListItem])
def list_vests(
    skip: int = 0,
    limit: int = 100,
    vest_type: Optional[str] = None,
    threat_level: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    query = db.query(VestModel).options(joinedload(VestModel.layers))
    
    if vest_type:
        query = query.filter(VestModel.vest_type == vest_type)
    
    if threat_level:
        query = query.filter(VestModel.threat_level == threat_level)
    
    vests = query.offset(skip).limit(limit).all()
    
    # Build composition string for each vest
    result = []
    for vest in vests:
        # Get materials for this vest's layers
        material_ids = [layer.material_id for layer in vest.layers if layer.material_id]
        materials = {}
        if material_ids:
            material_records = db.query(Material).filter(Material.id.in_(material_ids)).all()
            materials = {m.id: m for m in material_records}
        
        # Build composition string
        composition_parts = []
        for layer in sorted(vest.layers, key=lambda l: l.layer_index):
            if layer.material_id and layer.material_id in materials:
                material = materials[layer.material_id]
                part = f"{layer.layer_count} {material.name}"
                composition_parts.append(part)
        
        vest_dict = {
            "id": vest.id,
            "vest_code": vest.vest_code,
            "vest_type": vest.vest_type,
            "threat_level": vest.threat_level,
            "protection_class": vest.protection_class,
            "total_layers": vest.total_layers,
            "total_thickness_mm": vest.total_thickness_mm,
            "sizes": vest.sizes,
            "created_by_username": vest.created_by_username if hasattr(vest, 'created_by_username') else None,
            "composition": ", ".join(composition_parts) if composition_parts else None
        }
        result.append(VestListItem(**vest_dict))
    
    return result


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
    
    # Calculate total thickness from layers
    calculated_thickness = calculate_vest_thickness(db_vest.id, db)
    if calculated_thickness is not None:
        db_vest.total_thickness_mm = calculated_thickness
    
    db.commit()
    db.refresh(db_vest)
    # Reload with layers
    db_vest = db.query(VestModel).options(joinedload(VestModel.layers)).filter(VestModel.id == db_vest.id).first()
    return db_vest


@router.get("/{vest_id}", response_model=Vest)
def get_vest(
    vest_id: str,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    vest = db.query(VestModel).options(joinedload(VestModel.layers)).filter(VestModel.id == vest_id).first()
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
    # Reload with layers
    vest = db.query(VestModel).options(joinedload(VestModel.layers)).filter(VestModel.id == vest_id).first()
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
    
    # Calculate total thickness from layers
    calculated_thickness = calculate_vest_thickness(vest_id, db)
    if calculated_thickness is not None:
        vest.total_thickness_mm = calculated_thickness
    
    db.commit()
    
    return db.query(VestLayer).filter(VestLayer.vest_id == vest_id).order_by(VestLayer.layer_index).all()


@router.post("/recalculate-thickness")
def recalculate_all_thicknesses(
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_write_access)
):
    """Recalculate total thickness for all vests based on their layers."""
    vests = db.query(VestModel).all()
    updated_count = 0
    
    for vest in vests:
        calculated_thickness = calculate_vest_thickness(vest.id, db)
        if calculated_thickness is not None and vest.total_thickness_mm != calculated_thickness:
            vest.total_thickness_mm = calculated_thickness
            updated_count += 1
    
    db.commit()
    return {"message": f"Updated thickness for {updated_count} vests"}


@router.get("/{vest_id}/test-sessions")
def get_vest_test_sessions(
    vest_id: str,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """Get all test sessions linked to a vest."""
    from app.db.models.test_session import TestSession
    
    vest = db.query(VestModel).filter(VestModel.id == vest_id).first()
    if not vest:
        raise HTTPException(status_code=404, detail="Vest not found")
    
    test_sessions = db.query(TestSession).filter(TestSession.vest_id == vest_id, TestSession.parent_test_group_id.is_(None)).all()
    
    result = []
    for session in test_sessions:
        # Count shots from parent session
        shot_count = db.query(ShotDataModel).filter(ShotDataModel.test_session_id == session.id).count()
        
        # Count shots from all child sessions
        child_sessions = db.query(TestSession).filter(TestSession.parent_test_group_id == session.id).all()
        for child in child_sessions:
            shot_count += db.query(ShotDataModel).filter(ShotDataModel.test_session_id == child.id).count()
        
        session_dict = {
            "id": session.id,
            "name": session.name,
            "test_date": session.test_date,
            "lab_name": session.lab_name,
            "protocol": session.protocol,
            "is_official": session.is_official,
            "certification_number": session.certification_number,
            "shot_count": shot_count,
            "created_at": session.created_at,
        }
        result.append(session_dict)
    
    return {
        "vest_code": vest.vest_code,
        "test_sessions": result
    }
